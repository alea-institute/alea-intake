"""Audit logger for autonomy events (D-10).

Records all autonomy-related events to the AutonomyEvent DB model
for full audit trail. Every event links to run_id and intake_id.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AutonomyAuditLogger:
    """Records autonomy events to the AutonomyEvent DB model."""

    def __init__(self, db_session: "AsyncSession") -> None:
        self._session = db_session

    async def log_event(
        self,
        run_id: int,
        intake_id: int,
        event_type: str,
        actor_id: int | None = None,
        stage_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Create an AutonomyEvent record."""
        from app.models.autonomy import AutonomyEvent

        event = AutonomyEvent(
            run_id=run_id,
            intake_id=intake_id,
            event_type=event_type,
            actor_id=actor_id,
            stage_name=stage_name,
            details_json=details,
        )
        self._session.add(event)
        await self._session.flush()

        logger.debug(
            "Logged autonomy event: type=%s stage=%s run=%d",
            event_type,
            stage_name,
            run_id,
        )

    async def log_checkpoint_reached(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
        safety_triggered: bool = False,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="checkpoint_reached",
            stage_name=stage_name,
            details={"safety_triggered": safety_triggered},
        )

    async def log_approved(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
        actor_id: int | None = None,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="approved",
            actor_id=actor_id,
            stage_name=stage_name,
        )

    async def log_rejected(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
        actor_id: int | None = None,
        guidance: str | None = None,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="rejected",
            actor_id=actor_id,
            stage_name=stage_name,
            details={"guidance": guidance},
        )

    async def log_edited(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
        actor_id: int | None = None,
        edits: dict | None = None,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="edited",
            actor_id=actor_id,
            stage_name=stage_name,
            details={"edits": edits},
        )

    async def log_auto_proceed(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="auto_proceed",
            stage_name=stage_name,
        )

    async def log_stage_skip(
        self,
        run_id: int,
        intake_id: int,
        stage_name: str,
        reason: str = "",
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="stage_skip",
            stage_name=stage_name,
            details={"reason": reason},
        )

    async def log_mode_change(
        self,
        run_id: int,
        intake_id: int,
        actor_id: int | None = None,
        old_config: dict | None = None,
        new_config: dict | None = None,
    ) -> None:
        await self.log_event(
            run_id=run_id,
            intake_id=intake_id,
            event_type="mode_change",
            actor_id=actor_id,
            details={"old_config": old_config, "new_config": new_config},
        )
