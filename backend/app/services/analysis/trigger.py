"""Analysis trigger system -- auto + manual analysis triggering (D-04).

Auto-triggers when N new facts accumulate since last analysis run.
Manual trigger available via REST API at any time.
Threshold configurable per org via analysis_settings.auto_trigger_threshold.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.analysis import AnalysisRun
from app.models.fact import ExtractedFact

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.analysis.orchestrator import AnalysisOrchestrator

logger = logging.getLogger(__name__)


class AnalysisTrigger:
    """Auto + manual analysis triggering (D-04).

    Auto-triggers when N new facts accumulate since last analysis run.
    Manual trigger available via REST API at any time.
    Threshold configurable per org via analysis_settings.auto_trigger_threshold.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        orchestrator: AnalysisOrchestrator,
        auto_trigger_threshold: int = 5,
    ) -> None:
        self._session = db_session
        self._orchestrator = orchestrator
        self._auto_trigger_threshold = auto_trigger_threshold

    async def check_auto_trigger(
        self,
        intake_id: int,
        session_id: int,
    ) -> bool:
        """Check if auto-trigger threshold reached. Called after fact extraction.

        Count new ExtractedFact records since last AnalysisRun for this intake.
        If count >= threshold and no analysis currently running: trigger via asyncio.create_task.
        Returns True if analysis was triggered.
        """
        # Check if analysis is already running
        if await self._is_analysis_running(intake_id):
            return False

        # Count facts since last completed analysis run
        fact_count = await self._count_new_facts(intake_id)

        if fact_count < self._auto_trigger_threshold:
            return False

        # Trigger analysis in background
        logger.info(
            "Auto-triggering analysis for intake %d (fact_count=%d, threshold=%d)",
            intake_id,
            fact_count,
            self._auto_trigger_threshold,
        )

        # Create the run record immediately so we can track it
        run = AnalysisRun(
            intake_id=intake_id,
            status="running",
            trigger_type="auto",
            current_iteration_number=0,
            max_iterations=10,
        )
        self._session.add(run)
        await self._session.flush()

        # Start orchestrator in background (D-02 hybrid model)
        asyncio.create_task(
            self._orchestrator.run(
                intake_id=intake_id,
                session_id=session_id,
            )
        )

        return True

    async def manual_trigger(
        self,
        intake_id: int,
        session_id: int,
        ws_manager: Any | None = None,
    ) -> AnalysisRun:
        """Manually trigger analysis. Always runs regardless of fact count.

        If analysis already running for this intake: return existing run.
        Background execution via asyncio.create_task (D-02 hybrid model).
        """
        # Check for existing running analysis
        existing = await self._get_running_analysis(intake_id)
        if existing:
            return existing

        # Run analysis directly (for manual trigger, run inline for immediate feedback)
        return await self._orchestrator.run(
            intake_id=intake_id,
            session_id=session_id,
            ws_manager=ws_manager,
        )

    async def _is_analysis_running(self, intake_id: int) -> bool:
        """Check if an AnalysisRun with status='running' exists for this intake."""
        result = await self._session.execute(
            select(AnalysisRun).where(
                AnalysisRun.intake_id == intake_id,
                AnalysisRun.status == "running",
            )
        )
        return result.scalars().first() is not None

    async def _get_running_analysis(self, intake_id: int) -> AnalysisRun | None:
        """Get the running AnalysisRun for this intake, if any."""
        result = await self._session.execute(
            select(AnalysisRun).where(
                AnalysisRun.intake_id == intake_id,
                AnalysisRun.status == "running",
            )
        )
        return result.scalars().first()

    async def _count_new_facts(self, intake_id: int) -> int:
        """Count ExtractedFact records since the last completed AnalysisRun.

        If no prior run exists, counts all facts.
        """
        # Find the last completed run's created_at timestamp
        last_run_result = await self._session.execute(
            select(AnalysisRun.created_at)
            .where(
                AnalysisRun.intake_id == intake_id,
                AnalysisRun.status.in_(["converged", "max_iterations"]),
            )
            .order_by(AnalysisRun.created_at.desc())
            .limit(1)
        )
        last_run_time = last_run_result.scalars().first()

        # Count facts after last run (or all facts if no prior run)
        query = select(func.count()).select_from(ExtractedFact).where(
            ExtractedFact.intake_id == intake_id,
            ExtractedFact.is_active == True,  # noqa: E712
        )
        if last_run_time:
            query = query.where(ExtractedFact.created_at > last_run_time)

        result = await self._session.execute(query)
        return result.scalar() or 0
