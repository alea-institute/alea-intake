"""Persistence completion policies share the complete session purge."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.config import PersistenceMode


class TestPersistenceManagerGetMode:
    """Test PersistenceManager.get_mode() reads from org settings."""

    def test_returns_mode_from_org_settings(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral"},
            id=1,
        )
        pm = PersistenceManager()
        assert pm.get_mode(org) == PersistenceMode.EPHEMERAL

    def test_defaults_to_persistent_when_missing(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(settings={}, id=1)
        pm = PersistenceManager()
        assert pm.get_mode(org) == PersistenceMode.PERSISTENT

    def test_defaults_to_persistent_when_settings_none(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(settings=None, id=1)
        pm = PersistenceManager()
        assert pm.get_mode(org) == PersistenceMode.PERSISTENT


@pytest.mark.parametrize("status", ["completed", "abandoned"])
async def test_ephemeral_completion_uses_complete_purge(status):
    from app.deployment.persistence import PersistenceManager
    org = SimpleNamespace(settings={"persistence_mode": "ephemeral"}, id=1)
    session = AsyncMock()
    with patch("app.db.retention.purge_intake", new_callable=AsyncMock) as purge:
        await PersistenceManager().handle_session_complete(42, org, session, status)
        purge.assert_awaited_once_with(session, 42)


@pytest.mark.parametrize("mode,status", [("persistent", "completed"), ("ephemeral", "active")])
async def test_retained_and_active_sessions_do_not_purge(mode, status):
    from app.deployment.persistence import PersistenceManager
    org = SimpleNamespace(settings={"persistence_mode": mode}, id=1)
    with patch("app.db.retention.purge_intake", new_callable=AsyncMock) as purge:
        await PersistenceManager().handle_session_complete(42, org, AsyncMock(), status)
        purge.assert_not_awaited()


class TestHandleSessionCompleteCMSIntegrated:
    """Test CMS-integrated mode triggers sync."""

    @pytest.mark.asyncio
    async def test_triggers_cms_sync(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={
                "persistence_mode": "cms_integrated",
                "cms_connector": "clio",
            },
            id=1,
        )
        session = AsyncMock()
        pm = PersistenceManager()

        with patch.object(pm, "_enqueue_cms_sync", new_callable=AsyncMock) as mock_sync:
            await pm.handle_session_complete(
                intake_id=42,
                org=org,
                session=session,
                session_status="completed",
            )
            mock_sync.assert_called_once()
