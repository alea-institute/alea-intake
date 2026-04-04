"""Per-message safety screening middleware with priority-based interrupt model.

Provides the screen_message_fast function that runs on every consumer message
throughout the conversation. Uses TriggerMatcher from Plan 01 for <50ms
keyword/regex/concept matching. Three-tier priority dispatch:
  - Critical: immediate WebSocket safety_alert with resources
  - Elevated: queued for next conversation pause
  - Advisory: folded into next exploration round

Also provides ScreeningEvent persistence for audit trail.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningEvent
from app.services.exploration.schemas import ScreeningResult
from app.services.screening.trigger_matcher import TriggeredProtocol, TriggerMatcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session-level TriggerMatcher cache
# ---------------------------------------------------------------------------
# Maps session_id -> (TriggerMatcher, loaded_at_time)
# Reloads every 300 seconds or on first use for a session.
_matcher_cache: dict[int, tuple[TriggerMatcher, float]] = {}
_CACHE_TTL_SECONDS = 300.0


def _get_or_build_matcher(
    session_id: int,
    active_protocols: list[tuple],
) -> TriggerMatcher:
    """Return a cached TriggerMatcher for the session, or build a new one.

    Caches the matcher per session_id to avoid recompiling regex on every message.
    TTL of 5 minutes ensures protocol activation changes are picked up.
    """
    now = time.monotonic()
    cached = _matcher_cache.get(session_id)
    if cached is not None:
        matcher, loaded_at = cached
        if (now - loaded_at) < _CACHE_TTL_SECONDS:
            return matcher

    matcher = TriggerMatcher(active_protocols)
    _matcher_cache[session_id] = (matcher, now)
    return matcher


def clear_matcher_cache(session_id: int | None = None) -> None:
    """Clear the matcher cache for a specific session or all sessions."""
    if session_id is not None:
        _matcher_cache.pop(session_id, None)
    else:
        _matcher_cache.clear()


# ---------------------------------------------------------------------------
# Core screening function
# ---------------------------------------------------------------------------


async def screen_message_fast(
    content: str,
    session_id: int,
    db_session: AsyncSession,
    active_protocols: list[tuple] | None = None,
    question_transparency: bool = True,
) -> ScreeningResult:
    """Fast per-message screening against active protocol triggers.

    Designed for <50ms execution. Uses TriggerMatcher for keyword/regex/concept
    matching, then groups results by severity tier and builds the ScreeningResult.

    Args:
        content: The consumer's message text to screen.
        session_id: The current intake session ID.
        db_session: Async DB session for loading protocols if not provided.
        active_protocols: Optional pre-loaded list of (OrgProtocolActivation, ProtocolVersion).
            If None, loads from ProtocolService.
        question_transparency: Whether to use text_transparent variant of questions.

    Returns:
        ScreeningResult with triggered protocols, safety resources, mandatory questions.
    """
    # Load protocols if not provided
    if active_protocols is None:
        try:
            from app.services.screening.protocol_service import ProtocolService

            protocol_svc = ProtocolService(db_session)
            active_protocols = await protocol_svc.get_active_protocols(include_versions=True)
        except Exception:
            logger.warning("Failed to load active protocols; screening skipped", exc_info=True)
            return ScreeningResult()

    if not active_protocols:
        return ScreeningResult()

    # Get or build the cached TriggerMatcher
    matcher = _get_or_build_matcher(session_id, active_protocols)

    # Fast match
    triggered: list[TriggeredProtocol] = matcher.match_fast(content)

    if not triggered:
        return ScreeningResult()

    # Group by severity tier
    critical_triggers: list[TriggeredProtocol] = []
    elevated_triggers: list[TriggeredProtocol] = []
    advisory_triggers: list[TriggeredProtocol] = []

    for tp in triggered:
        if tp.severity_tier == "critical":
            critical_triggers.append(tp)
        elif tp.severity_tier == "elevated":
            elevated_triggers.append(tp)
        else:
            advisory_triggers.append(tp)

    # Build protocol dicts for the result
    triggered_dicts: list[dict] = []
    for tp in triggered:
        triggered_dicts.append({
            "protocol_id": tp.protocol_id,
            "protocol_name": tp.protocol_name,
            "severity_tier": tp.severity_tier,
            "version_id": tp.version_id,
            "trigger_type": tp.trigger_type,
            "matched_terms": tp.matched_terms,
        })

    # Extract safety resources and mandatory questions from critical triggers
    safety_resources: list[dict] = []
    mandatory_questions: list[dict] = []

    if critical_triggers:
        # Build a version lookup from active_protocols
        version_lookup: dict[int, Any] = {}
        for _act, ver in active_protocols:
            version_lookup[ver.id] = ver

        for tp in critical_triggers:
            version = version_lookup.get(tp.version_id)
            if version is None:
                continue

            # Extract safety resources
            if version.safety_resources_json:
                sr = version.safety_resources_json
                if isinstance(sr, dict):
                    for key, resources in sr.items():
                        if isinstance(resources, list):
                            safety_resources.extend(resources)
                elif isinstance(sr, list):
                    safety_resources.extend(sr)

            # Extract immediate resources from escalation_actions
            esc = version.escalation_actions_json or {}
            immediate_res = esc.get("immediate_resources", [])
            if isinstance(immediate_res, list):
                for res in immediate_res:
                    # Avoid duplicates by name
                    if not any(r.get("name") == res.get("name") for r in safety_resources):
                        safety_resources.append(res)

            # Extract mandatory questions
            questions = version.questions_json or []
            for q in questions:
                if q.get("is_mandatory"):
                    question_dict = dict(q)
                    # Apply transparency setting
                    if question_transparency and q.get("text_transparent"):
                        question_dict["text"] = q["text_transparent"]
                    # Keep original text if not transparent
                    mandatory_questions.append(question_dict)

    # Sort mandatory questions by priority
    mandatory_questions.sort(key=lambda q: q.get("priority", 999))

    return ScreeningResult(
        triggered_protocols=triggered_dicts,
        has_critical=len(critical_triggers) > 0,
        has_elevated=len(elevated_triggers) > 0,
        has_advisory=len(advisory_triggers) > 0,
        safety_resources=safety_resources,
        mandatory_questions=mandatory_questions,
        needs_deep_scan=len(critical_triggers) > 0,
    )


# ---------------------------------------------------------------------------
# ScreeningEvent persistence
# ---------------------------------------------------------------------------


async def persist_screening_event(
    db_session: AsyncSession,
    session_id: int,
    triggered: dict,
    action_taken: str,
) -> ScreeningEvent:
    """Create and persist a ScreeningEvent audit record.

    Args:
        db_session: Async DB session.
        session_id: The intake session ID.
        triggered: Dict with protocol_id, severity_tier, version_id, trigger_type, matched_terms.
        action_taken: One of "immediate_alert", "queued", "folded_to_exploration".

    Returns:
        The persisted ScreeningEvent.
    """
    event = ScreeningEvent(
        session_id=session_id,
        protocol_id=triggered.get("protocol_id", 0),
        protocol_version_id=triggered.get("version_id", 0),
        severity_tier=triggered.get("severity_tier", "advisory"),
        trigger_details_json={
            "trigger_type": triggered.get("trigger_type"),
            "matched_terms": triggered.get("matched_terms", []),
            "protocol_name": triggered.get("protocol_name", ""),
        },
        action_taken=action_taken,
    )
    db_session.add(event)
    await db_session.flush()
    return event


# ---------------------------------------------------------------------------
# Priority dispatch helpers
# ---------------------------------------------------------------------------


def build_safety_alert_message(screening_result: ScreeningResult) -> dict:
    """Build the WebSocket JSON message for critical safety alerts.

    Returns a dict suitable for WebSocket send_json with type="safety_alert".
    """
    return {
        "type": "safety_alert",
        "severity": "critical",
        "resources": screening_result.safety_resources,
        "questions": screening_result.mandatory_questions,
        "message": "We want to make sure you're safe. Here are some resources that may help.",
    }


async def queue_elevated_screening(
    db_session: AsyncSession,
    session_id: int,
    triggered_protocols: list[dict],
) -> None:
    """Persist queued ScreeningEvent records for elevated-tier triggers.

    These are surfaced at the next conversation pause (e.g., when the system
    generates follow-up questions).
    """
    for tp in triggered_protocols:
        await persist_screening_event(
            db_session=db_session,
            session_id=session_id,
            triggered=tp,
            action_taken="queued",
        )


async def add_to_exploration_queue(
    db_session: AsyncSession,
    session_id: int,
    triggered_protocols: list[dict],
) -> None:
    """Persist ScreeningEvent records for advisory-tier triggers.

    These inform the next exploration round about additional areas to explore.
    """
    for tp in triggered_protocols:
        await persist_screening_event(
            db_session=db_session,
            session_id=session_id,
            triggered=tp,
            action_taken="folded_to_exploration",
        )
