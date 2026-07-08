"""Tests for analysis pipeline stages: issue-spotting, research stub, and fact-mapping.

Validates LLM-driven stage execution with mocked LLM, DB persistence,
ConceptResolver wiring, FOLIO adjacency, and composite confidence scoring.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Set required env var for Settings
os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.analysis import (
    AnalysisClaim,
    AnalysisIteration,
    AnalysisRun,
    AnalysisStage,
    ClaimElement,
    FactClaimMapping,
)
from app.models.fact import ExtractedFact
from app.models.intake import Intake, IntakeSession, Message
from app.services.analysis.stages.issue_spot import IssueSpotStage
from app.services.analysis.stages.research_stub import ResearchStubStage


# ---- Fixtures ----


@pytest.fixture
async def stage_engine():
    """Create async SQLite engine with all analysis tables."""
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
async def stage_session(stage_engine):
    """Yield an AsyncSession against the test engine."""
    async with stage_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def analysis_run(stage_session):
    """Create test AnalysisRun and AnalysisIteration."""
    run = AnalysisRun(
        intake_id=1,
        status="running",
        trigger_type="auto",
        current_iteration_number=1,
        max_iterations=10,
    )
    stage_session.add(run)
    await stage_session.flush()

    iteration = AnalysisIteration(
        run_id=run.id,
        iteration_number=1,
        status="running",
    )
    stage_session.add(iteration)
    await stage_session.flush()

    return run, iteration


@pytest.fixture
def sample_facts(stage_session):
    """Create sample ExtractedFact records for testing."""
    facts = [
        ExtractedFact(
            intake_id=1,
            message_id=1,
            assertion_text="John was fired from Acme Corp on January 15, 2026",
            fact_type="legal_event",
            confidence=0.9,
        ),
        ExtractedFact(
            intake_id=1,
            message_id=1,
            assertion_text="John had an employment contract with Acme Corp",
            fact_type="document_reference",
            confidence=0.85,
        ),
        ExtractedFact(
            intake_id=1,
            message_id=1,
            assertion_text="The termination occurred in California",
            fact_type="location",
            confidence=0.95,
        ),
    ]
    for f in facts:
        stage_session.add(f)
    return facts


@pytest.fixture
def mock_llm_service():
    """Create a mock LLMService that returns configurable responses."""
    service = MagicMock()
    service.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }
    return service


# ---- Issue-Spotting Stage Tests ----


@pytest.mark.asyncio
async def test_issue_spot_execute_returns_claims(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """IssueSpotStage.execute() with mocked LLM returns IssueSpotResult with claims and jurisdictions."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination",
                "claim_type": "identified",
                "folio_iri": None,
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "Facts indicate termination from employment",
                "is_potential": False,
                "elements": [
                    {"element_name": "Employment relationship", "element_description": "Employer-employee relationship existed"},
                    {"element_name": "Wrongful act", "element_description": "Termination violated law or public policy"},
                ],
            },
            {
                "claim_name": "Breach of Employment Contract",
                "claim_type": "discovered",
                "folio_iri": None,
                "jurisdiction": "California",
                "confidence": 0.7,
                "rationale": "Employment contract mentioned, potential breach",
                "is_potential": True,
                "elements": [
                    {"element_name": "Valid contract", "element_description": "Enforceable employment contract existed"},
                ],
            },
        ],
        "jurisdictions": ["California", "Federal"],
        "summary": "Wrongful termination and potential breach of contract in California",
    }

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
        folio=None,
        embedding_service=None,
    )

    # Mock the LLM call
    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts)

    assert result["claims_count"] == 2
    assert "California" in result["jurisdictions"]
    assert "Federal" in result["jurisdictions"]
    assert result["summary"] is not None


