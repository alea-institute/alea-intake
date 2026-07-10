"""Deadline detection stage -- probabilistic detect -> deterministic compute + persist.

Gathers an intake's consumer message text plus extracted facts, asks the LLM to
extract time-sensitive ``DeadlineEvent``s (structured, mockable -- mirrors
``FactExtractionService._call_llm_extraction``), runs the deterministic
``compute_deadlines`` engine, and persists ``Deadline`` rows for the run.

Integration note: this stage is invoked from the analysis router at trigger time
(right after the run is created and facts are backfilled), NOT inserted into the
orchestrator STAGES loop. The loop's per-stage argument dispatch, STAGES
indexing (resume/convergence), and per-jurisdiction fan-out make inserting a new
stage there invasive and risky for the convergence logic; a decoupled call keeps
detection additive and lets it degrade gracefully (LLM failure -> zero deadlines,
analysis never crashes).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.analysis import Deadline
from app.models.fact import ExtractedFact
from app.models.intake import IntakeSession, Message
from app.services.deadline.engine import compute_deadlines
from app.services.deadline.schemas import (
    DeadlineEvent,
    DeadlineEventSchema,
    DeadlineExtractionResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


DEADLINE_SYSTEM_PROMPT = """You are a legal deadline-detection assistant. Given narrative text from a legal
intake, extract every TIME-SENSITIVE event that could create a legal deadline or
statute-of-limitations concern (eviction summons/hearing, being served with a
petition, a notice to vacate or cure, a filing, an injury/incident, an
immigration entry or hearing, etc.).

TODAY'S DATE IS {today}. Interpret every date in the narrative relative to this
anchor:
- Preserve any year the text states verbatim -- if the client writes
  "August 20, 2026", the year is 2026. NEVER shift a stated year.
- If a month/day is given with no year, choose the year that makes the event
  make sense relative to today (an upcoming hearing is in the future; a past
  injury is in the past). Do NOT default to a prior year.
- A stated court date, hearing date, or filing deadline that is already an
  explicit calendar date IS itself the operative deadline -- return it as the
  event's `date`.

For each event return:
- event_type: short category, e.g. "eviction_summons", "eviction_hearing",
  "custody_response", "notice_to_vacate", "asylum_entry", "removal_hearing",
  "master_calendar_hearing", "filing_deadline", "injury".
- raw_text: the exact narrative snippet the event came from.
- trigger: the triggering act -- one of "served", "service", "notice_posted",
  "hearing", "filed", "incident", "entry", "deadline".
  * When the client was SERVED with a petition, summons, or complaint (divorce,
    custody, dissolution, eviction, civil suit), use trigger="served" and set
    `date` to the DATE THEY WERE SERVED — NOT the response deadline. The engine
    computes the response deadline from the service date (e.g. a served
    Minnesota family petition = answer due 30 days later). Do this even if the
    client also states "I have to respond by <date>"; the service date is what
    the deadline rule needs.
  * Use "hearing" for a scheduled court appearance date (the stated date IS the
    deadline).
  * Reserve "deadline" ONLY for an explicitly stated filing/response deadline
    that stands alone with no service/trigger date to compute from.
- date: the trigger date in ISO 8601 (YYYY-MM-DD), or null if not stated. For a
  "served" event this is the service date, not the downstream response deadline.
- jurisdiction_hint: the U.S. state (two-letter, e.g. "MN") or "US"/"federal"
  for immigration-court / federal matters. Infer it from the narrative (a
  Minnesota address, a Hennepin County court, an immigration court, ICE/EOIR,
  USCIS) even when not stated as an abbreviation. Use null only when truly
  indeterminable.
- window_days: an explicit cure/response window in days if the text states one,
  else null.

Rules:
1. Only extract events explicitly supported by the text. Never invent dates.
2. Normalize dates to ISO 8601. If only a partial date is given, apply the
   year-anchoring guidance above rather than returning null.

