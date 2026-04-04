"""Tests for the three-layer exploration engine: layers, deduplication, and multi-round stability.

Tests ExplorationEngine and the four layer functions (folio_adjacency, protocol_match,
cheap_llm, expensive_llm) with mocked FOLIO, LLM, and ProtocolService dependencies.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exploration.schemas import (
    ExplorationConfig,
    ExplorationResult,
    ExplorationRoundResult,
    ExplorationStageResult,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_claim(claim_name: str, folio_iri: str | None = None, claim_type: str = "identified") -> MagicMock:
    """Build a mock AnalysisClaim."""
    claim = MagicMock()
    claim.claim_name = claim_name
    claim.folio_iri = folio_iri
    claim.claim_type = claim_type
    claim.confidence = 0.8
    claim.is_potential = False
    return claim


def _make_fact(text: str) -> MagicMock:
    """Build a mock ExtractedFact."""
    fact = MagicMock()
    fact.assertion_text = text
    fact.fact_type = "event"
    fact.confidence = 0.9
    return fact


def _make_adjacency_result(concept_iri: str, label: str, depth: int = 1) -> dict:
    """Return the dict structure from discover_adjacent_concepts."""
    return {
        "nodes": [
            {"iri": concept_iri, "label": label, "branch": None, "is_unmapped": False, "depth": depth},
        ],
        "edges": [],
    }


@pytest.fixture
def mock_llm_service():
    """LLM service with async method simulation."""
    llm = MagicMock()
    llm.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }
    return llm


@pytest.fixture
def mock_embedding_service():
    svc = AsyncMock()
    svc.search = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def mock_protocol_service():
    svc = AsyncMock()
    svc.get_active_protocols = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def default_config():
    return ExplorationConfig(
        min_rounds=1,
        max_rounds=3,
        stability_threshold=0,
        exploration_confidence_threshold=0.4,
        question_transparency=True,
    )


@pytest.fixture
def sample_claims():
    return [
        _make_claim("Wrongful Termination", folio_iri="https://folio.openlegalstandard.org/objective001"),
        _make_claim("Breach of Contract", folio_iri="https://folio.openlegalstandard.org/objective002"),
    ]


@pytest.fixture
def sample_facts():
    return [
        _make_fact("I was fired from my job last month"),
        _make_fact("My employer did not pay my last paycheck"),
    ]


# ---------------------------------------------------------------------------
# ExplorationEngine multi-round tests
# ---------------------------------------------------------------------------


class TestExplorationEngineRounds:
    """Multi-round stability detection per D-06."""

    @pytest.mark.asyncio
    async def test_explore_runs_min_rounds_even_if_stable(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Engine runs min_rounds even when stable after round 1."""
        from app.services.exploration.engine import ExplorationEngine

        config = ExplorationConfig(min_rounds=2, max_rounds=5, stability_threshold=0)
        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={"exploration": config.model_dump()},
            protocol_service=mock_protocol_service,
        )

        # Patch _run_exploration_round to return stable result
        stable_round = ExplorationRoundResult(
            round_number=1, results=[], new_issues_count=0, is_stable=True,
        )
        engine._run_exploration_round = AsyncMock(return_value=stable_round)

        run, iteration = MagicMock(), MagicMock()
        result = await engine.explore(run, iteration, sample_claims, sample_facts)

        # Should run min_rounds=2 even though stable
        assert engine._run_exploration_round.call_count >= 2
        assert isinstance(result, ExplorationStageResult)

    @pytest.mark.asyncio
    async def test_explore_stops_on_stability_after_min_rounds(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Engine stops when stable and min_rounds met."""
        from app.services.exploration.engine import ExplorationEngine

        config = ExplorationConfig(min_rounds=1, max_rounds=5, stability_threshold=0)
        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={"exploration": config.model_dump()},
            protocol_service=mock_protocol_service,
        )

        stable_round = ExplorationRoundResult(
            round_number=1, results=[], new_issues_count=0, is_stable=True,
        )
        engine._run_exploration_round = AsyncMock(return_value=stable_round)

        run, iteration = MagicMock(), MagicMock()
        result = await engine.explore(run, iteration, sample_claims, sample_facts)

        # Should stop at min_rounds since stable
        assert engine._run_exploration_round.call_count == 1

    @pytest.mark.asyncio
    async def test_explore_stops_at_max_rounds(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Engine stops at max_rounds even if still finding new issues."""
        from app.services.exploration.engine import ExplorationEngine

        config = ExplorationConfig(min_rounds=1, max_rounds=3, stability_threshold=0)
        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={"exploration": config.model_dump()},
            protocol_service=mock_protocol_service,
        )

        unstable_round = ExplorationRoundResult(
            round_number=1,
            results=[ExplorationResult(
                description="New issue",
                source_layer="cheap_llm",
                confidence=0.7,
                is_new_issue=True,
                claim_name="New Claim",
            )],
            new_issues_count=1,
            is_stable=False,
        )
        engine._run_exploration_round = AsyncMock(return_value=unstable_round)

        run, iteration = MagicMock(), MagicMock()
        result = await engine.explore(run, iteration, sample_claims, sample_facts)

        assert engine._run_exploration_round.call_count == 3  # max_rounds


