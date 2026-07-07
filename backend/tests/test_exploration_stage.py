"""Tests for ExploreStage orchestrator integration and AnalysisClaim persistence.

Tests ExploreStage following IssueSpotStage pattern: constructor, execute method,
AnalysisClaim creation for discovered issues, orchestrator STAGES list update,
and question_transparency config propagation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exploration.schemas import (
    ExplorationConfig,
    ExplorationResult,
    ExplorationRoundResult,
    ExplorationStageResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claim(claim_name: str, folio_iri: str | None = None) -> MagicMock:
    claim = MagicMock()
    claim.claim_name = claim_name
    claim.folio_iri = folio_iri
    claim.claim_type = "identified"
    claim.confidence = 0.8
    claim.is_potential = False
    return claim


def _make_fact(text: str) -> MagicMock:
    fact = MagicMock()
    fact.assertion_text = text
    fact.fact_type = "event"
    fact.confidence = 0.9
    return fact


def _make_stage_result() -> ExplorationStageResult:
    """Create a sample ExplorationStageResult with discovered issues."""
    return ExplorationStageResult(
        rounds=[
            ExplorationRoundResult(
                round_number=1,
                results=[
                    ExplorationResult(
                        description="Discovered DV issue",
                        folio_iri="https://folio.openlegalstandard.org/obj_dv",
                        source_layer="protocol_match",
                        confidence=0.85,
                        is_new_issue=True,
                        claim_name="Domestic Violence",
                        rationale="Protocol triggered by keyword match",
                        protocol_id=1,
                    ),
                    ExplorationResult(
                        description="Wage theft",
                        folio_iri=None,
                        source_layer="cheap_llm",
                        confidence=0.6,
                        is_new_issue=True,
                        claim_name="Wage Theft",
                        rationale="Employer didn't pay last paycheck",
                    ),
                ],
                new_issues_count=2,
                is_stable=False,
            ),
            ExplorationRoundResult(
                round_number=2,
                results=[],
                new_issues_count=0,
                is_stable=True,
            ),
        ],
        total_new_issues=2,
        new_claims=[
            {
                "claim_name": "Domestic Violence",
                "folio_iri": "https://folio.openlegalstandard.org/obj_dv",
                "confidence": 0.85,
                "source_layer": "protocol_match",
                "rationale": "Protocol triggered by keyword match",
            },
            {
                "claim_name": "Wage Theft",
                "folio_iri": None,
                "confidence": 0.6,
                "source_layer": "cheap_llm",
                "rationale": "Employer didn't pay last paycheck",
            },
        ],
        triggered_protocols=[
            {"protocol_id": 1, "claim_name": "Domestic Violence", "confidence": 0.85},
        ],
    )


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
    }
    return llm


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_embedding():
    return AsyncMock()


@pytest.fixture
def sample_run():
    run = MagicMock()
    run.id = 1
    run.intake_id = 10
    return run


@pytest.fixture
def sample_iteration():
    it = MagicMock()
    it.id = 1
    it.iteration_number = 1
    return it


@pytest.fixture
def sample_claims():
    return [
        _make_claim("Wrongful Termination", "https://folio.openlegalstandard.org/obj001"),
    ]


@pytest.fixture
def sample_facts():
    return [
        _make_fact("I was fired from my job"),
        _make_fact("My employer didn't pay me"),
    ]


# ---------------------------------------------------------------------------
# ExploreStage tests
# ---------------------------------------------------------------------------


class TestExploreStageExecute:
    """ExploreStage.execute returns expected dict and creates AnalysisClaim records."""

    @pytest.mark.asyncio
    async def test_returns_expected_keys(
        self, mock_llm, mock_session, mock_embedding,
        sample_run, sample_iteration, sample_claims, sample_facts,
    ):
        """ExploreStage.execute returns dict with new_claims, triggered_protocols, etc."""
        from app.services.analysis.stages.explore import ExploreStage

        stage = ExploreStage(
            llm_service=mock_llm,
            db_session=mock_session,
            folio=None,
            embedding_service=mock_embedding,
            org_config={},
        )

        stage_result = _make_stage_result()

        with patch("app.services.analysis.stages.explore.ExplorationEngine") as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.explore = AsyncMock(return_value=stage_result)
            MockEngine.return_value = mock_engine

            with patch("app.services.analysis.stages.explore.ProtocolService") as MockPS:
                MockPS.return_value = AsyncMock()

                result = await stage.execute(
                    sample_run, sample_iteration, sample_claims, sample_facts,
                )

        assert "new_claims" in result
        assert "triggered_protocols" in result
        assert "rounds_completed" in result
        assert "total_new_issues" in result

    @pytest.mark.asyncio
    async def test_creates_analysis_claims_for_discovered_issues(
        self, mock_llm, mock_session, mock_embedding,
        sample_run, sample_iteration, sample_claims, sample_facts,
    ):
        """ExploreStage creates AnalysisClaim with claim_type='discovered' and is_potential=True."""
        from app.services.analysis.stages.explore import ExploreStage

        stage = ExploreStage(
            llm_service=mock_llm,
            db_session=mock_session,
            folio=None,
            embedding_service=mock_embedding,
            org_config={},
        )

        stage_result = _make_stage_result()

        with patch("app.services.analysis.stages.explore.ExplorationEngine") as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.explore = AsyncMock(return_value=stage_result)
            MockEngine.return_value = mock_engine

            with patch("app.services.analysis.stages.explore.ProtocolService") as MockPS:
                MockPS.return_value = AsyncMock()

                result = await stage.execute(
                    sample_run, sample_iteration, sample_claims, sample_facts,
                )

        # Verify session.add was called for each new claim
        add_calls = mock_session.add.call_args_list
        # At least 2 claims should be added
        claim_adds = [
            c for c in add_calls
            if hasattr(c[0][0], "claim_type") and c[0][0].claim_type == "discovered"
        ]
        assert len(claim_adds) >= 2

        # Check the claims have correct attributes
        for call_args in claim_adds:
            claim = call_args[0][0]
            assert claim.claim_type == "discovered"
            assert claim.is_potential is True

    @pytest.mark.asyncio
    async def test_question_transparency_propagated(
        self, mock_llm, mock_session, mock_embedding,
        sample_run, sample_iteration, sample_claims, sample_facts,
    ):
        """ExploreStage uses question_transparency from ExplorationConfig."""
        from app.services.analysis.stages.explore import ExploreStage

        stage = ExploreStage(
            llm_service=mock_llm,
            db_session=mock_session,
            folio=None,
            embedding_service=mock_embedding,
            org_config={"exploration": {"question_transparency": False}},
        )

        stage_result = _make_stage_result()

        with patch("app.services.analysis.stages.explore.ExplorationEngine") as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.explore = AsyncMock(return_value=stage_result)
            MockEngine.return_value = mock_engine

            with patch("app.services.analysis.stages.explore.ProtocolService") as MockPS:
                MockPS.return_value = AsyncMock()

                result = await stage.execute(
                    sample_run, sample_iteration, sample_claims, sample_facts,
                )

        assert "question_transparency" in result


class TestExploreStageGuards:
    """BUG-8 guards: no exploration from zero facts; dedupe across iterations."""

    @pytest.mark.asyncio
    async def test_skips_exploration_when_no_facts(
        self, mock_llm, mock_session, mock_embedding,
        sample_run, sample_iteration, sample_claims,
    ):
        """With zero extracted facts, exploration is skipped entirely (no LLM)."""
        from app.services.analysis.stages.explore import ExploreStage

        stage = ExploreStage(
            llm_service=mock_llm,
            db_session=mock_session,
            folio=None,
            embedding_service=mock_embedding,
            org_config={},
        )

        with patch("app.services.analysis.stages.explore.ExplorationEngine") as MockEngine:
            result = await stage.execute(
                sample_run, sample_iteration, sample_claims, [],
            )

        MockEngine.assert_not_called()
        assert result["new_claims"] == 0
        assert result["skipped_no_facts"] is True
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedupes_discovered_claims_against_existing(
        self, mock_llm, mock_session, mock_embedding,
        sample_run, sample_iteration, sample_facts,
    ):
        """Discovered claims whose name already exists are not re-persisted."""
        from app.services.analysis.stages.explore import ExploreStage

        # Existing claims already include one of the two discovered names
        # (case-insensitively).
        existing = [
            _make_claim("domestic violence"),
            _make_claim("Wrongful Termination"),
        ]

        stage = ExploreStage(
            llm_service=mock_llm,
            db_session=mock_session,
            folio=None,
            embedding_service=mock_embedding,
            org_config={},
        )

        stage_result = _make_stage_result()

        with patch("app.services.analysis.stages.explore.ExplorationEngine") as MockEngine:
            mock_engine = AsyncMock()
            mock_engine.explore = AsyncMock(return_value=stage_result)
            MockEngine.return_value = mock_engine

            with patch("app.services.analysis.stages.explore.ProtocolService") as MockPS:
                MockPS.return_value = AsyncMock()

                result = await stage.execute(
                    sample_run, sample_iteration, existing, sample_facts,
                )

        # Only "Wage Theft" is new; "Domestic Violence" deduped.
        assert result["new_claims"] == 1
        added_names = [c[0][0].claim_name for c in mock_session.add.call_args_list]
        assert added_names == ["Wage Theft"]


# ---------------------------------------------------------------------------
# Orchestrator integration tests
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """Verify orchestrator STAGES list and _get_stage_instance."""

    def test_stages_contains_explore_between_issue_spot_and_research(self):
        """STAGES has 'explore' between 'issue_spot' and 'research' per D-07."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        stages = AnalysisOrchestrator.STAGES
        assert "explore" in stages
        issue_spot_idx = stages.index("issue_spot")
        explore_idx = stages.index("explore")
        research_idx = stages.index("research")
        assert explore_idx == issue_spot_idx + 1
        assert research_idx == explore_idx + 1

    def test_get_stage_instance_returns_explore_stage(self):
        """_get_stage_instance('explore') returns ExploreStage instance."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator
        from app.services.analysis.stages.explore import ExploreStage

        mock_session = AsyncMock()
        mock_llm = MagicMock()
        orchestrator = AnalysisOrchestrator(
            db_session=mock_session,
            llm_service=mock_llm,
        )

        stage = orchestrator._get_stage_instance("explore")
        assert isinstance(stage, ExploreStage)


class TestOrchestratorDecisionSchema:
    """OrchestratorDecision accepts 'explore' as valid next_stage."""

    def test_explore_is_valid_next_stage(self):
        """OrchestratorDecision schema accepts 'explore'."""
        from app.services.analysis.schemas import OrchestratorDecision

        decision = OrchestratorDecision(
            next_stage="explore",
            reasoning="Running exploration after issue-spotting",
        )
        assert decision.next_stage == "explore"


class TestStagesInit:
    """ExploreStage is exported from stages __init__."""

    def test_explore_stage_in_exports(self):
        """ExploreStage is importable from stages package."""
        from app.services.analysis.stages import ExploreStage

        assert ExploreStage is not None


# ---------------------------------------------------------------------------
# Full integration: orchestrator runs explore after issue_spot
# ---------------------------------------------------------------------------


class TestFullOrchestration:
    """Verify the orchestrator runs explore stage in the right position."""

    @pytest.mark.asyncio
    async def test_select_stages_includes_explore(self):
        """_select_stages returns all stages including explore."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        mock_session = AsyncMock()
        mock_llm = MagicMock()
        orchestrator = AnalysisOrchestrator(
            db_session=mock_session,
            llm_service=mock_llm,
        )

        run = MagicMock()
        iteration = MagicMock()
        stages = await orchestrator._select_stages(run, iteration)
        assert "explore" in stages
        assert stages.index("explore") == 1  # After issue_spot, before research
