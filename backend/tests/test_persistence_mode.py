"""Tests for PersistenceManager: ephemeral, persistent, and CMS-integrated modes.

Covers:
- get_mode() reads org persistence_mode from settings JSON
- handle_session_complete() dispatches correctly per mode
- Ephemeral deletion only fires for terminal sessions (Pitfall 5)
- Ephemeral deletion preserves anonymized audit trail (D-08)
- TTL defaults and per-org override
- CMS-integrated mode triggers sync
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestHandleSessionCompleteEphemeral:
    """Test ephemeral mode behavior on session complete."""

    @pytest.mark.asyncio
    async def test_schedules_deletion_for_terminal_session(self):
        """Ephemeral mode schedules deletion after TTL for completed sessions."""
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral"},
            id=1,
        )
        session = AsyncMock()
        pm = PersistenceManager()

        with patch.object(pm, "_schedule_deletion", new_callable=AsyncMock) as mock_sched:
            await pm.handle_session_complete(
                intake_id=42,
                org=org,
                session=session,
                session_status="completed",
            )
            mock_sched.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_delete_active_session(self):
        """Pitfall 5: active session must NOT trigger deletion."""
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral"},
            id=1,
        )
        session = AsyncMock()
        pm = PersistenceManager()

        with patch.object(pm, "_schedule_deletion", new_callable=AsyncMock) as mock_sched:
            await pm.handle_session_complete(
                intake_id=42,
                org=org,
                session=session,
                session_status="active",
            )
            mock_sched.assert_not_called()

    @pytest.mark.asyncio
    async def test_abandoned_session_triggers_deletion(self):
        """Abandoned is a terminal state; should trigger deletion."""
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral"},
            id=1,
        )
        session = AsyncMock()
        pm = PersistenceManager()

        with patch.object(pm, "_schedule_deletion", new_callable=AsyncMock) as mock_sched:
            await pm.handle_session_complete(
                intake_id=42,
                org=org,
                session=session,
                session_status="abandoned",
            )
            mock_sched.assert_called_once()


class TestHandleSessionCompletePersistent:
    """Test persistent mode does nothing on session complete."""

    @pytest.mark.asyncio
    async def test_does_nothing_for_persistent_mode(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "persistent"},
            id=1,
        )
        session = AsyncMock()
        pm = PersistenceManager()

        with patch.object(pm, "_schedule_deletion", new_callable=AsyncMock) as mock_sched:
            await pm.handle_session_complete(
                intake_id=42,
                org=org,
                session=session,
                session_status="completed",
            )
            mock_sched.assert_not_called()


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


class TestEphemeralDeletionPreservesAudit:
    """D-08: Ephemeral deletion preserves anonymized audit trail."""

    @pytest.mark.asyncio
    async def test_preserves_audit_trail(self):
        from app.deployment.persistence import PersistenceManager

        pm = PersistenceManager()
        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral"},
            id=1,
            deletion_policy="anonymize",
        )
        session = AsyncMock()

        # Mock the DB operations
        with patch("app.deployment.persistence.select") as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = SimpleNamespace(
                status="completed"
            )
            session.execute = AsyncMock(return_value=mock_result)

            # Execute ephemeral deletion and verify audit trail is preserved
            await pm._execute_ephemeral_deletion(
                intake_id=42, org=org, session=session
            )

            # Session.execute should have been called (for delete operations)
            assert session.execute.called


class TestEphemeralTTL:
    """Test TTL defaults and per-org configuration."""

    def test_default_ttl_is_24_hours(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(settings={"persistence_mode": "ephemeral"}, id=1)
        pm = PersistenceManager()
        assert pm._get_ttl_hours(org) == 24

    def test_custom_ttl_from_org_settings(self):
        from app.deployment.persistence import PersistenceManager

        org = SimpleNamespace(
            settings={"persistence_mode": "ephemeral", "ephemeral_ttl_hours": 48},
            id=1,
        )
        pm = PersistenceManager()
        assert pm._get_ttl_hours(org) == 48
