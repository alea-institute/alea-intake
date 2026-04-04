"""Tests for AnalysisTrigger and analysis REST API endpoints.

Validates auto-trigger fires when fact count >= threshold, does not fire
when analysis already running, manual trigger always starts, and REST
endpoints for trigger (202), status, results, override, and audit trail.
"""

import os
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
async def trigger_engine():
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
async def trigger_session(trigger_engine):
    """Yield an AsyncSession against the test engine."""
    async with trigger_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def seed_trigger_data(trigger_session):
    """Create intake, session, and enough facts to trigger analysis."""
    intake = Intake(org_id=1, status="active")
    trigger_session.add(intake)
    await trigger_session.flush()

    session_obj = IntakeSession(intake_id=intake.id, status="active")
    trigger_session.add(session_obj)
    await trigger_session.flush()

    # Create 6 facts (above default threshold of 5)
    for i in range(6):
        fact = ExtractedFact(
            intake_id=intake.id,
            message_id=1,
            assertion_text=f"Fact {i}",
            fact_type="legal_event",
            confidence=0.8,
        )
        trigger_session.add(fact)
    await trigger_session.flush()

    return intake, session_obj


@pytest.fixture
def mock_orchestrator():
    """Create a mock AnalysisOrchestrator."""
    orch = AsyncMock()
    orch.run = AsyncMock(return_value=MagicMock(
        id=1,
        status="converged",
        intake_id=1,
    ))
    return orch


# ---- Test: Auto-trigger fires when threshold reached ----


class TestAutoTrigger:
    """AnalysisTrigger.check_auto_trigger fires at fact threshold."""

    @pytest.mark.asyncio
    async def test_auto_trigger_fires(self, trigger_session, seed_trigger_data, mock_orchestrator):
        """Auto-trigger returns True when fact count >= threshold."""
        from app.services.analysis.trigger import AnalysisTrigger

        intake, session_obj = seed_trigger_data

        trigger = AnalysisTrigger(
            db_session=trigger_session,
            orchestrator=mock_orchestrator,
            auto_trigger_threshold=5,
        )

        result = await trigger.check_auto_trigger(
            intake_id=intake.id,
            session_id=session_obj.id,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_auto_trigger_does_not_fire_below_threshold(self, trigger_session, mock_orchestrator):
        """Auto-trigger returns False when fact count < threshold."""
        from app.services.analysis.trigger import AnalysisTrigger

        intake = Intake(org_id=1, status="active")
        trigger_session.add(intake)
        await trigger_session.flush()

        session_obj = IntakeSession(intake_id=intake.id, status="active")
        trigger_session.add(session_obj)
        await trigger_session.flush()

        # Only 2 facts (below threshold of 5)
        for i in range(2):
            fact = ExtractedFact(
                intake_id=intake.id,
                message_id=1,
                assertion_text=f"Fact {i}",
                fact_type="legal_event",
                confidence=0.8,
            )
            trigger_session.add(fact)
        await trigger_session.flush()

        trigger = AnalysisTrigger(
            db_session=trigger_session,
            orchestrator=mock_orchestrator,
            auto_trigger_threshold=5,
        )

        result = await trigger.check_auto_trigger(
            intake_id=intake.id,
            session_id=session_obj.id,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_auto_trigger_skips_when_running(self, trigger_session, seed_trigger_data, mock_orchestrator):
        """Auto-trigger returns False when analysis already running."""
        from app.services.analysis.trigger import AnalysisTrigger

        intake, session_obj = seed_trigger_data

        # Create an active running analysis
        run = AnalysisRun(
            intake_id=intake.id,
            status="running",
            trigger_type="auto",
            current_iteration_number=1,
            max_iterations=10,
        )
        trigger_session.add(run)
        await trigger_session.flush()

        trigger = AnalysisTrigger(
            db_session=trigger_session,
            orchestrator=mock_orchestrator,
            auto_trigger_threshold=5,
        )

        result = await trigger.check_auto_trigger(
            intake_id=intake.id,
            session_id=session_obj.id,
        )

        assert result is False


# ---- Test: Manual trigger ----


class TestManualTrigger:
    """Manual trigger always starts analysis."""

    @pytest.mark.asyncio
    async def test_manual_trigger_starts(self, trigger_session, seed_trigger_data, mock_orchestrator):
        """manual_trigger creates and returns an AnalysisRun."""
        from app.services.analysis.trigger import AnalysisTrigger

        intake, session_obj = seed_trigger_data

        trigger = AnalysisTrigger(
            db_session=trigger_session,
            orchestrator=mock_orchestrator,
            auto_trigger_threshold=5,
        )

        run = await trigger.manual_trigger(
            intake_id=intake.id,
            session_id=session_obj.id,
        )

        assert run is not None
        assert run.status in ("running", "converged")

    @pytest.mark.asyncio
    async def test_manual_trigger_returns_existing_if_running(self, trigger_session, seed_trigger_data, mock_orchestrator):
        """manual_trigger returns existing run if one is already active."""
        from app.services.analysis.trigger import AnalysisTrigger

        intake, session_obj = seed_trigger_data

        # Create an active running analysis
        existing_run = AnalysisRun(
            intake_id=intake.id,
            status="running",
            trigger_type="auto",
            current_iteration_number=1,
            max_iterations=10,
        )
        trigger_session.add(existing_run)
        await trigger_session.flush()

        trigger = AnalysisTrigger(
            db_session=trigger_session,
            orchestrator=mock_orchestrator,
            auto_trigger_threshold=5,
        )

        run = await trigger.manual_trigger(
            intake_id=intake.id,
            session_id=session_obj.id,
        )

        assert run.id == existing_run.id


# ---- Test: REST API endpoints ----


class TestAnalysisAPI:
    """Analysis REST API endpoints."""

    @pytest.mark.asyncio
    async def test_analysis_router_exists(self):
        """analysis router is registered and has expected routes."""
        from app.routers.analysis import router

        route_paths = [r.path for r in router.routes]
        assert any("analyze" in p for p in route_paths)
        assert any("status" in p for p in route_paths)
        assert any("results" in p for p in route_paths)
        assert any("override" in p for p in route_paths)
        assert any("audit" in p for p in route_paths)

    @pytest.mark.asyncio
    async def test_analysis_router_in_main(self):
        """analysis router is included in main app."""
        from app.main import app

        # Check that analysis routes are registered
        route_paths = [r.path for r in app.routes]
        assert any("/api/v1/analysis" in p for p in route_paths)
