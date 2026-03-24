"""Tests for unmapped concept handling: local IRI generation, nearest concepts, and persistence.

Validates that concepts not found in FOLIO get structured records with
folio-python generate_iri() IRIs, computed unmapped confidence, up to 3
nearest FOLIO concepts, and optional LLM-suggested branch.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folio_concepts import UnmappedConceptRecord


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_match(iri: str, label: str, confidence: float):
    """Create a mock low-confidence match object."""
    m = MagicMock()
    m.iri = iri
    m.label = label
    m.confidence = confidence
    return m


# ── Unit Tests ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_unmapped_generates_iri(mock_folio):
    """handle_unmapped_concept generates local IRI via FOLIO.generate_iri()."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/testABC123"
    )
    matches = [_make_match("iri1", "Label 1", 0.2)]

    result = await handle_unmapped_concept(
        text="quantum entanglement tort", folio=mock_folio, low_confidence_matches=matches
    )

    mock_folio.generate_iri.assert_called_once()
    assert result.local_iri == "https://folio.openlegalstandard.org/testABC123"


@pytest.mark.asyncio
async def test_handle_unmapped_includes_nearest_concepts(mock_folio):
    """handle_unmapped_concept returns top 3 nearest concepts by confidence."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/testXYZ"
    )
    matches = [
        _make_match("iri1", "Label 1", 0.1),
        _make_match("iri2", "Label 2", 0.4),
        _make_match("iri3", "Label 3", 0.3),
        _make_match("iri4", "Label 4", 0.2),
        _make_match("iri5", "Label 5", 0.05),
    ]

    result = await handle_unmapped_concept(
        text="alien abduction liability", folio=mock_folio, low_confidence_matches=matches
    )

    # Top 3 by confidence: iri2(0.4), iri3(0.3), iri4(0.2)
    assert len(result.nearest_concepts) == 3
    assert result.nearest_concepts[0]["iri"] == "iri2"
    assert result.nearest_concepts[0]["confidence"] == 0.4
    assert result.nearest_concepts[1]["iri"] == "iri3"
    assert result.nearest_concepts[2]["iri"] == "iri4"


@pytest.mark.asyncio
async def test_handle_unmapped_calculates_unmapped_confidence(mock_folio):
    """Unmapped confidence is 1 - (best_match / threshold)."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/testConf"
    )
    matches = [_make_match("iri1", "Label 1", 0.2)]

    result = await handle_unmapped_concept(
        text="mystery concept",
        folio=mock_folio,
        low_confidence_matches=matches,
        confidence_threshold=0.5,
    )

    # 1 - (0.2 / 0.5) = 0.6
    assert abs(result.unmapped_confidence - 0.6) < 0.01


@pytest.mark.asyncio
async def test_handle_unmapped_no_matches(mock_folio):
    """With no matches, unmapped_confidence should be 1.0."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/testEmpty"
    )

    result = await handle_unmapped_concept(
        text="completely unknown concept",
        folio=mock_folio,
        low_confidence_matches=[],
    )

    assert result.unmapped_confidence == 1.0
    assert result.nearest_concepts == []


@pytest.mark.asyncio
async def test_unmapped_data_fields(mock_folio):
    """UnmappedConceptData has all required fields."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/testFields"
    )
    matches = [_make_match("iri1", "Label 1", 0.3)]

    result = await handle_unmapped_concept(
        text="novel legal concept", folio=mock_folio, low_confidence_matches=matches
    )

    assert isinstance(result.local_iri, str)
    assert isinstance(result.original_text, str)
    assert result.suggested_branch is None  # No LLM provided
    assert isinstance(result.unmapped_confidence, float)
    assert isinstance(result.nearest_concepts, list)


@pytest.mark.asyncio
async def test_unmapped_local_iri_follows_folio_scheme(mock_folio):
    """Local IRI starts with FOLIO namespace."""
    from app.services.folio.unmapped import handle_unmapped_concept

    mock_folio.generate_iri = MagicMock(
        return_value="https://folio.openlegalstandard.org/abc123def"
    )

    result = await handle_unmapped_concept(
        text="test concept", folio=mock_folio, low_confidence_matches=[]
    )

    assert result.local_iri.startswith("https://folio.openlegalstandard.org/")


# ── Persistence Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_unmapped_creates_record(async_session: AsyncSession, test_org):
    """persist_unmapped creates UnmappedConceptRecord in the DB."""
    from app.services.folio.unmapped import UnmappedConceptData, persist_unmapped

    data = UnmappedConceptData(
        local_iri="https://folio.openlegalstandard.org/testPersist001",
        original_text="novel concept for persistence test",
        suggested_branch="Objectives",
        unmapped_confidence=0.8,
        nearest_concepts=[{"iri": "iri1", "label": "Label 1", "confidence": 0.2}],
    )

    record = await persist_unmapped(
        session=async_session, intake_id=1, org_id=test_org.id, unmapped=data
    )

    assert record.id is not None
    assert record.local_iri == data.local_iri
    assert record.original_text == data.original_text
    assert record.suggested_branch == "Objectives"
    assert record.unmapped_confidence == 0.8
    assert record.nearest_iris == data.nearest_concepts

    # Verify it persists in the DB
    result = await async_session.execute(
        select(UnmappedConceptRecord).where(UnmappedConceptRecord.local_iri == data.local_iri)
    )
    db_record = result.scalar_one()
    assert db_record.original_text == "novel concept for persistence test"
