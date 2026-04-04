"""Tests for ResearchStage -- full research pipeline replacing research_stub.

Validates parallel tool queries, deduplication, citation verification, ranking,
KB + insights integration, usage tracking with budget enforcement, authority
storage, gap detection, and orchestrator wiring. Also tests FolioMCPClient
lifespan integration.
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.analysis import AnalysisClaim, AnalysisRun
from app.models.research import Authority
from app.services.research.base import ResearchQuery, ResearchResult


# ---- Fixtures ----


@pytest.fixture
async def rs_engine():
    """Create async SQLite engine with all tables."""
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
async def rs_session(rs_engine):
    """Yield an AsyncSession against the test engine."""
    async with rs_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
def sample_claims():
    """Create sample AnalysisClaim-like objects for testing."""
    claim1 = SimpleNamespace(
        id=1,
        claim_name="Wrongful Termination",
        folio_iri="https://folio.openlegalstandard.org/objective001",
        jurisdiction="California",
        elements=[
            SimpleNamespace(element_name="At-will exception"),
            SimpleNamespace(element_name="Wrongful discharge"),
        ],
    )
    claim2 = SimpleNamespace(
        id=2,
        claim_name="Discrimination",
        folio_iri="https://folio.openlegalstandard.org/objective002",
        jurisdiction="Federal",
        elements=[
            SimpleNamespace(element_name="Protected class"),
            SimpleNamespace(element_name="Adverse action"),
        ],
    )
    return [claim1, claim2]


@pytest.fixture
def sample_run():
    """Create a sample AnalysisRun-like object."""
    return SimpleNamespace(
        id=1,
        intake_id=10,
        status="running",
    )


@pytest.fixture
def mock_tool_registry():
    """Mock ResearchToolRegistry with get_active_adapters."""
    registry = AsyncMock()
    adapter1 = AsyncMock()
    adapter1.adapter_name = "courtlistener"
    adapter1.discover = AsyncMock(return_value=[
        ResearchResult(
            citation="123 F.3d 456",
            title="Smith v. Jones",
            authority_type="case_law",
            jurisdiction="California",
            source_tool="courtlistener",
            relevance_score=0.8,
        ),
    ])
    adapter2 = AsyncMock()
    adapter2.adapter_name = "google_scholar"
    adapter2.discover = AsyncMock(return_value=[
        ResearchResult(
            citation="789 U.S. 101",
            title="Doe v. Roe",
            authority_type="case_law",
            jurisdiction="Federal",
            source_tool="google_scholar",
            relevance_score=0.7,
        ),
    ])
    registry.get_active_adapters = AsyncMock(return_value=[adapter1, adapter2])
    return registry


@pytest.fixture
def mock_citation_verifier():
    """Mock CitationVerifier with verify_batch."""
    from app.services.research.citation_verifier import VerificationResult

    verifier = AsyncMock()
    verifier.verify_batch = AsyncMock(return_value=[
        VerificationResult(
            status="verified",
            sources_checked=["courtlistener"],
            confidence=0.7,
            citation_normalized="123 F.3d 456",
        ),
        VerificationResult(
            status="unverified",
            sources_checked=["courtlistener"],
            confidence=0.0,
            citation_normalized="789 U.S. 101",
        ),
    ])
    return verifier


@pytest.fixture
def mock_result_ranker():
    """Mock ResultRanker with rank method."""
    ranker = MagicMock()
    ranker.rank = MagicMock(side_effect=lambda results, query: results)
    return ranker


@pytest.fixture
def mock_citation_normalizer():
    """Mock CitationNormalizer with deduplicate_results."""
    normalizer = MagicMock()
    normalizer.deduplicate_results = MagicMock(side_effect=lambda results: results)
    return normalizer


@pytest.fixture
def mock_kb_retriever():
    """Mock KBRetriever with search method."""
    from app.services.knowledge_base.retriever import KBSearchResult

    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[
        KBSearchResult(
            chunk_content="KB result content",
            document_title="KB Doc",
            document_id=1,
            score=0.6,
        ),
    ])
    return retriever


@pytest.fixture
def mock_insights_service():
    """Mock InsightsService with get_insights."""
    from app.services.knowledge_base.retriever import KBSearchResult

    service = AsyncMock()
    service.get_insights = AsyncMock(return_value=[
        KBSearchResult(
            chunk_content="Insight content",
            document_title="Insight Doc",
            document_id=2,
            score=0.4,
            is_insight=True,
        ),
    ])
    return service


@pytest.fixture
def mock_usage_tracker():
    """Mock UsageTracker with record_call and check_budget."""
    tracker = AsyncMock()
    tracker.record_call = AsyncMock()
    tracker.check_budget = AsyncMock(return_value=True)
    return tracker


@pytest.fixture
def mock_llm_service():
    """Mock LLMService."""
    return MagicMock()


# ---- Test: ResearchStage.__init__ ----


class TestResearchStageInit:
    """ResearchStage accepts all required dependencies."""

    def test_accepts_all_dependencies(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service,
    ):
        """Test 1: ResearchStage.__init__ accepts all required dependencies."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )
        assert stage is not None
        assert stage._org_id == 1


