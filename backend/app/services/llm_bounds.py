"""Output bounds shared by every structured LLM call in analysis.

A live guest intake on Claude (2026-11-08) never finished analysis: fact
mapping and gap analysis asked for unbounded lists, every reply ran to the
8192-token ceiling, the truncated JSON failed to parse, and alea-llm-client
resent each identical request up to three times. These helpers carry the
pattern fact extraction already uses (``services/extraction``):

* bound each call -- batch inputs, cap list lengths, demand terse fields;
* turn the client's blind retries off and retry at most once, with a compact
  request, before degrading to an empty result for that call;
* validate item by item, dropping and counting bad items.

Logs carry stage labels, counts and exception type names only. Replies and
exception messages can carry visitor content, so neither reaches a log.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

logger = structlog.get_logger(__name__)

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

# One retry, with a compact (non-identical) request; never more.
MAX_JSON_ATTEMPTS = 2
# Concurrent LLM calls within one stage.
DEFAULT_CONCURRENCY = 4

TERSE_JSON_RULES = (
    "Reply with exactly one JSON object and nothing else: no prose, no markdown "
    "fences, no placeholder or example object, and no \"Correction:\" or second "
    "attempt. Write the final answer once."
)


@dataclass(frozen=True)
class ShowcaseCaps:
    """Tighter output caps for showcase demos (see ``ALEA_SHOWCASE_*``)."""

    claims: int
    gaps: int
    questions: int
    mappings_per_fact: int
    facts_per_extraction: int
    rationale_words: int


def showcase_caps() -> ShowcaseCaps | None:
    """Showcase output caps, or None outside showcase mode.

    Authenticated deployments get None and keep every prompt unchanged (the
    offline replay harness keys recordings by prompt hash).
    """
    from app import config as app_config

    settings = app_config.get_settings()
    if not settings.showcase_mode:
        return None
    return ShowcaseCaps(
        claims=max(1, settings.showcase_max_claims),
        gaps=max(1, settings.showcase_max_gaps),
        questions=max(1, settings.showcase_max_questions),
        mappings_per_fact=max(1, settings.showcase_max_mappings_per_fact),
        facts_per_extraction=max(1, settings.showcase_max_facts_per_extraction),
        rationale_words=max(4, settings.showcase_rationale_words),
    )


def compact_instruction(max_items: int) -> str:
    """The retry instruction after a truncated or unparseable reply."""
    return (
        "Your previous reply was cut off or was not valid JSON. Reply again with "
        f"one complete JSON object containing at most {max_items} items, every "
        "text field under 15 words. " + TERSE_JSON_RULES
    )


def limit_client_retries(client: Any) -> None:
    """Stop alea-llm-client re-sending an identical request on a bad reply.

    Its retry wrapper resends the same request up to three times when the
    JSON reply fails to parse, which multiplied truncated 8192-token replies.
    The caller owns the single retry instead.
    """
    target = getattr(client, "_model", client)
    if hasattr(target, "retry_limit"):
        try:
            target.retry_limit = 1
        except (AttributeError, TypeError):  # pragma: no cover - exotic clients
            pass


def first_validation_error(exc: ValidationError) -> str:
    """Describe a validation failure by type and field path, never by content."""
    errors = exc.errors(include_input=False, include_url=False)
    if not errors:
        return "unknown"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "<root>"
    return f"{first.get('type', 'unknown')} at {loc}"


def validate_items(
    raw: Any, schema: type[M], *, stage: str, limit: int | None = None
) -> list[M]:
    """Validate a reply's list item by item; drop and count the bad ones."""
    if not isinstance(raw, list):
        return []
    items: list[M] = []
    dropped = 0
    first_error = None
    for item in raw:
        try:
            items.append(schema.model_validate(item))
        except ValidationError as exc:
            dropped += 1
            first_error = first_error or first_validation_error(exc)
    if dropped:
        logger.warning(
            "llm_items_dropped", stage=stage, dropped=dropped, total=len(raw),
            first_failure=first_error,
        )
    if limit is not None and len(items) > limit:
        logger.info("llm_items_capped", stage=stage, total=len(items), cap=limit)
        items = items[:limit]
    return items


def list_field(data: Any, key: str) -> list | None:
    """Return ``data[key]`` when it is a list; accept a bare list reply too."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return data[key]
    return None


async def bounded_call(
    call: Callable[[bool], Awaitable[Any]],
    parse: Callable[[Any], T | None],
    *,
    stage: str,
    default: T,
) -> T:
    """Run ``call`` at most twice and return ``parse``'s first usable result.

    ``call(compact)`` performs one LLM request; the second attempt passes
    ``compact=True`` so the caller can shrink the request. ``parse`` returns
    None for an unusable reply (no expected list, wrong shape). When both
    attempts fail, the call degrades to ``default`` and logs the stage only.
    """
    for attempt in range(1, MAX_JSON_ATTEMPTS + 1):
        try:
            raw = await call(attempt > 1)
        except Exception as exc:  # truncated JSON surfaces here as a parse error
            logger.warning(
                "llm_call_failed", stage=stage, attempt=attempt,
                attempts=MAX_JSON_ATTEMPTS, exc_type=type(exc).__name__,
            )
            continue
        result = parse(raw)
        if result is not None:
            return result
        logger.warning(
            "llm_reply_unusable", stage=stage, attempt=attempt,
            attempts=MAX_JSON_ATTEMPTS, reply_type=type(raw).__name__,
        )
    logger.warning("llm_call_degraded", stage=stage, attempts=MAX_JSON_ATTEMPTS)
    return default


def batched(items: Sequence[T], size: int) -> list[list[T]]:
    """Split ``items`` into consecutive batches of at most ``size``."""
    size = max(1, size)
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


async def gather_bounded(
    calls: Sequence[Callable[[], Awaitable[T]]],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[T]:
    """Run independent LLM calls concurrently, at most ``concurrency`` at once.

    Callers pass only LLM work here: an AsyncSession is not safe to share
    across concurrent tasks, so database reads happen before and writes after.
    """
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run(call: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await call()

    return list(await asyncio.gather(*(run(call) for call in calls)))
