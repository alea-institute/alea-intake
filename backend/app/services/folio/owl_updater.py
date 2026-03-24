"""OWL Update Manager -- background checking, idle-wait, and hot-reload.

Singleton service that orchestrates the FOLIO OWL update lifecycle:
1. ETag-based freshness check via ensure_owl_fresh
2. Wait for active analyses to finish (idle quiescence)
3. Hot-swap the FOLIO singleton with a freshly loaded instance
4. Rebuild embedding index if EmbeddingService has been initialized
"""

from __future__ import annotations

import asyncio
import logging
import threading

from folio import FOLIO

from app.config import get_settings
from app.services.folio.folio_service import reload_folio
from app.services.folio.owl_cache import ensure_owl_fresh

logger = logging.getLogger(__name__)


class OWLUpdateManager:
    """Singleton manager for FOLIO OWL ontology background updates."""

    _instance: OWLUpdateManager | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._active_count: int = 0
        self._count_lock = asyncio.Lock()
        self._idle_event = asyncio.Event()
        self._idle_event.set()  # starts idle

    @classmethod
    def get_instance(cls) -> OWLUpdateManager:
        """Return the singleton OWLUpdateManager, creating it on first call.

        Uses double-checked locking for thread safety.
        """
        if cls._instance is not None:
            return cls._instance
        with cls._instance_lock:
            if cls._instance is not None:
                return cls._instance
            cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    async def increment_active(self) -> None:
        """Increment active analysis counter (call before starting an analysis)."""
        async with self._count_lock:
            self._active_count += 1
            self._idle_event.clear()

    async def decrement_active(self) -> None:
        """Decrement active analysis counter (call after finishing an analysis)."""
        async with self._count_lock:
            self._active_count -= 1
            if self._active_count <= 0:
                self._active_count = 0
                self._idle_event.set()

    async def wait_for_idle(self, timeout: float = 300.0) -> bool:
        """Wait until all active analyses have completed.

        Args:
            timeout: Maximum seconds to wait. Defaults to 300 (5 minutes).

        Returns:
            True if idle state reached, False if timeout expired.
        """
        try:
            await asyncio.wait_for(self._idle_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def check_and_update(self) -> bool:
        """Check for OWL update and hot-swap FOLIO singleton if update available.

        Returns True if an update was applied, False if no update was needed.
        """
        loop = asyncio.get_event_loop()
        updated = await loop.run_in_executor(None, ensure_owl_fresh)

        if not updated:
            return False

        # Wait for active analyses to finish
        idle = await self.wait_for_idle()
        if not idle:
            logger.warning("Timeout waiting for idle; proceeding with reload")

        # Construct new FOLIO instance with fresh OWL
        settings = get_settings()
        new_folio = await loop.run_in_executor(
            None, lambda: FOLIO(github_repo_branch=settings.folio_owl_branch)
        )
        reload_folio(new_folio)

        # Rebuild embedding index if EmbeddingService has been initialized (Plan 02-02)
        try:
            from app.services.embedding.service import EmbeddingService

            emb_service = EmbeddingService.get_instance()
            if emb_service is not None:
                await emb_service.rebuild_index(new_folio)
                logger.info("Embedding index rebuilt after OWL update")
        except (ImportError, Exception) as e:
            logger.debug("Skipping embedding rebuild: %s", e)

        return True


async def _periodic_owl_check(manager: OWLUpdateManager, interval_hours: int = 24) -> None:
    """Background task that periodically checks for OWL updates.

    Runs indefinitely, sleeping for the configured interval between checks.

    Args:
        manager: The OWLUpdateManager instance to use.
        interval_hours: Hours between update checks.
    """
    interval_seconds = interval_hours * 3600
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            updated = await manager.check_and_update()
            if updated:
                logger.info("FOLIO OWL updated and reloaded")
        except Exception:
            logger.exception("Error during periodic OWL check")
