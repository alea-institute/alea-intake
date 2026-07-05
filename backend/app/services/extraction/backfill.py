"""Fact-extraction backfill — extract legal facts from an intake's ingested
messages just before analysis runs.

Root-cause fix (persona UAT campaign, 2026-07): no ingestion path (text WS
handler, document upload, or voice transcript) ever invoked
``FactExtractionService.extract_and_persist``. The orchestrator loads facts via
``_load_facts(intake_id)``, which therefore always returned an empty list, so
every analysis run produced 0 claims / 0 gaps / 0 questions and an empty memo.

This module bridges the gap at analysis-trigger time: it finds every non-system
message for the intake that does not yet have extracted facts, normalizes it, and
runs extraction + FOLIO concept resolution. Running at trigger time makes the fix
a single wiring point that covers all ingestion modalities (text, document, voice)
at once, and is idempotent (already-extracted messages are skipped).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.fact import ExtractedFact
from app.models.intake import IntakeSession, Message
from app.services.extraction.fact_extraction import FactExtractionService
from app.services.intake.message_pipeline import normalize_text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def backfill_intake_facts(
    db: AsyncSession,
    intake_id: int,
    llm_service: LLMService,
    folio: Any | None = None,
    embedding_service: Any | None = None,
) -> int:
    """Extract + persist facts for every un-extracted, non-system message of an intake.

    Returns the number of newly created ``ExtractedFact`` rows. Idempotent:
    messages that already have facts are skipped, so re-running before each
    analysis only processes new input. Never raises for a single bad message —
    extraction failures are logged and skipped so analysis still proceeds.
    """
    # All sessions belonging to this intake.
    session_ids = (
        await db.execute(
            select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
        )
    ).scalars().all()
    if not session_ids:
        return 0

    # Consumer/professional messages (exclude system LLM replies), in order.
    messages = (
        await db.execute(
            select(Message)
            .where(
                Message.session_id.in_(session_ids),
                Message.sender_type != "system",
            )
            .order_by(Message.sequence_number)
        )
    ).scalars().all()
    if not messages:
        return 0

    # Messages that already have facts — skip them (idempotency).
    already = set(
        (
            await db.execute(
                select(ExtractedFact.message_id).where(
                    ExtractedFact.intake_id == intake_id
                )
            )
        ).scalars().all()
    )

    service = FactExtractionService(
        llm_service=llm_service,
        db_session=db,
        folio=folio,
        embedding_service=embedding_service,
    )

    session_facts: list[dict] = []
    created_total = 0
    for msg in messages:
        if msg.id in already:
            continue
        raw = msg.content_encrypted or b""
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        normalized = normalize_text(text, msg.id, msg.party_id)
        try:
            facts = await service.extract_and_persist(
                normalized,
                intake_id=intake_id,
                message_id=msg.id,
                party_id=msg.party_id,
                session_facts=session_facts,
            )
        except Exception:
            logger.warning(
                "Fact backfill failed for message %d (intake %d); skipping",
                msg.id,
                intake_id,
                exc_info=True,
            )
            continue
        created_total += len(facts)
        for f in facts:
            session_facts.append({"assertion_text": getattr(f, "assertion_text", "")})

    logger.info(
        "Fact backfill: created %d facts across %d messages for intake %d",
        created_total,
        len(messages),
        intake_id,
    )
    return created_total