# ---------------------------------------------------------------------------
# Layer tests
# ---------------------------------------------------------------------------


class TestLayerFolioAdjacency:
    """Tests for layer_folio_adjacency."""

    @pytest.mark.asyncio
    async def test_calls_discover_adjacent_for_each_claim_iri(self, sample_claims):
        """layer_folio_adjacency calls discover_adjacent_concepts for each claim IRI."""
        from app.services.exploration.layers import layer_folio_adjacency

        mock_folio = MagicMock()
        mock_folio.classes = {
            "https://folio.openlegalstandard.org/objective001": MagicMock(label="WT"),
            "https://folio.openlegalstandard.org/objective002": MagicMock(label="BC"),
        }

        with patch("app.services.exploration.layers.discover_adjacent_concepts") as mock_discover:
            mock_discover.return_value = _make_adjacency_result(
                "https://folio.openlegalstandard.org/child001", "Child Concept", depth=1,
            )
            config = ExplorationConfig()
            results = await layer_folio_adjacency(mock_folio, sample_claims, config)

        # Called once per claim with a folio_iri
        assert mock_discover.call_count == 2
        assert all(isinstance(r, ExplorationResult) for r in results)
        assert all(r.source_layer == "folio_adjacency" for r in results)

    @pytest.mark.asyncio
    async def test_skips_when_folio_is_none(self, sample_claims):
        """Graceful degradation: returns empty when folio is None."""
        from app.services.exploration.layers import layer_folio_adjacency

        results = await layer_folio_adjacency(None, sample_claims, ExplorationConfig())
        assert results == []


class TestLayerProtocolMatch:
    """Tests for layer_protocol_match."""

    @pytest.mark.asyncio
    async def test_matches_protocol_triggers_against_facts(self):
        """layer_protocol_match returns results for matched protocols."""
        from app.services.exploration.layers import layer_protocol_match

        # Build mock active protocols
        activation = MagicMock()
        activation.protocol_id = 1
        version = MagicMock()
        version.id = 10
        version.trigger_conditions_json = {
            "keywords": ["domestic violence", "abuse"],
        }
        version.questions_json = [
            {"text": "Are you safe right now?", "priority": 1},
        ]
        version.escalation_actions_json = {"type": "immediate_interrupt"}
        version._protocol_name = "DV Screening"
        version._severity_tier = "critical"

        active_protocols = [(activation, version)]
        facts_text = "My husband has been abusing me and the children"

        results = await layer_protocol_match(active_protocols, facts_text)
        assert len(results) > 0
        assert results[0].source_layer == "protocol_match"
        assert results[0].protocol_id == 1