@pytest.mark.asyncio
async def test_issue_spot_persists_claims_to_db(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """Claims from LLM output are persisted as AnalysisClaim records in DB."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination",
                "claim_type": "identified",
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "Facts indicate termination",
                "is_potential": False,
                "elements": [],
            },
        ],
        "jurisdictions": ["California"],
        "summary": "Wrongful termination claim",
    }

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        await stage.execute(run, iteration, sample_facts)

    claims = (await stage_session.execute(select(AnalysisClaim))).scalars().all()
    assert len(claims) == 1
    assert claims[0].claim_name == "Wrongful Termination"
    assert claims[0].run_id == run.id
    assert claims[0].claim_type == "identified"
    assert claims[0].jurisdiction == "California"
    assert claims[0].confidence == 0.85


@pytest.mark.asyncio
async def test_issue_spot_discovered_claims_are_potential(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """Discovered claims (not in narrative) have is_potential=True and claim_type='discovered' (D-08)."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Discrimination",
                "claim_type": "discovered",
                "jurisdiction": "Federal",
                "confidence": 0.6,
                "rationale": "Pattern suggests possible discrimination",
                "is_potential": True,
                "elements": [],
            },
        ],
        "jurisdictions": ["Federal"],
        "summary": "Potential discrimination claim discovered",
    }

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        await stage.execute(run, iteration, sample_facts)

    claims = (await stage_session.execute(select(AnalysisClaim))).scalars().all()
    assert len(claims) == 1
    assert claims[0].is_potential is True
    assert claims[0].claim_type == "discovered"


@pytest.mark.asyncio
async def test_issue_spot_multiple_jurisdictions(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """Multiple jurisdictions detected in LLM output are returned for parallel analysis (D-06)."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination",
                "claim_type": "identified",
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "State claim",
                "is_potential": False,
                "elements": [],
            },
            {
                "claim_name": "Title VII Violation",
                "claim_type": "identified",
                "jurisdiction": "Federal",
                "confidence": 0.75,
                "rationale": "Federal claim",
                "is_potential": False,
                "elements": [],
            },
        ],
        "jurisdictions": ["California", "Federal", "Nevada"],
        "summary": "Multi-jurisdictional claims",
    }

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts)

    assert len(result["jurisdictions"]) == 3
    assert set(result["jurisdictions"]) == {"California", "Federal", "Nevada"}


@pytest.mark.asyncio
async def test_issue_spot_calls_concept_resolver(
    stage_session, analysis_run, sample_facts, mock_llm_service, mock_folio
):
    """ConceptResolver is called for each claim to resolve folio_iri."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination Claim",
                "claim_type": "identified",
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "Facts support this",
                "is_potential": False,
                "elements": [],
            },
        ],
        "jurisdictions": ["California"],
        "summary": "Wrongful termination claim identified",
    }

    # Mock embedding service
    mock_embedding = AsyncMock()

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
        folio=mock_folio,
        embedding_service=mock_embedding,
    )

    from types import SimpleNamespace

    resolved_concept = SimpleNamespace(
        iri="https://folio.openlegalstandard.org/objective001",
        label="Wrongful Termination",
        branch="Area of Law",
        confidence=0.9,
    )

    with (
        patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response),
        patch.object(
            stage, "_resolve_folio_concept",
            new_callable=AsyncMock,
            return_value=resolved_concept,
        ) as mock_resolve,
    ):
        await stage.execute(run, iteration, sample_facts)

    mock_resolve.assert_called_once_with("Wrongful Termination Claim")
    claims = (await stage_session.execute(select(AnalysisClaim))).scalars().all()
    # Fit branch ("Area of Law") -> mapping survives semantic-fit validation.
    assert claims[0].folio_iri == "https://folio.openlegalstandard.org/objective001"