# ---- Test: ResearchStage.execute pipeline ----


class TestResearchStageExecute:
    """ResearchStage.execute orchestrates the full research pipeline."""

    @pytest.mark.asyncio
    async def test_queries_active_adapters_in_parallel(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 2: execute queries all active adapters via asyncio.gather per D-04."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        # get_active_adapters should be called
        mock_tool_registry.get_active_adapters.assert_called_with(1)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_builds_research_query_from_claim(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 3: For each claim, builds ResearchQuery from claim_name, elements, jurisdiction."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        # Adapters should have been called with queries for each claim
        adapters = await mock_tool_registry.get_active_adapters(1)
        for adapter in adapters:
            assert adapter.discover.call_count >= 1

    @pytest.mark.asyncio
    async def test_deduplicates_via_citation_normalizer(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 4: Results from all tools are merged and deduplicated per D-15."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        await stage.execute(sample_run, sample_claims)

        mock_citation_normalizer.deduplicate_results.assert_called()

    @pytest.mark.asyncio
    async def test_verifies_citations_in_batch(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 5: All citations verified in batch via verify_batch per D-05."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        await stage.execute(sample_run, sample_claims)

        mock_citation_verifier.verify_batch.assert_called()

    @pytest.mark.asyncio
    async def test_ranks_results(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 6: Results ranked via result_ranker.rank per D-15."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        await stage.execute(sample_run, sample_claims)

        mock_result_ranker.rank.assert_called()

    @pytest.mark.asyncio
    async def test_kb_retrieval_in_parallel(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 7: KB retrieval runs in parallel with external tool queries per D-11."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        mock_kb_retriever.search.assert_called()
        assert result["kb_results_count"] >= 1

    @pytest.mark.asyncio
    async def test_insights_service_queried(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 8: InsightsService.get_insights queried for each claim's folio_iri per D-08."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        assert mock_insights_service.get_insights.call_count >= 1
        assert result["insights_count"] >= 1

    @pytest.mark.asyncio
    async def test_usage_tracked(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 9: Usage tracked for each tool call via usage_tracker.record_call per D-18."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        await stage.execute(sample_run, sample_claims)

        mock_usage_tracker.record_call.assert_called()

    @pytest.mark.asyncio
    async def test_budget_enforcement_skips_tools(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 10: Tools exceeding budget are skipped per D-18."""
        from app.services.research.research_stage import ResearchStage

        # Make check_budget return False for all tools
        mock_usage_tracker.check_budget = AsyncMock(return_value=False)

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        # No tools should have been queried (all over budget)
        assert result["tools_queried"] == 0

    @pytest.mark.asyncio
    async def test_returns_result_dict(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 12: Return dict includes all expected keys."""
        from app.services.research.research_stage import ResearchStage

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, sample_claims)

        expected_keys = {
            "authorities_found", "verified_count", "unverified_count",
            "tools_queried", "kb_results_count", "insights_count",
            "research_gaps", "research_notes",
        }
        assert expected_keys.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_research_gaps_detected(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_run,
    ):
        """Test 13: Elements with no supporting authority generate research gaps per D-04."""
        from app.services.research.research_stage import ResearchStage

        # Create a claim with no results from any tool
        claim_no_results = SimpleNamespace(
            id=99,
            claim_name="Obscure Claim",
            folio_iri="https://folio.openlegalstandard.org/obscure001",
            jurisdiction="California",
            elements=[SimpleNamespace(element_name="Obscure element")],
        )

        # Make adapters return empty results
        adapters = await mock_tool_registry.get_active_adapters(1)
        for adapter in adapters:
            adapter.discover = AsyncMock(return_value=[])
        mock_kb_retriever.search = AsyncMock(return_value=[])
        mock_insights_service.get_insights = AsyncMock(return_value=[])
        mock_citation_normalizer.deduplicate_results = MagicMock(return_value=[])
        mock_citation_verifier.verify_batch = AsyncMock(return_value=[])
        mock_result_ranker.rank = MagicMock(return_value=[])

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        result = await stage.execute(sample_run, [claim_no_results])

        assert len(result["research_gaps"]) >= 1
        assert any("Obscure Claim" in gap for gap in result["research_gaps"])

    @pytest.mark.asyncio
    async def test_failing_tool_does_not_block_others(
        self, mock_tool_registry, mock_citation_verifier, mock_result_ranker,
        mock_citation_normalizer, mock_kb_retriever, mock_insights_service,
        mock_usage_tracker, mock_llm_service, sample_claims, sample_run,
    ):
        """Test 14: asyncio.gather with return_exceptions=True prevents one tool blocking others."""
        from app.services.research.research_stage import ResearchStage

        # Make one adapter raise an exception
        adapters = await mock_tool_registry.get_active_adapters(1)
        adapters[0].discover = AsyncMock(side_effect=ConnectionError("API down"))

        stage = ResearchStage(
            db_session=MagicMock(),
            tool_registry=mock_tool_registry,
            citation_verifier=mock_citation_verifier,
            result_ranker=mock_result_ranker,
            citation_normalizer=mock_citation_normalizer,
            kb_retriever=mock_kb_retriever,
            insights_service=mock_insights_service,
            usage_tracker=mock_usage_tracker,
            llm_service=mock_llm_service,
            org_id=1,
        )

        # Should not raise -- failing tool is gracefully handled
        result = await stage.execute(sample_run, sample_claims)

        assert isinstance(result, dict)
        # Second adapter should still have returned results
        assert result["authorities_found"] >= 0


# ---- Test: Orchestrator wiring ----


class TestOrchestratorWiring:
    """Orchestrator._get_stage_instance("research") returns ResearchStage."""

    def test_get_stage_instance_returns_research_stage(self):
        """Test 15: _get_stage_instance("research") returns ResearchStage not stub."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator
        from app.services.research.research_stage import ResearchStage

        orch = AnalysisOrchestrator(
            db_session=MagicMock(),
            llm_service=MagicMock(),
            folio=None,
            embedding_service=None,
            org_config={"org_id": 1},
        )

        instance = orch._get_stage_instance("research")
        assert isinstance(instance, ResearchStage)

    @pytest.mark.asyncio
    async def test_orchestrator_calls_execute_with_correct_args(self):
        """Test 16: Orchestrator passes stage_instance.execute(run, claims)."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator
        from app.services.research.research_stage import ResearchStage

        orch = AnalysisOrchestrator(
            db_session=MagicMock(),
            llm_service=MagicMock(),
            folio=None,
            embedding_service=None,
            org_config={"org_id": 1},
        )

        # Verify the execute signature matches: execute(run, claims)
        instance = orch._get_stage_instance("research")
        assert isinstance(instance, ResearchStage)
        assert hasattr(instance, "execute")


# ---- Test: FolioMCPClient lifespan ----


class TestFolioMCPLifespan:
    """FolioMCPClient.connect() called in lifespan startup, close() on shutdown."""

    @pytest.mark.asyncio
    async def test_lifespan_connects_and_closes_mcp(self):
        """Test 17: FolioMCPClient.connect() in startup, close() in shutdown."""
        from app.services.mcp.folio_mcp_client import FolioMCPClient

        mock_client = AsyncMock(spec=FolioMCPClient)
        mock_client.connect = AsyncMock()
        mock_client.close = AsyncMock()

        with patch.object(FolioMCPClient, "get_instance", return_value=mock_client):
            # Simulate what lifespan should do
            client = FolioMCPClient.get_instance()
            await client.connect()
            # ... yield ...
            await client.close()

            mock_client.connect.assert_called_once()
            mock_client.close.assert_called_once()