class TestLayerCheapLlm:
    """Tests for layer_cheap_llm."""

    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_results(self, mock_llm_service, sample_claims):
        """layer_cheap_llm calls LLM and parses structured output."""
        from app.services.exploration.layers import layer_cheap_llm

        # Mock the LLM call to return structured JSON
        mock_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = {
            "issues": [
                {
                    "claim_name": "Wage Theft",
                    "description": "Potential unpaid wages claim",
                    "confidence": 0.7,
                    "rationale": "Employer didn't pay last paycheck",
                },
            ],
        }
        mock_model.json_async = AsyncMock(return_value=mock_response)

        with patch("app.services.exploration.layers._create_llm_model", return_value=mock_model):
            results = await layer_cheap_llm(
                mock_llm_service, "I was fired and not paid", sample_claims, {},
            )

        assert len(results) == 1
        assert results[0].source_layer == "cheap_llm"
        assert results[0].claim_name == "Wage Theft"

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_failure(self, mock_llm_service, sample_claims):
        """Graceful degradation: returns empty on LLM failure."""
        from app.services.exploration.layers import layer_cheap_llm

        with patch("app.services.exploration.layers._create_llm_model", side_effect=Exception("LLM unavailable")):
            results = await layer_cheap_llm(
                mock_llm_service, "facts text", sample_claims, {},
            )

        assert results == []


