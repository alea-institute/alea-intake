"""Tests for AutonomyInterceptor wrapping stage execution.

Covers chatbot (all auto), professional (all checkpoint), agent (selective),
safety override, rejection re-run, edit apply, and mid-intake mode switch.
Also tests orchestrator accepts optional autonomy_interceptor parameter.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.analysis.autonomy.approval_queue import ApprovalQueue
from app.services.analysis.autonomy.config import (
    AutonomyConfig,
    StageCheckpoint,
    TimeoutBehavior,
)
from app.services.analysis.autonomy.interceptor import AutonomyInterceptor
from app.services.analysis.autonomy.schemas import ApprovalAction


ALL_STAGES = [
    "issue_spot",
    "explore",
    "research",
    "fact_map",
    "gap_analyze",
    "question_gen",
]


@pytest.fixture
def mock_audit_logger() -> MagicMock:
    logger = MagicMock()
    logger.log_checkpoint_reached = AsyncMock()
    logger.log_approved = AsyncMock()
    logger.log_rejected = AsyncMock()
    logger.log_edited = AsyncMock()
    logger.log_auto_proceed = AsyncMock()
    logger.log_stage_skip = AsyncMock()
    logger.log_mode_change = AsyncMock()
    logger.log_event = AsyncMock()
    return logger


@pytest.fixture
def mock_notification() -> MagicMock:
    notif = MagicMock()
    notif.notify = AsyncMock()
    return notif


@pytest.fixture
def execute_fn() -> AsyncMock:
    fn = AsyncMock(return_value={"claims": ["claim1"], "status": "ok"})
    return fn


class TestChatbotAllAuto:
    """AUTONOMY-01: chatbot preset calls execute_fn immediately, no approval."""

    @pytest.mark.asyncio
    async def test_chatbot_all_auto(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.chatbot_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        for stage in ALL_STAGES:
            result = await interceptor.execute_with_autonomy(
                stage_name=stage,
                execute_fn=execute_fn,
                run_id=1,
                iteration_id=10,
                intake_id=100,
            )
            assert result == {"claims": ["claim1"], "status": "ok"}

        # execute_fn called once per stage (6 times total)
        assert execute_fn.await_count == 6
        # No approval requests created
        assert len(queue.get_pending()) == 0


class TestProfessionalAllCheckpoint:
    """AUTONOMY-02: professional preset creates approval for every stage."""

    @pytest.mark.asyncio
    async def test_professional_all_checkpoint(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.professional_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        async def _auto_approve_all() -> None:
            """Auto-approve any requests that appear."""
            for _ in range(20):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    try:
                        queue.resolve(req.id, ApprovalAction(decision="approve"))
                    except (ValueError, KeyError):
                        pass

        approver = asyncio.create_task(_auto_approve_all())

        for stage in ALL_STAGES:
            result = await interceptor.execute_with_autonomy(
                stage_name=stage,
                execute_fn=execute_fn,
                run_id=1,
                iteration_id=10,
                intake_id=100,
            )
            assert result == {"claims": ["claim1"], "status": "ok"}

        approver.cancel()
        # Notification called for each stage
        assert mock_notification.notify.await_count == 6


class TestAgentSelectiveCheckpoints:
    """AUTONOMY-03: agent preset auto-passes most stages, checkpoints question_gen."""

    @pytest.mark.asyncio
    async def test_agent_selective(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.agent_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        # Auto stages run without approval
        for stage in ALL_STAGES[:-1]:  # All except question_gen
            result = await interceptor.execute_with_autonomy(
                stage_name=stage,
                execute_fn=execute_fn,
                run_id=1,
                iteration_id=10,
                intake_id=100,
            )
            assert result == {"claims": ["claim1"], "status": "ok"}

        assert mock_notification.notify.await_count == 0

        # question_gen needs approval
        async def _approve_question_gen() -> None:
            for _ in range(20):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    try:
                        queue.resolve(req.id, ApprovalAction(decision="approve"))
                    except (ValueError, KeyError):
                        pass

        approver = asyncio.create_task(_approve_question_gen())
        result = await interceptor.execute_with_autonomy(
            stage_name="question_gen",
            execute_fn=execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        approver.cancel()
        assert result == {"claims": ["claim1"], "status": "ok"}
        assert mock_notification.notify.await_count == 1


class TestSafetyOverride:
    """D-02: safety alerts always force checkpoint regardless of config."""

    @pytest.mark.asyncio
    async def test_safety_always_checkpoints(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.chatbot_preset()  # All AUTO
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        async def _approve() -> None:
            for _ in range(20):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    try:
                        queue.resolve(req.id, ApprovalAction(decision="approve"))
                    except (ValueError, KeyError):
                        pass

        approver = asyncio.create_task(_approve())
        result = await interceptor.execute_with_autonomy(
            stage_name="issue_spot",
            execute_fn=execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
            safety_triggered=True,
        )
        approver.cancel()
        assert result == {"claims": ["claim1"], "status": "ok"}
        # Notification was called despite chatbot preset
        assert mock_notification.notify.await_count == 1


class TestRejectRerun:
    """D-08: rejection re-runs stage with guidance, up to 2 times."""

    @pytest.mark.asyncio
    async def test_reject_rerun_with_guidance(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock,
    ) -> None:
        call_count = 0

        async def _execute_fn(**kwargs: object) -> dict:
            nonlocal call_count
            call_count += 1
            return {"result": f"attempt_{call_count}"}

        config = AutonomyConfig.professional_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        async def _reject_then_approve() -> None:
            """First reject, then approve the re-run."""
            seen: set[int] = set()
            for _ in range(40):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    if req.id not in seen:
                        seen.add(req.id)
                        if len(seen) == 1:
                            # First: reject
                            queue.resolve(
                                req.id,
                                ApprovalAction(
                                    decision="reject",
                                    guidance_text="Add more detail",
                                ),
                            )
                        else:
                            # Second: approve
                            queue.resolve(
                                req.id,
                                ApprovalAction(decision="approve"),
                            )

        approver = asyncio.create_task(_reject_then_approve())
        result = await interceptor.execute_with_autonomy(
            stage_name="issue_spot",
            execute_fn=_execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        approver.cancel()
        # execute_fn called once in the re-run (initial checkpoint waits without executing)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_reject_exhausted_skips(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock,
    ) -> None:
        """After 2 rejected re-runs, stage is skipped."""
        async def _execute_fn(**kwargs: object) -> dict:
            return {"result": "attempt"}

        config = AutonomyConfig.professional_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        async def _always_reject() -> None:
            seen: set[int] = set()
            for _ in range(60):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    if req.id not in seen:
                        seen.add(req.id)
                        try:
                            queue.resolve(
                                req.id,
                                ApprovalAction(
                                    decision="reject",
                                    guidance_text="Not good enough",
                                ),
                            )
                        except (ValueError, KeyError):
                            pass

        approver = asyncio.create_task(_always_reject())
        result = await interceptor.execute_with_autonomy(
            stage_name="issue_spot",
            execute_fn=_execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        approver.cancel()
        assert result.get("skipped") is True
        assert "max_rejections_exceeded" in result.get("reason", "")


class TestEditApplies:
    """D-09: edit decision executes stage then applies edits to result."""

    @pytest.mark.asyncio
    async def test_edit_applies_modifications(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.professional_preset()
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        async def _edit() -> None:
            for _ in range(20):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    try:
                        queue.resolve(
                            req.id,
                            ApprovalAction(
                                decision="edit",
                                edits={"extra_field": "added_by_professional"},
                            ),
                        )
                    except (ValueError, KeyError):
                        pass

        approver = asyncio.create_task(_edit())
        result = await interceptor.execute_with_autonomy(
            stage_name="issue_spot",
            execute_fn=execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        approver.cancel()
        assert result["extra_field"] == "added_by_professional"
        assert result["claims"] == ["claim1"]  # Original preserved


class TestMidIntakeModSwitch:
    """D-05: config change takes effect at next stage boundary."""

    @pytest.mark.asyncio
    async def test_mid_intake_mode_switch(
        self, mock_audit_logger: MagicMock, mock_notification: MagicMock, execute_fn: AsyncMock,
    ) -> None:
        config = AutonomyConfig.chatbot_preset()  # Start all AUTO
        queue = ApprovalQueue()
        interceptor = AutonomyInterceptor(
            config=config,
            approval_queue=queue,
            audit_logger=mock_audit_logger,
            notification=mock_notification,
        )

        # First stage runs auto
        result = await interceptor.execute_with_autonomy(
            stage_name="issue_spot",
            execute_fn=execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        assert mock_notification.notify.await_count == 0

        # Switch to professional mid-intake
        interceptor.update_config(AutonomyConfig.professional_preset())

        # Next stage should now require approval
        async def _approve() -> None:
            for _ in range(20):
                await asyncio.sleep(0.02)
                for req in queue.get_pending():
                    try:
                        queue.resolve(req.id, ApprovalAction(decision="approve"))
                    except (ValueError, KeyError):
                        pass

        approver = asyncio.create_task(_approve())
        result = await interceptor.execute_with_autonomy(
            stage_name="explore",
            execute_fn=execute_fn,
            run_id=1,
            iteration_id=10,
            intake_id=100,
        )
        approver.cancel()
        assert mock_notification.notify.await_count == 1


class TestOrchestratorAcceptsInterceptor:
    """AnalysisOrchestrator.__init__ accepts optional autonomy_interceptor."""

    def test_orchestrator_accepts_autonomy_interceptor(self) -> None:
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        mock_db = MagicMock()
        mock_llm = MagicMock()
        mock_interceptor = MagicMock()

        orch = AnalysisOrchestrator(
            db_session=mock_db,
            llm_service=mock_llm,
            autonomy_interceptor=mock_interceptor,
        )
        assert orch._autonomy is mock_interceptor

    def test_orchestrator_works_without_interceptor(self) -> None:
        from app.services.analysis.orchestrator import AnalysisOrchestrator

        mock_db = MagicMock()
        mock_llm = MagicMock()

        orch = AnalysisOrchestrator(
            db_session=mock_db,
            llm_service=mock_llm,
        )
        assert orch._autonomy is None