@pytest.mark.asyncio
async def test_issue_spot_graceful_without_concept_resolver(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """If ConceptResolver unavailable, stage proceeds with folio_iri=None."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination",
                "claim_type": "identified",
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "Facts support this",
                "is_potential": False,
                "elements": [],
            },
        ],
        "jurisdictions": ["California"],
        "summary": "Claim identified",
    }

    # No folio, no embedding_service
    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
        folio=None,
        embedding_service=None,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts)

    assert result["claims_count"] == 1
    claims = (await stage_session.execute(select(AnalysisClaim))).scalars().all()
    assert claims[0].folio_iri is None


@pytest.mark.asyncio
async def test_issue_spot_persists_elements(
    stage_session, analysis_run, sample_facts, mock_llm_service
):
    """Elements from spotted claims are persisted as ClaimElement records."""
    run, iteration = analysis_run
    await stage_session.flush()

    llm_response = {
        "claims": [
            {
                "claim_name": "Wrongful Termination",
                "claim_type": "identified",
                "jurisdiction": "California",
                "confidence": 0.85,
                "rationale": "Facts support this",
                "is_potential": False,
                "elements": [
                    {"element_name": "Employment relationship", "element_description": "Must prove employment existed"},
                    {"element_name": "Wrongful act", "element_description": "Termination violated law or policy"},
                ],
            },
        ],
        "jurisdictions": ["California"],
        "summary": "Claim with elements",
    }

    stage = IssueSpotStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        await stage.execute(run, iteration, sample_facts)

    elements = (await stage_session.execute(select(ClaimElement))).scalars().all()
    assert len(elements) == 2
    element_names = {e.element_name for e in elements}
    assert "Employment relationship" in element_names
    assert "Wrongful act" in element_names


# ---- Research Stub Stage Tests ----


@pytest.mark.asyncio
async def test_research_stub_returns_elements_from_folio(
    stage_session, analysis_run, mock_folio
):
    """ResearchStubStage.execute() returns element list from FOLIO adjacency."""
    run, _ = analysis_run

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        folio_iri="https://folio.openlegalstandard.org/objective001",
        jurisdiction="California",
        confidence=0.85,
        rationale="Test",
        iteration_discovered=1,
    )
    stage_session.add(claim)
    await stage_session.flush()

    stage = ResearchStubStage(
        db_session=stage_session,
        folio=mock_folio,
    )

    result = await stage.execute(run, [claim])

    assert result["elements_discovered"] >= 0
    assert "research_notes" in result


@pytest.mark.asyncio
async def test_research_stub_graceful_without_folio(
    stage_session, analysis_run
):
    """ResearchStubStage gracefully returns empty when FOLIO unavailable."""
    run, _ = analysis_run

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        folio_iri=None,
        jurisdiction="California",
        confidence=0.85,
        rationale="Test",
        iteration_discovered=1,
    )
    stage_session.add(claim)
    await stage_session.flush()

    stage = ResearchStubStage(
        db_session=stage_session,
        folio=None,
    )

    result = await stage.execute(run, [claim])

    assert result["elements_discovered"] == 0
    assert "deferred" in result["research_notes"].lower() or "unavailable" in result["research_notes"].lower()


# ---- Fact-Mapping Stage Tests ----


from app.services.analysis.stages.fact_map import FactMapStage
from app.services.analysis.schemas import ConfidenceWeights


@pytest.fixture
async def claims_with_elements(stage_session, analysis_run):
    """Create AnalysisClaim records with ClaimElement children for fact-mapping tests."""
    run, iteration = analysis_run

    claim1 = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        folio_iri="https://folio.openlegalstandard.org/objective001",
        jurisdiction="California",
        confidence=0.85,
        rationale="Facts indicate termination from employment",
        iteration_discovered=1,
    )
    stage_session.add(claim1)
    await stage_session.flush()

    elem1 = ClaimElement(
        claim_id=claim1.id,
        element_name="Employment relationship",
        element_description="Must prove employment existed",
        jurisdiction="California",
    )
    elem2 = ClaimElement(
        claim_id=claim1.id,
        element_name="Wrongful act",
        element_description="Termination violated law or policy",
        jurisdiction="California",
    )
    stage_session.add(elem1)
    stage_session.add(elem2)

    claim2 = AnalysisClaim(
        run_id=run.id,
        claim_name="Breach of Contract",
        claim_type="discovered",
        folio_iri="https://folio.openlegalstandard.org/objective002",
        jurisdiction="California",
        confidence=0.7,
        rationale="Employment contract mentioned",
        is_potential=True,
        iteration_discovered=1,
    )
    stage_session.add(claim2)
    await stage_session.flush()

    elem3 = ClaimElement(
        claim_id=claim2.id,
        element_name="Valid contract",
        element_description="Enforceable employment contract existed",
        jurisdiction="California",
    )
    stage_session.add(elem3)
    await stage_session.flush()

    return [claim1, claim2], [elem1, elem2, elem3]


@pytest.mark.asyncio
async def test_fact_map_creates_mappings(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """FactMapStage.execute() with mocked LLM creates FactClaimMapping records."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Firing event directly supports wrongful act element",
            },
            {
                "fact_id": sample_facts[1].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Employment relationship",
                "llm_confidence": 0.85,
                "mapping_rationale": "Contract proves employment existed",
            },
        ],
        "unmapped_facts": [sample_facts[2].id],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts, claims)

    assert result["mappings_created"] == 2
    mappings = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    assert len(mappings) == 2


