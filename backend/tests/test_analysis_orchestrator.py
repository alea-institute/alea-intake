"""Tests for AnalysisOrchestrator -- iterative analysis loop with LLM-driven stage selection.

Validates orchestrator creates AnalysisRun, iterates with stage execution,
creates AnalysisStage checkpoints with audit_json, supports parallel
jurisdiction execution, pause/resume from checkpoints, override convergence,
and WebSocket progress broadcasting.
"""

import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    AnalysisStage,
    ClaimElement,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact
from app.models.intake import Intake, IntakeSession, Message


# ---- Fixtures ----


@pytest.fixture
async def orch_engine():
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
async def orch_session(orch_engine):
    """Yield an AsyncSession against the test engine."""
    async with orch_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def seed_intake(orch_session):
    """Create intake, session, and sample extracted facts."""
    intake = Intake(
        org_id=1,
        status="active",
    )
    orch_session.add(intake)
    await orch_session.flush()

    session_obj = IntakeSession(
        intake_id=intake.id,
        status="active",
    )
    orch_session.add(session_obj)
    await orch_session.flush()

    facts = []
    for i, (text, ft) in enumerate([
        ("John was fired on January 15, 2026", "legal_event"),
        ("He worked at Acme Corp for 3 years", "time_period"),
        ("His supervisor made discriminatory remarks", "legal_event"),
        ("He is based in California", "location"),
    ]):
        fact = ExtractedFact(
            intake_id=intake.id,
            message_id=1,
            assertion_text=text,
            fact_type=ft,
            confidence=0.85,
        )
        orch_session.add(fact)
    await orch_session.flush()

    return intake, session_obj


