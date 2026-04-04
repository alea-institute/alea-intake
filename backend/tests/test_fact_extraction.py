"""Tests for fact extraction service and schemas.

Validates LLM-driven fact extraction with Pydantic structured output,
ConceptResolver wiring, source span validation, fact supersession,
and graceful degradation when services are unavailable.
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Set required env var for Settings
os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.fact import ExtractedFact, FactSourceSpan
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.services.extraction.schemas import (
    ExtractedEntitySchema,
    ExtractedFactSchema,
    ExtractionResultSchema,
)


# ---- Schema validation tests ----


def test_extracted_entity_schema_valid():
    """ExtractedEntitySchema validates correct fields."""
    entity = ExtractedEntitySchema(
        entity_type="person",
        value="John Smith",
        confidence=0.95,
        source_start=0,
        source_end=10,
    )
    assert entity.entity_type == "person"
    assert entity.confidence == 0.95


def test_extracted_entity_schema_confidence_bounds():
    """Confidence outside 0-1 range should fail validation."""
    with pytest.raises(ValidationError):
        ExtractedEntitySchema(
            entity_type="date",
            value="2026-01-15",
            confidence=1.5,
            source_start=0,
            source_end=10,
        )
    with pytest.raises(ValidationError):
        ExtractedEntitySchema(
            entity_type="date",
            value="2026-01-15",
            confidence=-0.1,
            source_start=0,
            source_end=10,
        )


def test_extracted_fact_schema_valid():
    """ExtractedFactSchema validates with entities."""
    fact = ExtractedFactSchema(
        assertion="John Smith was injured on January 15, 2026",
        fact_type="event",
        entities=[
            ExtractedEntitySchema(
                entity_type="person",
                value="John Smith",
                confidence=0.95,
                source_start=0,
                source_end=10,
            ),
            ExtractedEntitySchema(
                entity_type="date",
                value="January 15, 2026",
                confidence=0.9,
                source_start=30,
                source_end=46,
            ),
        ],
        confidence=0.92,
        source_start=0,
        source_end=46,
    )
    assert fact.fact_type == "event"
    assert len(fact.entities) == 2


def test_extraction_result_schema_empty():
    """ExtractionResultSchema with empty facts list."""
    result = ExtractionResultSchema(facts=[], entities=[])
    assert result.facts == []
    assert result.entities == []


def test_extraction_result_schema_full():
    """ExtractionResultSchema validates with facts and entities."""
    result = ExtractionResultSchema(
        facts=[
            ExtractedFactSchema(
                assertion="Client was injured",
                fact_type="event",
                confidence=0.9,
                source_start=0,
                source_end=19,
            )
        ],
        entities=[
            ExtractedEntitySchema(
                entity_type="person",
                value="Client",
                confidence=0.95,
                source_start=0,
                source_end=6,
            )
        ],
    )
    assert len(result.facts) == 1
    assert len(result.entities) == 1


# ---- FactExtractionService tests ----


@pytest.fixture
async def test_engine():
    """Create a test DB engine."""
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
async def intake_fixture(db_session):
    """Create a minimal intake with session and message for testing."""
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

    msg = Message(
        session_id=intake_session.id,
        sender_type="consumer",
        modality="text",
        content_encrypted=b"I was injured on January 15, 2026 at the grocery store.",
        sequence_number=1,
        party_id=party.id,
    )
    db_session.add(msg)
    await db_session.flush()

    return {
        "intake": intake,
        "party": party,
        "session": intake_session,
        "message": msg,
    }


def _mock_llm_service(extraction_json: dict | None = None):
    """Create a mock LLMService that returns predefined extraction JSON."""
    mock = MagicMock()

    if extraction_json is None:
        extraction_json = {
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
            "entities": [
                {
                    "entity_type": "person",
                    "value": "Client",
                    "confidence": 0.95,
                    "source_start": 0,
                    "source_end": 6,
                },
            ],
        }

    mock.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }

    return mock, extraction_json


@pytest.mark.asyncio
async def test_extract_facts_calls_llm(db_session):
    """FactExtractionService.extract_facts calls LLMService and returns ExtractionResultSchema."""
    from app.services.extraction.fact_extraction import FactExtractionService

    mock_llm, extraction_json = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    text = "I was injured on January 15, 2026 at the grocery store."

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = extraction_json
        result = await service.extract_facts(text)

    assert isinstance(result, ExtractionResultSchema)
    assert len(result.facts) == 2
    assert result.facts[0].assertion == "Client was injured on January 15, 2026"
    assert result.facts[0].fact_type == "event"


@pytest.mark.asyncio
async def test_extract_facts_malformed_llm_output(db_session):
    """Malformed LLM output returns empty ExtractionResultSchema."""
    from app.services.extraction.fact_extraction import FactExtractionService

    mock_llm, _ = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = {"invalid": "data"}
        result = await service.extract_facts("Some text")

    assert isinstance(result, ExtractionResultSchema)
    assert len(result.facts) == 0


@pytest.mark.asyncio
async def test_extract_facts_empty_text(db_session):
    """Empty or minimal text returns empty facts list."""
    from app.services.extraction.fact_extraction import FactExtractionService

    mock_llm, _ = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = {"facts": [], "entities": []}
        result = await service.extract_facts("")

    assert isinstance(result, ExtractionResultSchema)
    assert len(result.facts) == 0


@pytest.mark.asyncio
async def test_extract_and_persist(db_session, intake_fixture):
    """extract_and_persist stores ExtractedFact and FactSourceSpan in DB."""
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.intake.message_pipeline import NormalizedContent, SourceSpan

    mock_llm, extraction_json = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    normalized = NormalizedContent(
        text="I was injured on January 15, 2026 at the grocery store.",
        source_type="chat",
        source_id=str(intake_fixture["message"].id),
        source_spans=[SourceSpan(start_char=0, end_char=55)],
    )

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = extraction_json
        facts = await service.extract_and_persist(
            normalized=normalized,
            intake_id=intake_fixture["intake"].id,
            message_id=intake_fixture["message"].id,
            party_id=intake_fixture["party"].id,
        )

    assert len(facts) == 2

    # Verify DB records
    result = await db_session.execute(
        select(ExtractedFact).where(
            ExtractedFact.intake_id == intake_fixture["intake"].id
        )
    )
    db_facts = result.scalars().all()
    assert len(db_facts) == 2
    assert db_facts[0].assertion_text == "Client was injured on January 15, 2026"
    assert db_facts[0].fact_type == "event"
    assert db_facts[0].confidence == 0.92
    assert db_facts[0].is_active is True

    # Verify source spans
    span_result = await db_session.execute(select(FactSourceSpan))
    spans = span_result.scalars().all()
    assert len(spans) == 2
    assert spans[0].start_char == 0
    assert spans[0].end_char == 36


@pytest.mark.asyncio
async def test_extract_and_persist_with_concept_resolution(db_session, intake_fixture):
    """extract_and_persist calls resolve_concepts and stores IRIs in metadata_json."""
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.folio.concept_resolver import ResolvedConcept
    from app.services.intake.message_pipeline import NormalizedContent, SourceSpan

    mock_llm, extraction_json = _mock_llm_service()
    mock_folio = MagicMock()
    mock_embedding = MagicMock()

    mock_resolved = [
        ResolvedConcept(
            iri="http://folio/objective/123",
            label="Negligence",
            branch="Objectives",
            confidence=0.85,
            source="combined",
            matched_text="Client was injured",
        )
    ]

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
        folio=mock_folio,
        embedding_service=mock_embedding,
    )

    normalized = NormalizedContent(
        text="I was injured on January 15, 2026 at the grocery store.",
        source_type="chat",
        source_id=str(intake_fixture["message"].id),
        source_spans=[SourceSpan(start_char=0, end_char=55)],
    )

    with (
        patch.object(
            service, "_call_llm_extraction", new_callable=AsyncMock
        ) as mock_call,
        patch(
            "app.services.extraction.fact_extraction.resolve_concepts",
            new_callable=AsyncMock,
        ) as mock_resolve,
    ):
        mock_call.return_value = extraction_json
        mock_resolve.return_value = mock_resolved
        facts = await service.extract_and_persist(
            normalized=normalized,
            intake_id=intake_fixture["intake"].id,
            message_id=intake_fixture["message"].id,
            party_id=intake_fixture["party"].id,
        )

    assert len(facts) == 2

    # Verify resolved concepts in metadata
    result = await db_session.execute(
        select(ExtractedFact).where(
            ExtractedFact.intake_id == intake_fixture["intake"].id
        )
    )
    db_facts = result.scalars().all()
    for fact in db_facts:
        assert "resolved_concepts" in fact.metadata_json
        assert len(fact.metadata_json["resolved_concepts"]) > 0
        assert fact.metadata_json["resolved_concepts"][0]["iri"] == "http://folio/objective/123"


@pytest.mark.asyncio
async def test_extract_and_persist_no_folio(db_session, intake_fixture):
    """extract_and_persist with folio=None gracefully skips concept resolution."""
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.intake.message_pipeline import NormalizedContent, SourceSpan

    mock_llm, extraction_json = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
        folio=None,
        embedding_service=None,
    )

    normalized = NormalizedContent(
        text="I was injured on January 15, 2026 at the grocery store.",
        source_type="chat",
        source_id=str(intake_fixture["message"].id),
        source_spans=[SourceSpan(start_char=0, end_char=55)],
    )

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = extraction_json
        facts = await service.extract_and_persist(
            normalized=normalized,
            intake_id=intake_fixture["intake"].id,
            message_id=intake_fixture["message"].id,
        )

    assert len(facts) == 2

    result = await db_session.execute(
        select(ExtractedFact).where(
            ExtractedFact.intake_id == intake_fixture["intake"].id
        )
    )
    db_facts = result.scalars().all()
    for fact in db_facts:
        assert fact.metadata_json["resolved_concepts"] == []


@pytest.mark.asyncio
async def test_source_span_validation(db_session, intake_fixture):
    """Facts with source_start > len(text) are dropped."""
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.intake.message_pipeline import NormalizedContent, SourceSpan

    mock_llm, _ = _mock_llm_service()

    # Create extraction with out-of-bounds spans
    bad_extraction = {
        "facts": [
            {
                "assertion": "Valid fact",
                "fact_type": "event",
                "entities": [],
                "confidence": 0.9,
                "source_start": 0,
                "source_end": 10,
            },
            {
                "assertion": "Invalid fact with bad span",
                "fact_type": "event",
                "entities": [],
                "confidence": 0.8,
                "source_start": 500,  # Way out of bounds
                "source_end": 600,
            },
        ],
        "entities": [],
    }

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    short_text = "Short text."

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = bad_extraction
        result = await service.extract_facts(short_text)

    # Only the valid fact should remain
    assert len(result.facts) == 1
    assert result.facts[0].assertion == "Valid fact"


def test_extraction_system_prompt_entity_types():
    """EXTRACTION_SYSTEM_PROMPT contains all 10 required entity types."""
    from app.services.extraction.fact_extraction import EXTRACTION_SYSTEM_PROMPT

    required_types = [
        "person",
        "date",
        "location",
        "amount",
        "organization",
        "party_relationship",
        "legal_event",
        "document_reference",
        "time_period",
        "claimed_damages",
    ]
    for entity_type in required_types:
        assert entity_type in EXTRACTION_SYSTEM_PROMPT, (
            f"Entity type '{entity_type}' missing from EXTRACTION_SYSTEM_PROMPT"
        )


@pytest.mark.asyncio
async def test_fact_supersession(db_session, intake_fixture):
    """When extract_and_persist detects conflicting fact, old fact becomes inactive."""
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.intake.message_pipeline import NormalizedContent, SourceSpan

    mock_llm, _ = _mock_llm_service()

    service = FactExtractionService(
        llm_service=mock_llm,
        db_session=db_session,
    )

    # Create an initial fact manually
    old_fact = ExtractedFact(
        intake_id=intake_fixture["intake"].id,
        message_id=intake_fixture["message"].id,
        party_id=intake_fixture["party"].id,
        assertion_text="Client was injured on January 10, 2026",
        fact_type="event",
        entity_type="date",
        confidence=0.8,
        is_active=True,
        metadata_json={"entities": [{"entity_type": "date", "value": "January 10, 2026"}]},
    )
    db_session.add(old_fact)
    await db_session.flush()

    # Now extract a contradicting fact (same party, same type, overlapping entity)
    new_extraction = {
        "facts": [
            {
                "assertion": "Client was injured on January 15, 2026",
                "fact_type": "event",
                "entities": [
                    {
                        "entity_type": "date",
                        "value": "January 15, 2026",
                        "confidence": 0.95,
                        "source_start": 20,
                        "source_end": 36,
                    }
                ],
                "confidence": 0.95,
                "source_start": 0,
                "source_end": 36,
            }
        ],
        "entities": [],
    }

    normalized = NormalizedContent(
        text="I was injured on January 15, 2026 at the grocery store.",
        source_type="chat",
        source_id=str(intake_fixture["message"].id),
        source_spans=[SourceSpan(start_char=0, end_char=55)],
    )

    # Provide existing facts as session context
    session_facts = [
        {
            "id": old_fact.id,
            "assertion_text": old_fact.assertion_text,
            "fact_type": old_fact.fact_type,
            "entity_type": old_fact.entity_type,
            "confidence": old_fact.confidence,
            "party_id": old_fact.party_id,
            "metadata_json": old_fact.metadata_json,
        }
    ]

    with patch.object(
        service, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = new_extraction
        new_facts = await service.extract_and_persist(
            normalized=normalized,
            intake_id=intake_fixture["intake"].id,
            message_id=intake_fixture["message"].id,
            party_id=intake_fixture["party"].id,
            session_facts=session_facts,
        )

    assert len(new_facts) == 1

    # Verify old fact is superseded
    await db_session.refresh(old_fact)
    assert old_fact.is_active is False
    assert old_fact.superseded_by_id == new_facts[0].id
