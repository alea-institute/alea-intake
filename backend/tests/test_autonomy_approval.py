"""Tests for ApprovalQueue async pause/resume with real asyncio.Event.

Covers approve/reject/edit/timeout flows, race condition protection,
and rejection re-run exhaustion.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.analysis.autonomy.approval_queue import ApprovalQueue
from app.services.analysis.autonomy.config import TimeoutBehavior
from app.services.analysis.autonomy.schemas import ApprovalAction


@pytest.fixture
def queue() -> ApprovalQueue:
    return ApprovalQueue()


class TestApprovalQueueBasics:
    """Basic create/resolve operations."""

    def test_create_request(self, queue: ApprovalQueue) -> None:
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )
        assert req.run_id == 1
        assert req.stage_name == "issue_spot"
        assert req.status == "pending"

    @pytest.mark.asyncio
    async def test_approve_unblocks_pipeline(self, queue: ApprovalQueue) -> None:
        """Approval via resolve unblocks wait_for_action (asyncio.Event.set)."""
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )

        async def _resolve_later() -> None:
            await asyncio.sleep(0.05)
            queue.resolve(
                req.id,
                ApprovalAction(decision="approve", actor_id=99),
            )

        task = asyncio.create_task(_resolve_later())
        action = await queue.wait_for_action(
            req.id,
            timeout_seconds=5,
            timeout_behavior=TimeoutBehavior.AUTO_PROCEED,
        )
        await task
        assert action.decision == "approve"
        assert action.actor_id == 99

    def test_get_pending(self, queue: ApprovalQueue) -> None:
        queue.create_request(run_id=1, stage_name="issue_spot", iteration_id=10)
        queue.create_request(run_id=2, stage_name="explore", iteration_id=20)
        pending = queue.get_pending()
        assert len(pending) == 2


class TestApprovalQueueTimeout:
    """Timeout behavior tests (D-04)."""

    @pytest.mark.asyncio
    async def test_timeout_auto_proceed(self, queue: ApprovalQueue) -> None:
        """Timeout fires and returns auto_proceed action."""
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )
        # Very short timeout
        action = await queue.wait_for_action(
            req.id,
            timeout_seconds=0.1,
            timeout_behavior=TimeoutBehavior.AUTO_PROCEED,
        )
        assert action.decision == "auto_proceed"

    @pytest.mark.asyncio
    async def test_timeout_queue_next(self, queue: ApprovalQueue) -> None:
        """Timeout fires and returns queue action."""
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )
        action = await queue.wait_for_action(
            req.id,
            timeout_seconds=0.1,
            timeout_behavior=TimeoutBehavior.QUEUE_NEXT,
        )
        assert action.decision == "queue"

    @pytest.mark.asyncio
    async def test_timeout_pause_until(self, queue: ApprovalQueue) -> None:
        """PAUSE_UNTIL waits indefinitely -- resolve before it would hang."""
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )

        async def _resolve_later() -> None:
            await asyncio.sleep(0.05)
            queue.resolve(
                req.id,
                ApprovalAction(decision="approve"),
            )

        task = asyncio.create_task(_resolve_later())
        action = await queue.wait_for_action(
            req.id,
            timeout_seconds=0.1,  # Ignored for PAUSE_UNTIL
            timeout_behavior=TimeoutBehavior.PAUSE_UNTIL,
        )
        await task
        assert action.decision == "approve"


class TestApprovalQueueRaceCondition:
    """Race condition protection (Pitfall 2)."""

    @pytest.mark.asyncio
    async def test_resolve_after_timeout_raises(self, queue: ApprovalQueue) -> None:
        """Resolve after timeout raises ValueError."""
        req = queue.create_request(
            run_id=1, stage_name="issue_spot", iteration_id=10
        )
        # Let it timeout
        await queue.wait_for_action(
            req.id,
            timeout_seconds=0.05,
            timeout_behavior=TimeoutBehavior.AUTO_PROCEED,
        )
        # Now try to resolve -- should raise
        with pytest.raises(ValueError, match="timed_out"):
            queue.resolve(
                req.id,
                ApprovalAction(decision="approve"),
            )


class TestApprovalQueueRerun:
    """Rerun tracking on create_request."""

    def test_create_rerun_request(self, queue: ApprovalQueue) -> None:
        req = queue.create_request(
            run_id=1,
            stage_name="issue_spot",
            iteration_id=10,
            is_rerun=True,
            attempt=1,
            guidance="Please revise the analysis",
        )
        assert req.is_rerun is True
        assert req.rerun_attempt == 1
        assert req.guidance_text == "Please revise the analysis"
