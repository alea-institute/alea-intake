"""Tests for the pre-analysis fact backfill (app.services.extraction.backfill).

Exercises ``backfill_intake_facts`` against a real SQLite-backed AsyncSession,
reusing the same fixture patterns as ``test_fact_extraction.py``. The LLM call
is stubbed by patching ``FactExtractionService._call_llm_extraction`` at the
class level, because ``backfill_intake_facts`` constructs the service itself.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Set required env var for Settings
os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.fact import ExtractedFact
from app.models.intake import Intake, IntakeParty, IntakeSession
from app.services.extraction.backfill import backfill_intake_facts
from app.services.extraction.fact_extraction import FactExtractionService
from app.services.intake.session_service import IntakeSessionService


# ---- Fixtures (mirror test_fact_extraction.py) ----


@pytest.fixture
async def test_engine():
    """Create a test DB engine with all tenant/shared tables (schemaless)."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    import app.models  # noqa: F401

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(_tenant_meta.drop_all)
        await conn.run_sync(_shared_meta.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Provide a session for DB operations."""
    async with test_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def intake_scaffold(db_session):
    """Create an intake with one party and one active session (no messages yet)."""
    intake = Intake(
        org_id=1,
        created_by_user_id=1,
        session_mode="multi_session",
        status="active",
    )
    db_session.add(intake)
    await db_session.flush()

    party = IntakeParty(
        intake_id=intake.id,
        user_id=1,
        role_in_intake="primary",
    )
    db_session.add(party)
    await db_session.flush()

    intake_session = IntakeSession(
        intake_id=intake.id,
        status="active",
    )
    db_session.add(intake_session)
    await db_session.flush()

    return {"intake": intake, "party": party, "session": intake_session}


def _extraction_json():
    """Predefined extraction JSON returning two facts (matches test_fact_extraction.py)."""
    return {
        "facts": [
            {
                "assertion": "Client was injured on January 15, 2026",
                "fact_type": "event",
                "entities": [
                    {
                        "entity_type": "person",
                        "value": "Client",
                        "confidence": 0.95,
                        "source_start": 0,
                        "source_end": 6,
                    },
                    {
                        "entity_type": "date",
                        "value": "January 15, 2026",
                        "confidence": 0.9,
                        "source_start": 20,
                        "source_end": 36,
                    },
                ],
                "confidence": 0.92,
                "source_start": 0,
                "source_end": 36,
            },
            {
                "assertion": "Injury occurred at the grocery store",
                "fact_type": "event",
                "entities": [
                    {
                        "entity_type": "location",
                        "value": "grocery store",
                        "confidence": 0.88,
                        "source_start": 40,
                        "source_end": 53,
                    },
                ],
                "confidence": 0.85,
                "source_start": 37,
                "source_end": 53,
            },
        ],
        "entities": [],
    }


def _mock_llm_service():
    """Create a mock LLMService with a valid client config."""
    mock = MagicMock()
    mock.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }
    return mock


# ---- Tests ----


@pytest.mark.asyncio
async def test_backfill_creates_facts(db_session, intake_scaffold):
    """Backfill extracts + persists facts for consumer messages, returning >0."""
    svc = IntakeSessionService(db_session)
    session_id = intake_scaffold["session"].id
    party_id = intake_scaffold["party"].id
    intake_id = intake_scaffold["intake"].id

    msg1 = await svc.store_message(
        session_id=session_id,
        sender_type="consumer",
        modality="text",
        content="I was injured on January 15, 2026 at the grocery store.",
        party_id=party_id,
    )
    msg2 = await svc.store_message(
        session_id=session_id,
        sender_type="consumer",
        modality="text",
        content="The store had a wet floor with no warning sign.",
        party_id=party_id,
    )

    mock_llm = _mock_llm_service()
    with patch.object(
        FactExtractionService,
        "_call_llm_extraction",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _extraction_json()
        created = await backfill_intake_facts(
            db_session, intake_id, mock_llm, folio=None, embedding_service=None
        )

    # Backfill created facts (exact count can vary if cross-message
    # supersession/dedup collapses identical assertions).
    assert created > 0

    rows = (
        await db_session.execute(
            select(ExtractedFact).where(ExtractedFact.intake_id == intake_id)
        )
    ).scalars().all()
    assert len(rows) == created
    linked_message_ids = {r.message_id for r in rows}
    assert linked_message_ids == {msg1.id, msg2.id}


@pytest.mark.asyncio
async def test_backfill_idempotent(db_session, intake_scaffold):
    """Running backfill twice does not create duplicate facts on the second run."""
    svc = IntakeSessionService(db_session)
    intake_id = intake_scaffold["intake"].id

    await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="consumer",
        modality="text",
        content="I was injured on January 15, 2026 at the grocery store.",
        party_id=intake_scaffold["party"].id,
    )

    mock_llm = _mock_llm_service()
    with patch.object(
        FactExtractionService,
        "_call_llm_extraction",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _extraction_json()
        first = await backfill_intake_facts(
            db_session, intake_id, mock_llm, folio=None, embedding_service=None
        )
        second = await backfill_intake_facts(
            db_session, intake_id, mock_llm, folio=None, embedding_service=None
        )

    assert first > 0
    assert second == 0

    rows = (
        await db_session.execute(
            select(ExtractedFact).where(ExtractedFact.intake_id == intake_id)
        )
    ).scalars().all()
    assert len(rows) == first


@pytest.mark.asyncio
async def test_backfill_skips_system_messages(db_session, intake_scaffold):
    """A system message is never sent through extraction."""
    svc = IntakeSessionService(db_session)
    intake_id = intake_scaffold["intake"].id

    await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="system",
        modality="text",
        content="Hello, how can I help you today?",
        party_id=None,
    )

    mock_llm = _mock_llm_service()
    with patch.object(
        FactExtractionService,
        "_call_llm_extraction",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _extraction_json()
        created = await backfill_intake_facts(
            db_session, intake_id, mock_llm, folio=None, embedding_service=None
        )

    assert created == 0
    mock_call.assert_not_called()

    rows = (
        await db_session.execute(
            select(ExtractedFact).where(ExtractedFact.intake_id == intake_id)
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_backfill_empty_intake(db_session, intake_scaffold):
    """An intake with a session but no messages returns 0."""
    mock_llm = _mock_llm_service()
    with patch.object(
        FactExtractionService,
        "_call_llm_extraction",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _extraction_json()
        created = await backfill_intake_facts(
            db_session,
            intake_scaffold["intake"].id,
            mock_llm,
            folio=None,
            embedding_service=None,
        )

    assert created == 0
    mock_call.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_uses_normalized_text_for_uploads(db_session, intake_scaffold):
    """BUG-27: for an uploaded document the body text lives in normalized_text
    while content_encrypted holds only the filename. Backfill must extract from
    the document body, not the filename (which yields zero facts)."""
    svc = IntakeSessionService(db_session)
    intake_id = intake_scaffold["intake"].id

    # Simulate an upload: content = filename; extracted body in normalized_text.
    msg = await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="consumer",
        modality="document",
        content="petition.pdf",
        party_id=intake_scaffold["party"].id,
    )
    body = "I was injured on January 15, 2026 at the grocery store with a wet floor."
    msg.normalized_text = body.encode("utf-8")
    await db_session.flush()

    mock_llm = _mock_llm_service()
    with patch.object(
        FactExtractionService,
        "_call_llm_extraction",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _extraction_json()
        created = await backfill_intake_facts(
            db_session, intake_id, mock_llm, folio=None, embedding_service=None
        )

    # The LLM must have been fed the document BODY, not the filename.
    assert mock_call.await_count == 1
    fed_text = mock_call.await_args.args[0] if mock_call.await_args.args else \
        mock_call.await_args.kwargs.get("text", "")
    assert "grocery store" in fed_text
    assert "petition.pdf" not in fed_text
    assert created > 0
