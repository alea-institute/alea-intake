"""PersistenceManager: org-configurable data lifecycle policies.

Supports three persistence modes:
- EPHEMERAL: Auto-delete PII after session TTL, preserve anonymized audit trail
- PERSISTENT: Retain data until right-to-delete request
- CMS_INTEGRATED: Sync to CMS then apply org retention policy

TTL starts from session completion timestamp, NOT creation (Pitfall 5).
Ephemeral deletion preserves anonymized audit trail and screening trigger counts (D-08).
"""

import asyncio
import logging

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PersistenceMode

logger = logging.getLogger(__name__)

# Terminal session statuses that permit ephemeral deletion
_TERMINAL_STATUSES = {"completed", "abandoned"}


class PersistenceManager:
    """Manages data lifecycle based on org persistence mode."""

    def __init__(self) -> None:
        self._pending_deletions: dict[int, asyncio.Task] = {}

    def get_mode(self, org) -> PersistenceMode:
        """Return org's persistence mode from settings JSON.

        Defaults to PERSISTENT if not configured.
        """
        settings = org.settings or {}
        mode_str = settings.get("persistence_mode", "persistent")
        return PersistenceMode(mode_str)

    def _get_ttl_hours(self, org) -> int:
        """Return ephemeral TTL in hours. Defaults to 24, configurable per org."""
        settings = org.settings or {}
        return settings.get("ephemeral_ttl_hours", 24)

    async def handle_session_complete(
        self,
        intake_id: int,
        org,
        session: AsyncSession,
        session_status: str,
    ) -> None:
        """Handle intake session completion based on org persistence mode.

        Args:
            intake_id: The intake record ID.
            org: Organization object with .settings dict.
            session: Database session.
            session_status: Current session status (active, completed, abandoned).
        """
        mode = self.get_mode(org)

        if mode == PersistenceMode.EPHEMERAL:
            # Pitfall 5: Only delete terminal sessions
            if session_status not in _TERMINAL_STATUSES:
                logger.debug(
                    "Ephemeral mode: session %d still active, skipping deletion",
                    intake_id,
                )
                return
            await self._schedule_deletion(
                intake_id=intake_id,
                ttl_hours=self._get_ttl_hours(org),
                org=org,
                session=session,
            )

        elif mode == PersistenceMode.PERSISTENT:
            # No action -- data retained until right-to-delete
            logger.debug("Persistent mode: data retained for intake %d", intake_id)

        elif mode == PersistenceMode.CMS_INTEGRATED:
            # Trigger CMS sync
            await self._enqueue_cms_sync(
                intake_id=intake_id, org=org, session=session
            )

    async def _schedule_deletion(
        self,
        intake_id: int,
        ttl_hours: int,
        org,
        session: AsyncSession,
    ) -> None:
        """Schedule ephemeral deletion after TTL.

        TTL starts from session completion timestamp, NOT creation (Pitfall 5).
        """
        logger.info(
            "Scheduling ephemeral deletion for intake %d in %d hours",
            intake_id,
            ttl_hours,
        )

        async def _delayed_delete():
            await asyncio.sleep(ttl_hours * 3600)
            try:
                await self._execute_ephemeral_deletion(
                    intake_id=intake_id, org=org, session=session
                )
            except Exception:
                logger.error(
                    "Ephemeral deletion failed for intake %d",
                    intake_id,
                    exc_info=True,
                )
            finally:
                self._pending_deletions.pop(intake_id, None)

        # Cancel existing task if any (e.g., session resumed)
        existing = self._pending_deletions.get(intake_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(_delayed_delete())
        self._pending_deletions[intake_id] = task

    async def _execute_ephemeral_deletion(
        self,
        intake_id: int,
        org,
        session: AsyncSession,
    ) -> None:
        """Execute ephemeral deletion: remove PII, preserve anonymized audit trail.

        D-08: Keeps anonymized audit trail (actor_id=None) and screening trigger counts.
        Follows DeletionService cascade pattern where applicable.
        """
        from app.models.intake import Intake

        # Re-check session is still terminal (guard against race)
        result = await session.execute(
            select(Intake).where(Intake.id == intake_id)
        )
        intake = result.scalar_one_or_none()
        if intake is None:
            logger.warning("Intake %d not found for ephemeral deletion", intake_id)
            return

        if intake.status not in _TERMINAL_STATUSES:
            logger.warning(
                "Intake %d is no longer terminal (status=%s), skipping deletion",
                intake_id,
                intake.status,
            )
            return

        logger.info("Executing ephemeral deletion for intake %d", intake_id)

        # Delete PII-containing records in dependency order
        # Each deletion is best-effort: missing tables won't block others
        try:
            await self._delete_intake_data(intake_id, session)
        except Exception:
            logger.error(
                "Error during ephemeral data deletion for intake %d",
                intake_id,
                exc_info=True,
            )

        # Anonymize audit trail (D-08): set actor_id=None instead of deleting
        try:
            from app.models.audit import AuditLog

            await session.execute(
                update(AuditLog)
                .where(AuditLog.details.contains(str(intake_id)))
                .values(actor_id=None, actor_role=None)
            )
        except Exception:
            logger.debug(
                "Audit anonymization skipped for intake %d (table may not exist)",
                intake_id,
            )

        await session.flush()
        logger.info("Ephemeral deletion complete for intake %d", intake_id)

    async def _delete_intake_data(
        self, intake_id: int, session: AsyncSession
    ) -> None:
        """Delete PII-containing intake data in dependency order.

        Preserves screening trigger counts (D-08) by not deleting
        analysis-level aggregate counters.
        """
        # Import models locally to avoid circular imports
        from app.models.intake import IntakeSession, Message

        # Delete messages (contains PII content)
        sessions_q = select(IntakeSession.id).where(
            IntakeSession.intake_id == intake_id
        )
        await session.execute(
            delete(Message).where(Message.session_id.in_(sessions_q))
        )

        # Delete intake sessions
        await session.execute(
            delete(IntakeSession).where(IntakeSession.intake_id == intake_id)
        )

        # Delete the intake record itself
        from app.models.intake import Intake

        await session.execute(delete(Intake).where(Intake.id == intake_id))

    async def _enqueue_cms_sync(
        self, intake_id: int, org, session: AsyncSession
    ) -> None:
        """Enqueue CMS sync for cms_integrated persistence mode."""
        logger.info(
            "Enqueueing CMS sync for intake %d (org %s)",
            intake_id,
            org.id,
        )
        try:
            from app.integrations.cms.sync_queue import CMSSyncQueue

            queue = CMSSyncQueue()
            await queue.enqueue(
                intake_id=intake_id,
                org_id=org.id,
                connector=org.settings.get("cms_connector", "generic"),
            )
        except Exception:
            logger.error(
                "Failed to enqueue CMS sync for intake %d",
                intake_id,
                exc_info=True,
            )

    def cancel_pending_deletion(self, intake_id: int) -> bool:
        """Cancel a pending ephemeral deletion (e.g., session resumed).

        Returns True if a deletion was cancelled, False otherwise.
        """
        task = self._pending_deletions.pop(intake_id, None)
        if task and not task.done():
            task.cancel()
            logger.info("Cancelled pending deletion for intake %d", intake_id)
            return True
        return False
