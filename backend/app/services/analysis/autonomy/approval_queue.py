"""In-memory approval queue with asyncio.Event pause/resume.

Each approval request gets an asyncio.Event that blocks the pipeline
until a professional resolves it. Race condition protection ensures
resolve after timeout raises ValueError (Pitfall 2).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.analysis.autonomy.config import TimeoutBehavior
from app.services.analysis.autonomy.schemas import ApprovalAction, ApprovalRequestSchema

logger = logging.getLogger(__name__)


class ApprovalQueue:
    """In-memory queue for autonomy approval gates.

    Each pending request stores:
    - schema: ApprovalRequestSchema
    - event: asyncio.Event (cleared = waiting, set = resolved)
    - action: ApprovalAction | None (set on resolve)
    - status: "pending" | "resolved" | "timed_out"
    """

    def __init__(self) -> None:
        self._next_id = 1
        # request_id -> (schema, event, action, status)
        self._pending: dict[
            int, tuple[ApprovalRequestSchema, asyncio.Event, ApprovalAction | None, str]
        ] = {}

    def create_request(
        self,
        run_id: int,
        stage_name: str,
        iteration_id: int,
        safety_triggered: bool = False,
        is_rerun: bool = False,
        attempt: int = 0,
        guidance: str | None = None,
    ) -> ApprovalRequestSchema:
        """Create a new approval request with a fresh asyncio.Event."""
        request_id = self._next_id
        self._next_id += 1

        schema = ApprovalRequestSchema(
            id=request_id,
            run_id=run_id,
            iteration_id=iteration_id,
            stage_name=stage_name,
            status="pending",
            safety_triggered=safety_triggered,
            is_rerun=is_rerun,
            rerun_attempt=attempt,
            guidance_text=guidance,
        )

        event = asyncio.Event()
        self._pending[request_id] = (schema, event, None, "pending")

        logger.debug(
            "Created approval request %d for stage %s (run=%d)",
            request_id,
            stage_name,
            run_id,
        )
        return schema

    async def wait_for_action(
        self,
        request_id: int,
        timeout_seconds: float,
        timeout_behavior: TimeoutBehavior,
    ) -> ApprovalAction:
        """Wait for a professional to resolve this request.

        Blocks via asyncio.Event.wait() until resolve() is called.
        On timeout, behavior depends on timeout_behavior:
        - AUTO_PROCEED: return auto_proceed action
        - QUEUE_NEXT: return queue action
        - PAUSE_UNTIL: ignore timeout, wait forever
        """
        entry = self._pending.get(request_id)
        if entry is None:
            raise KeyError(f"Request {request_id} not found")

        schema, event, _, _ = entry

        if timeout_behavior == TimeoutBehavior.PAUSE_UNTIL:
            # Wait indefinitely
            await event.wait()
        else:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                # Mark as timed out
                self._pending[request_id] = (
                    schema,
                    event,
                    None,
                    "timed_out",
                )
                logger.info(
                    "Approval request %d timed out (behavior=%s)",
                    request_id,
                    timeout_behavior.value,
                )

                if timeout_behavior == TimeoutBehavior.AUTO_PROCEED:
                    return ApprovalAction(decision="auto_proceed")
                elif timeout_behavior == TimeoutBehavior.QUEUE_NEXT:
                    return ApprovalAction(decision="queue")

        # Event was set -- retrieve the action
        entry = self._pending.get(request_id)
        if entry is None:
            raise KeyError(f"Request {request_id} disappeared")

        _, _, action, _ = entry
        if action is None:
            raise RuntimeError(f"Request {request_id} event set but no action")

        return action

    def resolve(self, request_id: int, action: ApprovalAction) -> None:
        """Resolve a pending request -- atomic status check (Pitfall 2).

        Raises ValueError if request already timed out.
        """
        entry = self._pending.get(request_id)
        if entry is None:
            raise KeyError(f"Request {request_id} not found")

        schema, event, _, status = entry

        if status == "timed_out":
            raise ValueError(
                f"Request {request_id} already timed_out -- cannot resolve"
            )

        if status == "resolved":
            raise ValueError(
                f"Request {request_id} already resolved"
            )

        # Atomically update
        self._pending[request_id] = (schema, event, action, "resolved")
        event.set()

        logger.debug(
            "Resolved approval request %d with decision=%s",
            request_id,
            action.decision,
        )

    def get_pending(self) -> list[ApprovalRequestSchema]:
        """Return all currently pending requests."""
        return [
            schema
            for schema, _, _, status in self._pending.values()
            if status == "pending"
        ]