@pytest.fixture
def mock_llm_service():
    """Create a mock LLMService."""
    svc = MagicMock()
    svc.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
    }
    svc.json_async = AsyncMock(return_value=MagicMock(data={}))
    return svc


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager with send_to_session."""
    mgr = AsyncMock()
    mgr.send_to_session = AsyncMock()
    return mgr


# ---- Test: Orchestrator creates AnalysisRun and iterates ----


class TestOrchestratorRun:
    """AnalysisOrchestrator.run() creates a run and iterates through stages."""

    @pytest.mark.asyncio
    async def test_creates_run_and_iterates(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """run() creates an AnalysisRun, executes stages, and converges."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        # Mock the internal methods to simulate one iteration that converges
        orch._select_stages = AsyncMock(return_value=["issue_spot", "gap_analyze", "question_gen"])
        orch._execute_stage = AsyncMock(return_value={"stage": "completed"})
        orch._evaluate_convergence = AsyncMock(return_value=(True, 0.85))

        run = await orch.run(
            intake_id=intake.id,
            session_id=session_obj.id,
            ws_manager=mock_ws_manager,
        )

        assert run is not None
        assert run.status == "converged"
        assert run.intake_id == intake.id

        # Verify AnalysisIteration was created
        result = await orch_session.execute(
            select(AnalysisIteration).where(AnalysisIteration.run_id == run.id)
        )
        iterations = result.scalars().all()
        assert len(iterations) >= 1

    @pytest.mark.asyncio
    async def test_hard_cap_terminates(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """run() terminates after max_iterations even without convergence."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
            max_iterations=2,
        )

        orch._select_stages = AsyncMock(return_value=["issue_spot"])
        orch._execute_stage = AsyncMock(return_value={"stage": "completed"})
        orch._evaluate_convergence = AsyncMock(return_value=(False, 0.3))

        run = await orch.run(
            intake_id=intake.id,
            session_id=session_obj.id,
            ws_manager=mock_ws_manager,
        )

        assert run.status == "max_iterations"
        assert run.current_iteration_number == 2


# ---- Test: Checkpoint creation with audit_json ----


class TestCheckpointCreation:
    """Each stage creates an AnalysisStage checkpoint with audit_json."""

    @pytest.mark.asyncio
    async def test_stage_creates_checkpoint_with_audit(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """_execute_stage creates AnalysisStage with populated audit_json."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        # Create run and iteration
        run = AnalysisRun(
            intake_id=intake.id, status="running", trigger_type="manual",
            current_iteration_number=1, max_iterations=10,
        )
        orch_session.add(run)
        await orch_session.flush()

        iteration = AnalysisIteration(
            run_id=run.id, iteration_number=1, status="running",
        )
        orch_session.add(iteration)
        await orch_session.flush()

        # Execute a stage -- mock the stage execute methods
        with patch.object(orch, "_get_stage_instance") as mock_get_stage:
            mock_stage = AsyncMock()
            mock_stage.execute = AsyncMock(return_value={
                "claims_count": 3,
                "jurisdictions": ["CA", "Federal"],
                "summary": "test",
                "claims": [],
            })
            mock_get_stage.return_value = mock_stage

            await orch._execute_stage("issue_spot", run, iteration, mock_ws_manager)

        # Verify AnalysisStage checkpoint was created
        result = await orch_session.execute(
            select(AnalysisStage).where(AnalysisStage.iteration_id == iteration.id)
        )
        stages = result.scalars().all()
        assert len(stages) == 1
        stage = stages[0]
        assert stage.stage_name == "issue_spot"
        assert stage.status == "completed"
        assert stage.audit_json is not None
        assert "stage_name" in stage.audit_json
        assert "duration_ms" in stage.audit_json
        assert stage.duration_ms is not None


# ---- Test: Parallel jurisdiction execution ----


class TestParallelJurisdictions:
    """When multiple jurisdictions detected, fact-map and gap-analyze run in parallel."""

    @pytest.mark.asyncio
    async def test_parallel_jurisdiction_execution(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """_run_parallel_jurisdictions runs per-jurisdiction branches via asyncio.gather."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        run = AnalysisRun(
            intake_id=intake.id, status="running", trigger_type="manual",
            current_iteration_number=1, max_iterations=10,
        )
        orch_session.add(run)
        await orch_session.flush()

        iteration = AnalysisIteration(
            run_id=run.id, iteration_number=1, status="running",
        )
        orch_session.add(iteration)
        await orch_session.flush()

        # Mock _execute_stage to track calls
        stage_calls = []

        async def mock_execute(stage_name, run, iteration, ws_manager, jurisdiction=None):
            stage_calls.append((stage_name, jurisdiction))
            return {"completed": True}

        orch._execute_stage = mock_execute

        await orch._run_parallel_jurisdictions(
            jurisdictions=["CA", "Federal"],
            run=run,
            iteration=iteration,
            ws_manager=mock_ws_manager,
        )

        # Should have called fact_map and gap_analyze for each jurisdiction
        fact_map_calls = [(s, j) for s, j in stage_calls if s == "fact_map"]
        gap_calls = [(s, j) for s, j in stage_calls if s == "gap_analyze"]
        assert len(fact_map_calls) == 2
        assert len(gap_calls) == 2
        assert {"CA", "Federal"} == {j for _, j in fact_map_calls}
        assert {"CA", "Federal"} == {j for _, j in gap_calls}


# ---- Test: Resume from latest checkpoint ----


class TestResume:
    """AnalysisOrchestrator.resume() continues from the last completed stage."""

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """resume() loads the latest stage checkpoint and continues."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        # Create a run that was interrupted after issue_spot
        run = AnalysisRun(
            intake_id=intake.id, status="paused", trigger_type="manual",
            current_iteration_number=1, max_iterations=10,
        )
        orch_session.add(run)
        await orch_session.flush()

        iteration = AnalysisIteration(
            run_id=run.id, iteration_number=1, status="running",
        )
        orch_session.add(iteration)
        await orch_session.flush()

        # Add a completed stage checkpoint
        stage = AnalysisStage(
            iteration_id=iteration.id,
            stage_name="issue_spot",
            status="completed",
            result_json={"claims_count": 2, "jurisdictions": ["CA"]},
            audit_json={"stage_name": "issue_spot"},
        )
        orch_session.add(stage)
        await orch_session.flush()

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        # Mock remaining execution to converge immediately
        orch._select_stages = AsyncMock(return_value=["research", "fact_map", "gap_analyze", "question_gen"])
        orch._execute_stage = AsyncMock(return_value={"stage": "completed"})
        orch._evaluate_convergence = AsyncMock(return_value=(True, 0.9))

        resumed_run = await orch.resume(run_id=run.id, ws_manager=mock_ws_manager)

        assert resumed_run.status == "converged"
        assert resumed_run.id == run.id


# ---- Test: Override convergence ----


class TestOverrideConvergence:
    """override_convergence resets signals and continues analysis."""

    @pytest.mark.asyncio
    async def test_override_resets_and_continues(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """override_convergence resets the run and triggers a new iteration."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        # Create a converged run
        run = AnalysisRun(
            intake_id=intake.id, status="converged", trigger_type="manual",
            current_iteration_number=3, max_iterations=10,
            convergence_score=0.82,
        )
        orch_session.add(run)
        await orch_session.flush()

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        # Mock to converge after one more iteration
        orch._select_stages = AsyncMock(return_value=["issue_spot"])
        orch._execute_stage = AsyncMock(return_value={"stage": "completed"})
        orch._evaluate_convergence = AsyncMock(return_value=(True, 0.92))

        result = await orch.override_convergence(run_id=run.id, ws_manager=mock_ws_manager)

        assert result.status == "converged"
        assert result.current_iteration_number > 3


# ---- Test: WebSocket progress broadcast ----


class TestProgressBroadcast:
    """WebSocket progress updates are sent during orchestration."""

    @pytest.mark.asyncio
    async def test_broadcast_progress_calls_ws(self, orch_session, seed_intake, mock_llm_service, mock_ws_manager):
        """_broadcast_progress sends data via ws_manager.send_to_session."""
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        intake, session_obj = seed_intake

        orch = AnalysisOrchestrator(
            db_session=orch_session,
            llm_service=mock_llm_service,
            folio=None,
            embedding_service=None,
        )

        run = AnalysisRun(
            intake_id=intake.id, status="running", trigger_type="manual",
            current_iteration_number=1, max_iterations=10,
        )
        orch_session.add(run)
        await orch_session.flush()

        await orch._broadcast_progress(run, "issue_spot", mock_ws_manager, session_id=session_obj.id)

        mock_ws_manager.send_to_session.assert_called_once()
        call_args = mock_ws_manager.send_to_session.call_args
        assert call_args[0][0] == session_obj.id
        msg = call_args[0][1]
        assert msg["type"] == "analysis_progress"
        assert msg["stage"] == "issue_spot"