@pytest.mark.asyncio
async def test_fact_map_composite_confidence(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """Each mapping has composite confidence from compute_composite_confidence (D-05)."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Direct support",
            },
        ],
        "unmapped_facts": [],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts, claims)

    mappings = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    assert len(mappings) == 1
    m = mappings[0]
    # Composite confidence should be calculated from the three signals
    assert m.confidence > 0
    assert m.llm_confidence == 0.9
    assert m.fact_confidence == sample_facts[0].confidence  # 0.9
    assert m.concept_confidence is not None


@pytest.mark.asyncio
async def test_fact_map_many_to_many(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """Mappings are many-to-many: one fact can map to multiple claims/elements."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    # Same fact maps to two different claims
    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[1].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Employment relationship",
                "llm_confidence": 0.85,
                "mapping_rationale": "Contract proves employment",
            },
            {
                "fact_id": sample_facts[1].id,
                "claim_name": "Breach of Contract",
                "element_name": "Valid contract",
                "llm_confidence": 0.8,
                "mapping_rationale": "Same contract is the breached agreement",
            },
        ],
        "unmapped_facts": [],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts, claims)

    assert result["mappings_created"] == 2
    mappings = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    # Both mappings should reference the same fact_id
    fact_ids = [m.fact_id for m in mappings]
    assert fact_ids.count(sample_facts[1].id) == 2


@pytest.mark.asyncio
async def test_fact_map_tracks_unmapped_facts(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """Unmapped facts (no claim match) are tracked in result."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Direct support",
            },
        ],
        "unmapped_facts": [sample_facts[1].id, sample_facts[2].id],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await stage.execute(run, iteration, sample_facts, claims)

    assert len(result["unmapped_facts"]) == 2
    assert sample_facts[1].id in result["unmapped_facts"]
    assert sample_facts[2].id in result["unmapped_facts"]


@pytest.mark.asyncio
async def test_fact_map_custom_confidence_weights(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """Custom ConfidenceWeights change the composite score."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Direct support",
            },
        ],
        "unmapped_facts": [],
    }

    # Custom weights heavily favoring LLM confidence
    custom_weights = ConfidenceWeights(llm_weight=0.8, concept_weight=0.1, fact_weight=0.1)

    stage_default = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage_default, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result_default = await stage_default.execute(run, iteration, sample_facts, claims)

    # Get the default confidence
    mappings_default = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    default_confidence = mappings_default[0].confidence

    # Clean up for next run
    for m in mappings_default:
        await stage_session.delete(m)
    await stage_session.flush()

    stage_custom = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
        confidence_weights=custom_weights,
    )

    with patch.object(stage_custom, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result_custom = await stage_custom.execute(run, iteration, sample_facts, claims)

    mappings_custom = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    custom_confidence = mappings_custom[0].confidence

    # Custom weights should produce a different score
    assert custom_confidence != default_confidence


@pytest.mark.asyncio
async def test_fact_map_persists_rationale(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """mapping_rationale is persisted from LLM output."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Firing event directly supports the wrongful termination element",
            },
        ],
        "unmapped_facts": [],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        await stage.execute(run, iteration, sample_facts, claims)

    mappings = (await stage_session.execute(select(FactClaimMapping))).scalars().all()
    assert mappings[0].mapping_rationale == "Firing event directly supports the wrongful termination element"


@pytest.mark.asyncio
async def test_fact_map_updates_element_satisfaction(
    stage_session, analysis_run, sample_facts, claims_with_elements, mock_llm_service
):
    """ClaimElement.is_satisfied is updated when mapping confidence > 0.5."""
    run, iteration = analysis_run
    claims, elements = claims_with_elements
    await stage_session.flush()

    llm_response = {
        "mappings": [
            {
                "fact_id": sample_facts[0].id,
                "claim_name": "Wrongful Termination",
                "element_name": "Wrongful act",
                "llm_confidence": 0.9,
                "mapping_rationale": "Strong support",
            },
        ],
        "unmapped_facts": [],
    }

    stage = FactMapStage(
        llm_service=mock_llm_service,
        db_session=stage_session,
    )

    with patch.object(stage, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        await stage.execute(run, iteration, sample_facts, claims)

    # Check that the "Wrongful act" element is now satisfied
    all_elements = (await stage_session.execute(select(ClaimElement))).scalars().all()
    wrongful_act = [e for e in all_elements if e.element_name == "Wrongful act"][0]
    assert wrongful_act.is_satisfied is True
    assert wrongful_act.satisfaction_confidence is not None
    assert wrongful_act.satisfaction_confidence > 0.5
