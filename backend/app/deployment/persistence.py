"""PersistenceManager: org-configurable data lifecycle policies.

Supports three persistence modes:
- EPHEMERAL: Delete the complete graph on session completion
- PERSISTENT: Retain data until right-to-delete request
- CMS_INTEGRATED: Sync to CMS then apply org retention policy

Ephemeral completion uses the same complete graph purge as the showcase.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PersistenceMode

logger = logging.getLogger(__name__)

# Terminal session statuses that permit ephemeral deletion
_TERMINAL_STATUSES = {"completed", "abandoned"}


class PersistenceManager:
    """Manages data lifecycle based on org persistence mode."""

    def get_mode(self, org) -> PersistenceMode:
        """Return org's persistence mode from settings JSON.

        Defaults to PERSISTENT if not configured.
        """
        settings = org.settings or {}
        mode_str = settings.get("persistence_mode", "persistent")
        return PersistenceMode(mode_str)

    async def handle_session_complete(self, intake_id, org, session, session_status):
        """Apply completion policy through the single graph-deletion owner."""
        mode = self.get_mode(org)
        if mode == PersistenceMode.EPHEMERAL and session_status in _TERMINAL_STATUSES:
            from app.db.retention import purge_intake
            await purge_intake(session, intake_id)
        elif mode == PersistenceMode.CMS_INTEGRATED:
            await self._enqueue_cms_sync(intake_id, org, session)

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