class TestLayerExpensiveLlm:
    """Tests for layer_expensive_llm."""

    @pytest.mark.asyncio
    async def test_calls_llm_with_context(self, mock_llm_service, sample_claims):
        """layer_expensive_llm passes FOLIO + protocol context to LLM."""
        from app.services.exploration.layers import layer_expensive_llm

        mock_model = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = {
            "issues": [
                {
                    "claim_name": "Discrimination",
                    "description": "Potential employment discrimination",
                    "confidence": 0.8,
                    "rationale": "Pattern suggests discriminatory termination",
                },
            ],
        }
        mock_model.json_async = AsyncMock(return_value=mock_response)

        folio_context = [
            ExplorationResult(
                description="Related concept",
                source_layer="folio_adjacency",
                confidence=0.7,
                is_new_issue=True,
            ),
        ]
        protocol_context = []

        with patch("app.services.exploration.layers._create_llm_model", return_value=mock_model):
            results = await layer_expensive_llm(
                mock_llm_service, "I was fired", sample_claims,
                folio_context, protocol_context, {},
            )

        assert len(results) == 1
        assert results[0].source_layer == "expensive_llm"


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for _deduplicate_results on ExplorationEngine."""

    @pytest.mark.asyncio
    async def test_merges_same_folio_iri_keeps_highest_confidence(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service,
    ):
        """Results with same FOLIO IRI merged, highest confidence kept."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        results = [
            ExplorationResult(
                description="Issue A",
                folio_iri="https://folio.openlegalstandard.org/obj001",
                source_layer="cheap_llm",
                confidence=0.6,
                is_new_issue=True,
                claim_name="Issue A",
            ),
            ExplorationResult(
                description="Issue A variant",
                folio_iri="https://folio.openlegalstandard.org/obj001",
                source_layer="folio_adjacency",
                confidence=0.8,
                is_new_issue=True,
                claim_name="Issue A",
            ),
        ]

        deduped = await engine._deduplicate_results(results)
        iri_results = [r for r in deduped if r.folio_iri == "https://folio.openlegalstandard.org/obj001"]
        assert len(iri_results) == 1
        assert iri_results[0].confidence == 0.8

    @pytest.mark.asyncio
    async def test_resolves_unresolved_via_concept_resolver(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service,
    ):
        """Unresolved results use ConceptResolver for FOLIO IRI."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=MagicMock(),
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        results = [
            ExplorationResult(
                description="Employment discrimination issue",
                folio_iri=None,
                source_layer="cheap_llm",
                confidence=0.7,
                is_new_issue=True,
                claim_name="Discrimination",
            ),
        ]

        mock_resolved = MagicMock()
        mock_resolved.iri = "https://folio.openlegalstandard.org/resolved001"

        with patch("app.services.exploration.engine.resolve_concepts", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = [mock_resolved]
            deduped = await engine._deduplicate_results(results)

        assert len(deduped) >= 1

    @pytest.mark.asyncio
    async def test_keeps_unresolvable_results(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service,
    ):
        """Truly unresolvable results kept as-is (not dropped)."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=MagicMock(),
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        results = [
            ExplorationResult(
                description="Totally novel issue",
                folio_iri=None,
                source_layer="expensive_llm",
                confidence=0.6,
                is_new_issue=True,
                claim_name="Novel Issue",
            ),
        ]

        with patch("app.services.exploration.engine.resolve_concepts", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = []  # Nothing resolved
            deduped = await engine._deduplicate_results(results)

        assert len(deduped) == 1
        assert deduped[0].claim_name == "Novel Issue"


# ---------------------------------------------------------------------------
# Parallel execution test
# ---------------------------------------------------------------------------


class TestParallelExecution:
    """Verify hybrid parallel approach (D-05): cheap LLM || sequential pipeline."""

    @pytest.mark.asyncio
    async def test_round_runs_cheap_llm_parallel_with_sequential(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Single round runs both branches via asyncio.gather."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        with patch("app.services.exploration.engine.layer_cheap_llm", new_callable=AsyncMock) as mock_cheap, \
             patch("app.services.exploration.engine.layer_folio_adjacency", new_callable=AsyncMock) as mock_folio, \
             patch("app.services.exploration.engine.layer_protocol_match", new_callable=AsyncMock) as mock_proto, \
             patch("app.services.exploration.engine.layer_expensive_llm", new_callable=AsyncMock) as mock_expensive:

            mock_cheap.return_value = []
            mock_folio.return_value = []
            mock_proto.return_value = []
            mock_expensive.return_value = []

            facts_text = "I was fired from my job"
            context = engine._build_context(sample_claims, sample_facts, [])
            result = await engine._run_exploration_round(context, 1)

            mock_cheap.assert_called_once()
            mock_folio.assert_called_once()
            mock_proto.assert_called_once()
            mock_expensive.assert_called_once()
            assert isinstance(result, ExplorationRoundResult)


# ---------------------------------------------------------------------------
# Graceful degradation and filtering
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Graceful degradation when dependencies unavailable."""

    @pytest.mark.asyncio
    async def test_folio_none_skips_folio_layer(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """ExplorationEngine with FOLIO=None gracefully skips FOLIO layer."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        with patch("app.services.exploration.engine.layer_cheap_llm", new_callable=AsyncMock) as mock_cheap, \
             patch("app.services.exploration.engine.layer_folio_adjacency", new_callable=AsyncMock) as mock_folio, \
             patch("app.services.exploration.engine.layer_protocol_match", new_callable=AsyncMock) as mock_proto, \
             patch("app.services.exploration.engine.layer_expensive_llm", new_callable=AsyncMock) as mock_expensive:

            mock_cheap.return_value = []
            mock_folio.return_value = []
            mock_proto.return_value = []
            mock_expensive.return_value = []

            run, iteration = MagicMock(), MagicMock()
            result = await engine.explore(run, iteration, sample_claims, sample_facts)

            # layer_folio_adjacency is called but with folio=None, it returns []
            assert isinstance(result, ExplorationStageResult)

    @pytest.mark.asyncio
    async def test_llm_unavailable_falls_back(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """ExplorationEngine with LLM unavailable falls back to FOLIO + protocol layers."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        with patch("app.services.exploration.engine.layer_cheap_llm", new_callable=AsyncMock) as mock_cheap, \
             patch("app.services.exploration.engine.layer_folio_adjacency", new_callable=AsyncMock) as mock_folio, \
             patch("app.services.exploration.engine.layer_protocol_match", new_callable=AsyncMock) as mock_proto, \
             patch("app.services.exploration.engine.layer_expensive_llm", new_callable=AsyncMock) as mock_expensive:

            mock_cheap.side_effect = Exception("LLM unavailable")
            mock_folio.return_value = []
            mock_proto.return_value = []
            mock_expensive.side_effect = Exception("LLM unavailable")

            run, iteration = MagicMock(), MagicMock()
            result = await engine.explore(run, iteration, sample_claims, sample_facts)

            assert isinstance(result, ExplorationStageResult)


class TestConfidenceThreshold:
    """Exploration confidence threshold filters low-quality results."""

    @pytest.mark.asyncio
    async def test_filters_below_threshold(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Results below exploration_confidence_threshold are filtered out."""
        from app.services.exploration.engine import ExplorationEngine

        config = ExplorationConfig(
            min_rounds=1, max_rounds=1, exploration_confidence_threshold=0.5,
        )
        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={"exploration": config.model_dump()},
            protocol_service=mock_protocol_service,
        )

        low_conf = ExplorationResult(
            description="Low conf", source_layer="cheap_llm",
            confidence=0.3, is_new_issue=True, claim_name="Low",
        )
        high_conf = ExplorationResult(
            description="High conf", source_layer="cheap_llm",
            confidence=0.7, is_new_issue=True, claim_name="High",
        )

        with patch("app.services.exploration.engine.layer_cheap_llm", new_callable=AsyncMock) as mock_cheap, \
             patch("app.services.exploration.engine.layer_folio_adjacency", new_callable=AsyncMock) as mock_folio, \
             patch("app.services.exploration.engine.layer_protocol_match", new_callable=AsyncMock) as mock_proto, \
             patch("app.services.exploration.engine.layer_expensive_llm", new_callable=AsyncMock) as mock_expensive:

            mock_cheap.return_value = [low_conf, high_conf]
            mock_folio.return_value = []
            mock_proto.return_value = []
            mock_expensive.return_value = []

            run, iteration = MagicMock(), MagicMock()
            result = await engine.explore(run, iteration, sample_claims, sample_facts)

            # Only the high confidence result should survive
            all_results = []
            for rnd in result.rounds:
                all_results.extend(rnd.results)
            high_conf_results = [r for r in all_results if r.confidence >= 0.5]
            low_conf_results = [r for r in all_results if r.confidence < 0.5]
            assert len(low_conf_results) == 0
            assert len(high_conf_results) >= 1


class TestNewIssueMarking:
    """Exploration-discovered issues marked as is_new_issue=True only if not in existing claims."""

    @pytest.mark.asyncio
    async def test_existing_claim_not_marked_new(
        self, mock_llm_service, mock_embedding_service, mock_db_session,
        mock_protocol_service, sample_claims, sample_facts,
    ):
        """Results matching existing claims have is_new_issue=False."""
        from app.services.exploration.engine import ExplorationEngine

        engine = ExplorationEngine(
            folio=None,
            llm_service=mock_llm_service,
            embedding_service=mock_embedding_service,
            db_session=mock_db_session,
            org_config={},
            protocol_service=mock_protocol_service,
        )

        # Result that matches an existing claim by IRI
        existing_result = ExplorationResult(
            description="Wrongful Termination",
            folio_iri="https://folio.openlegalstandard.org/objective001",
            source_layer="folio_adjacency",
            confidence=0.8,
            is_new_issue=True,  # Will be corrected by engine
            claim_name="Wrongful Termination",
        )

        with patch("app.services.exploration.engine.layer_cheap_llm", new_callable=AsyncMock) as mock_cheap, \
             patch("app.services.exploration.engine.layer_folio_adjacency", new_callable=AsyncMock) as mock_folio, \
             patch("app.services.exploration.engine.layer_protocol_match", new_callable=AsyncMock) as mock_proto, \
             patch("app.services.exploration.engine.layer_expensive_llm", new_callable=AsyncMock) as mock_expensive:

            mock_cheap.return_value = []
            mock_folio.return_value = [existing_result]
            mock_proto.return_value = []
            mock_expensive.return_value = []

            run, iteration = MagicMock(), MagicMock()
            result = await engine.explore(run, iteration, sample_claims, sample_facts)

            # The result matching existing claim should have is_new_issue=False
            all_results = []
            for rnd in result.rounds:
                all_results.extend(rnd.results)

            for r in all_results:
                if r.folio_iri == "https://folio.openlegalstandard.org/objective001":
                    assert r.is_new_issue is False
