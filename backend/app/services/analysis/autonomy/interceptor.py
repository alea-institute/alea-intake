"""AutonomyInterceptor wrapping stage execution with checkpoint logic.

Gates every stage through the autonomy config: AUTO stages execute
immediately, CHECKPOINT stages pause for professional approval.
Safety alerts always force checkpoint regardless of config (D-02).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from app.services.analysis.autonomy.config import (
    AutonomyConfig,
    StageCheckpoint,
)
from app.services.analysis.autonomy.schemas import ApprovalAction

if TYPE_CHECKING:
    from app.services.analysis.autonomy.approval_queue import ApprovalQueue
    from app.services.analysis.autonomy.audit_logger import AutonomyAuditLogger
    from app.services.analysis.autonomy.notification import NotificationService

logger = logging.getLogger(__name__)


class AutonomyInterceptor:
    """Wraps stage execution with configurable autonomy checkpoints.

    Injected into AnalysisOrchestrator.__init__ as optional parameter.
    Config is mutable for mid-intake mode switching (D-05).
    """

    def __init__(
        self,
        config: AutonomyConfig,
        approval_queue: "ApprovalQueue",
        audit_logger: "AutonomyAuditLogger",
        notification: "NotificationService",
        session_id: int | None = None,
    ) -> None:
        self._config = config
        self._queue = approval_queue
        self._audit = audit_logger
        self._notification = notification
        self._session_id = session_id

    def update_config(self, new_config: AutonomyConfig) -> None:
        """Replace config mid-intake (D-05). Takes effect at next stage."""
        self._config = new_config

    async def execute_with_autonomy(
        self,
        stage_name: str,
        execute_fn: Callable[..., Coroutine[Any, Any, dict]],
        run_id: int,
        iteration_id: int,
        intake_id: int,
        safety_triggered: bool = False,
    ) -> dict:
        """Execute a stage with autonomy gating.

        Args:
            stage_name: Pipeline stage name (e.g. "issue_spot").
            execute_fn: Async callable that runs the stage and returns dict.
            run_id: AnalysisRun.id.
            iteration_id: AnalysisIteration.id.
            intake_id: Intake.id for audit trail.
            safety_triggered: Whether safety screening flagged this stage.

        Returns:
            Stage result dict (possibly edited by professional).
        """
        checkpoint = self._config.get_stage_checkpoint(stage_name)

        # D-02: Safety always forces checkpoint
        needs_approval = safety_triggered or checkpoint == StageCheckpoint.CHECKPOINT

        if not needs_approval:
            # AUTO: execute immediately
            return await execute_fn()

        # CHECKPOINT: create approval request, notify, wait
        request = self._queue.create_request(
            run_id=run_id,
            stage_name=stage_name,
            iteration_id=iteration_id,
            safety_triggered=safety_triggered,
        )

        await self._audit.log_checkpoint_reached(
            run_id=run_id,
            intake_id=intake_id,
            stage_name=stage_name,
            safety_triggered=safety_triggered,
        )

        if self._notification:
            await self._notification.notify(
                request=request,
                session_id=self._session_id or 0,
            )

        # Wait for professional action
        action = await self._queue.wait_for_action(
            request_id=request.id,
            timeout_seconds=self._config.timeout_seconds,
            timeout_behavior=self._config.timeout_behavior,
        )

        return await self._handle_action(
            action=action,
            stage_name=stage_name,
            execute_fn=execute_fn,
            run_id=run_id,
            iteration_id=iteration_id,
            intake_id=intake_id,
        )

    async def _handle_action(
        self,
        action: ApprovalAction,
        stage_name: str,
        execute_fn: Callable[..., Coroutine[Any, Any, dict]],
        run_id: int,
        iteration_id: int,
        intake_id: int,
    ) -> dict:
        """Handle the professional's decision on an approval request."""
        decision = action.decision

        if decision == "approve":
            await self._audit.log_approved(
                run_id=run_id,
                intake_id=intake_id,
                stage_name=stage_name,
                actor_id=action.actor_id,
            )
            return await execute_fn()

        elif decision == "reject":
            await self._audit.log_rejected(
                run_id=run_id,
                intake_id=intake_id,
                stage_name=stage_name,
                actor_id=action.actor_id,
                guidance=action.guidance_text,
            )
            return await self._handle_reject(
                stage_name=stage_name,
                execute_fn=execute_fn,
                action=action,
                run_id=run_id,
                iteration_id=iteration_id,
                intake_id=intake_id,
            )

        elif decision == "edit":
            await self._audit.log_edited(
                run_id=run_id,
                intake_id=intake_id,
                stage_name=stage_name,
                actor_id=action.actor_id,
                edits=action.edits,
            )
            result = await execute_fn()
            return self._apply_edits(result, action.edits or {})

        elif decision == "auto_proceed":
            await self._audit.log_auto_proceed(
                run_id=run_id,
                intake_id=intake_id,
                stage_name=stage_name,
            )
            return await execute_fn()

        elif decision == "queue":
            # Re-wait with no timeout (pause until resolved)
            logger.info("Request queued for stage %s, waiting indefinitely", stage_name)
            request = self._queue.create_request(
                run_id=run_id,
                stage_name=stage_name,
                iteration_id=iteration_id,
            )
            if self._notification:
                await self._notification.notify(
                    request=request,
                    session_id=self._session_id or 0,
                )
            from app.services.analysis.autonomy.config import TimeoutBehavior
            new_action = await self._queue.wait_for_action(
                request_id=request.id,
                timeout_seconds=0,
                timeout_behavior=TimeoutBehavior.PAUSE_UNTIL,
            )
            return await self._handle_action(
                action=new_action,
                stage_name=stage_name,
                execute_fn=execute_fn,
                run_id=run_id,
                iteration_id=iteration_id,
                intake_id=intake_id,
            )

        elif decision == "pause":
            # Wait indefinitely
            request = self._queue.create_request(
                run_id=run_id,
                stage_name=stage_name,
                iteration_id=iteration_id,
            )
            from app.services.analysis.autonomy.config import TimeoutBehavior
            new_action = await self._queue.wait_for_action(
                request_id=request.id,
                timeout_seconds=0,
                timeout_behavior=TimeoutBehavior.PAUSE_UNTIL,
            )
            return await self._handle_action(
                action=new_action,
                stage_name=stage_name,
                execute_fn=execute_fn,
                run_id=run_id,
                iteration_id=iteration_id,
                intake_id=intake_id,
            )

        else:
            logger.warning("Unknown decision %s, auto-proceeding", decision)
            return await execute_fn()

    async def _handle_reject(
        self,
        stage_name: str,
        execute_fn: Callable[..., Coroutine[Any, Any, dict]],
        action: ApprovalAction,
        run_id: int,
        iteration_id: int,
        intake_id: int,
        max_retries: int = 2,
    ) -> dict:
        """Handle rejection with re-run and guidance (D-08).

        Re-runs execute_fn with guidance, creates new approval request.
        After max_retries exhausted, logs stage_skip and returns skip result.
        """
        for attempt in range(1, max_retries + 1):
            # Re-run with guidance
            result = await execute_fn(guidance=action.guidance_text)

            # Create new approval request for the re-run
            request = self._queue.create_request(
                run_id=run_id,
                stage_name=stage_name,
                iteration_id=iteration_id,
                is_rerun=True,
                attempt=attempt,
                guidance=action.guidance_text,
            )

            if self._notification:
                await self._notification.notify(
                    request=request,
                    session_id=self._session_id or 0,
                )

            # Wait for next action
            new_action = await self._queue.wait_for_action(
                request_id=request.id,
                timeout_seconds=self._config.timeout_seconds,
                timeout_behavior=self._config.timeout_behavior,
            )

            if new_action.decision == "approve":
                await self._audit.log_approved(
                    run_id=run_id,
                    intake_id=intake_id,
                    stage_name=stage_name,
                    actor_id=new_action.actor_id,
                )
                return result

            elif new_action.decision == "edit":
                await self._audit.log_edited(
                    run_id=run_id,
                    intake_id=intake_id,
                    stage_name=stage_name,
                    actor_id=new_action.actor_id,
                    edits=new_action.edits,
                )
                return self._apply_edits(result, new_action.edits or {})

            elif new_action.decision == "reject":
                await self._audit.log_rejected(
                    run_id=run_id,
                    intake_id=intake_id,
                    stage_name=stage_name,
                    actor_id=new_action.actor_id,
                    guidance=new_action.guidance_text,
                )
                action = new_action  # Use new guidance for next attempt
                continue

            else:
                # auto_proceed or other: accept the result
                return result

        # Exhausted all retries
        await self._audit.log_stage_skip(
            run_id=run_id,
            intake_id=intake_id,
            stage_name=stage_name,
            reason="max_rejections_exceeded",
        )
        return {"skipped": True, "reason": "max_rejections_exceeded"}

    @staticmethod
    def _apply_edits(result: dict, edits: dict) -> dict:
        """Shallow merge edits into result (D-09)."""
        merged = dict(result)
        merged.update(edits)
        return merged