Return a JSON object matching: {{"events": [ ... ]}}."""


class DeadlineDetectStage:
    """Detect time-sensitive events, compute deadlines, and persist them."""

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
    ) -> None:
        self._llm = llm_service
        self._session = db_session

    async def _call_llm_extraction(self, text: str, today: date | None = None) -> dict[str, Any]:
        """Call the LLM to extract deadline events. Returns raw JSON dict.

        Separated for easy mocking in tests (mirrors FactExtractionService).
        ``today`` anchors the year-resolution guidance in the prompt so the model
        never mis-dates an event to a prior year (BUG-12).
        """
        anchor = (today or date.today()).isoformat()
        messages = [
            {"role": "system", "content": DEADLINE_SYSTEM_PROMPT.format(today=anchor)},
            {"role": "user", "content": text},
        ]

        config = self._llm.get_client_config()

        from alea_llm_client import AnthropicModel, GoogleModel, OpenAIModel, VLLMModel

        _provider_map = {
            "openai": OpenAIModel,
            "anthropic": AnthropicModel,
            "google": GoogleModel,
            "vllm": VLLMModel,
        }

        model_cls = _provider_map.get(config["provider"])
        if model_cls is None:
            logger.error("Unknown LLM provider: %s", config["provider"])
            return {"events": []}

        init_kwargs: dict[str, Any] = {
            "api_key": config.get("api_key"),
            "model": config.get("model"),
        }
        if "endpoint" in config:
            init_kwargs["endpoint"] = config["endpoint"]

        model = model_cls(**init_kwargs)
        response = await model.json_async(messages=messages)
        return response.data

    async def detect_and_persist(
        self,
        intake_id: int,
        run_id: int,
        jurisdiction: str | None = None,
        today: date | None = None,
    ) -> list[Deadline]:
        """Detect events, compute deadlines, and persist Deadline rows.

        Degrades gracefully: any LLM/parse failure yields zero deadlines and
        never raises, so analysis is unaffected.
        """
        text = await self._gather_text(intake_id)
        if not text.strip():
            return []

        ref_today = today or date.today()

        # --- Detect (probabilistic, mockable) ---
        try:
            raw = await self._call_llm_extraction(text, today=ref_today)
            parsed = DeadlineExtractionResult.model_validate(raw)
        except Exception:
            logger.warning(
                "Deadline event extraction failed for intake %d; no deadlines produced",
                intake_id,
                exc_info=True,
            )
            return []

        events = [self._to_event(e) for e in parsed.events]
        if not events:
            return []

        # --- Compute (deterministic) ---
        computed = compute_deadlines(events, jurisdiction=jurisdiction, today=ref_today)

        # --- Persist ---
        created: list[Deadline] = []
        for cd in computed:
            row = Deadline(
                intake_id=intake_id,
                run_id=run_id,
                event_text=cd.event_text,
                event_type=cd.event_type or None,
                trigger=cd.trigger or None,
                trigger_date=cd.trigger_date,
                computed_date=cd.computed_date,
                rule_id=cd.rule_id,
                citation=cd.citation,
                computed=cd.computed,
                urgency=cd.urgency,
                hedge=cd.hedge,
                jurisdiction=cd.jurisdiction,
                source_message_id=cd.source_message_id,
                source_start=cd.source_start,
                source_end=cd.source_end,
                metadata_json={"window_days": cd.window_days} if cd.window_days else None,
            )
            self._session.add(row)
            created.append(row)

        await self._session.flush()
        logger.info(
            "Deadline detection: persisted %d deadlines (%d computed) for intake %d run %d",
            len(created),
            sum(1 for c in created if c.computed),
            intake_id,
            run_id,
        )
        return created

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_event(schema: DeadlineEventSchema) -> DeadlineEvent:
        parsed_date: date | None = None
        if schema.date:
            try:
                parsed_date = date.fromisoformat(schema.date[:10])
            except ValueError:
                parsed_date = None
        return DeadlineEvent(
            event_type=schema.event_type or "",
            raw_text=schema.raw_text or "",
            trigger=schema.trigger or "",
            date=parsed_date,
            jurisdiction_hint=schema.jurisdiction_hint,
            window_days=schema.window_days,
            source_start=schema.source_start,
            source_end=schema.source_end,
        )

    async def _gather_text(self, intake_id: int) -> str:
        """Concatenate the intake's consumer/professional message text + fact assertions.

        Mirrors backfill's message selection (non-system messages in order) so
        detection sees the same narrative the pipeline extracted facts from.
        """
        session_ids = (
            await self._session.execute(
                select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
            )
        ).scalars().all()

        parts: list[str] = []
        if session_ids:
            messages = (
                await self._session.execute(
                    select(Message)
                    .where(
                        Message.session_id.in_(session_ids),
                        Message.sender_type != "system",
                    )
                    .order_by(Message.sequence_number)
                )
            ).scalars().all()
            for msg in messages:
                raw = msg.content_encrypted or b""
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    parts.append(text)

        # Extracted fact assertions add normalized dates/events the LLM may reuse.
        facts = (
            await self._session.execute(
                select(ExtractedFact).where(
                    ExtractedFact.intake_id == intake_id,
                    ExtractedFact.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        for f in facts:
            if f.assertion_text:
                parts.append(f.assertion_text)

        return "\n".join(parts)
