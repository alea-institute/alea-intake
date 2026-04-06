"""Tests for OWLUpdateManager singleton, active counting, idle wait, and check_and_update."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOWLUpdateManagerSingleton:
    """Tests for OWLUpdateManager singleton pattern."""

    def setup_method(self):
        from app.services.folio.owl_updater import OWLUpdateManager
        OWLUpdateManager.reset_instance()

    def teardown_method(self):
        from app.services.folio.owl_updater import OWLUpdateManager
        OWLUpdateManager.reset_instance()

    def test_get_instance_returns_same_instance(self):
        """OWLUpdateManager.get_instance() returns same instance on repeated calls."""
        from app.services.folio.owl_updater import OWLUpdateManager

        first = OWLUpdateManager.get_instance()
        second = OWLUpdateManager.get_instance()

        assert first is second

    @pytest.mark.asyncio
    async def test_increment_active_increases_count(self):
        """increment_active() increases active count."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()
        assert manager._active_count == 0

        await manager.increment_active()
        assert manager._active_count == 1

        await manager.increment_active()
        assert manager._active_count == 2

    @pytest.mark.asyncio
    async def test_decrement_active_decreases_count(self):
        """decrement_active() decreases active count."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()

        await manager.increment_active()
        await manager.increment_active()
        assert manager._active_count == 2

        await manager.decrement_active()
        assert manager._active_count == 1

    @pytest.mark.asyncio
    async def test_wait_for_idle_returns_immediately_when_idle(self):
        """wait_for_idle() returns immediately when active_count is 0."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()
        result = await manager.wait_for_idle(timeout=1.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_idle_blocks_until_count_zero(self):
        """wait_for_idle() blocks until active_count reaches 0."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()
        await manager.increment_active()

        async def decrement_later():
            await asyncio.sleep(0.1)
            await manager.decrement_active()

        task = asyncio.create_task(decrement_later())
        result = await manager.wait_for_idle(timeout=5.0)
        await task

        assert result is True
        assert manager._active_count == 0


class TestCheckAndUpdate:
    """Tests for OWLUpdateManager.check_and_update()."""

    def setup_method(self):
        from app.services.folio.owl_updater import OWLUpdateManager
        OWLUpdateManager.reset_instance()

    def teardown_method(self):
        from app.services.folio.owl_updater import OWLUpdateManager
        OWLUpdateManager.reset_instance()

    @pytest.mark.asyncio
    async def test_no_update_returns_false(self):
        """check_and_update returns False when ensure_owl_fresh returns False."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()

        with patch("app.services.folio.owl_updater.ensure_owl_fresh", return_value=False):
            result = await manager.check_and_update()

        assert result is False

    @pytest.mark.asyncio
    async def test_update_available_reloads_folio(self):
        """check_and_update returns True and reloads FOLIO when update available."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()
        mock_new_folio = MagicMock()

        with (
            patch("app.services.folio.owl_updater.ensure_owl_fresh", return_value=True),
            patch("app.services.folio.owl_updater.FOLIO", return_value=mock_new_folio),
            patch("app.services.folio.owl_updater.reload_folio") as mock_reload,
            patch("app.services.folio.owl_updater.get_settings") as mock_settings,
        ):
            mock_settings.return_value.folio_owl_branch = "main"
            result = await manager.check_and_update()

        assert result is True
        mock_reload.assert_called_once_with(mock_new_folio)

    @pytest.mark.asyncio
    async def test_update_rebuilds_embedding_index(self):
        """check_and_update calls EmbeddingService.rebuild_index after reload."""
        from app.services.folio.owl_updater import OWLUpdateManager

        manager = OWLUpdateManager.get_instance()
        mock_new_folio = MagicMock()
        mock_emb_service = MagicMock()
        mock_emb_service.rebuild_index = AsyncMock()

        with (
            patch("app.services.folio.owl_updater.ensure_owl_fresh", return_value=True),
            patch("app.services.folio.owl_updater.FOLIO", return_value=mock_new_folio),
            patch("app.services.folio.owl_updater.reload_folio"),
            patch("app.services.folio.owl_updater.get_settings") as mock_settings,
            patch.dict("sys.modules", {
                "app.services.embedding.service": MagicMock(
                    EmbeddingService=MagicMock(
                        get_instance=MagicMock(return_value=mock_emb_service)
                    )
                )
            }),
        ):
            mock_settings.return_value.folio_owl_branch = "main"
            result = await manager.check_and_update()

        assert result is True
        mock_emb_service.rebuild_index.assert_called_once_with(mock_new_folio)


class TestHealthEndpoint:
    """Tests for health endpoint FOLIO status integration."""

    @pytest.mark.asyncio
    async def test_health_returns_folio_key(self, async_client):
        """Health endpoint returns JSON with 'folio' key containing owl_status."""
        with patch("app.services.folio.owl_cache.get_settings") as mock_cache_settings:
            mock_cache_settings.return_value.folio_cache_dir = "/tmp/test_folio_cache"
            response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "folio_owl" in data
        assert "cached" in data["folio_owl"]


class TestLifespan:
    """Tests for lifespan FOLIO startup integration."""

    @pytest.mark.asyncio
    async def test_lifespan_calls_folio_startup(self):
        """Lifespan calls ensure_owl_fresh and get_folio during startup."""
        from app.main import lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()

        async def noop_periodic(*args, **kwargs):
            await asyncio.sleep(3600)

        with (
            patch("app.main.ensure_owl_fresh") as mock_ensure,
            patch("app.main.get_folio") as mock_get,
            patch("app.main.OWLUpdateManager") as mock_mgr_cls,
            patch("app.main.EmbeddingService") as mock_emb_cls,
            patch("app.main._periodic_owl_check", side_effect=noop_periodic),
            patch("app.main.get_engine"),
            patch("app.main.dispose_engine", new_callable=AsyncMock),
            patch("app.main.get_settings") as mock_settings,
            patch("app.main._seed_screening_protocols", new_callable=AsyncMock),
            patch("app.main.setup_telemetry"),
            patch("app.main.setup_prometheus"),
            patch("app.main.ResearchToolRegistry") as mock_registry,
            patch("app.main.CourtListenerAdapter"),
            patch("app.deployment.migration_runner.run_startup_migrations", new_callable=AsyncMock),
            patch("app.services.mcp.folio_mcp_client.FolioMCPClient") as mock_mcp,
            patch("app.integrations.cms.sync_queue.CMSSyncQueue") as mock_cms,
            patch("app.deployment.persistence.PersistenceManager") as mock_persist,
            patch("app.skills.registry.SkillsRegistry") as mock_skills,
        ):
            mock_s = MagicMock()
            mock_s.folio_update_interval_hours = 24
            mock_s.courtlistener_base_url = "https://api.courtlistener.com"
            mock_s.research_timeout_seconds = 30
            mock_s.deployment_mode = "single_tenant"
            mock_s.cms_sync_interval_seconds = 60
            mock_s.persistence_mode = "persistent"
            mock_s.skills_dir = "/tmp/skills"
            mock_s.cors_origins = ["http://localhost:5173"]
            mock_s.secret_key = "test-secret-key-32-characters!!"
            mock_s.otel_exporter_endpoint = ""
            mock_s.otel_service_name = "alea-intake"
            mock_s.rate_limit_default = "100/minute"
            mock_s.rate_limit_auth = "20/minute"
            mock_settings.return_value = mock_s
            mock_mgr_cls.get_instance.return_value = MagicMock()
            mock_emb_cls.get_instance.return_value = MagicMock()
            mock_registry.get_instance.return_value = MagicMock()
            mock_mcp.get_instance.return_value = MagicMock(connect=AsyncMock(), close=AsyncMock())
            mock_cms_inst = MagicMock()
            mock_cms_inst.start = AsyncMock()
            mock_cms_inst.stop = AsyncMock()
            mock_cms_inst.run_worker = AsyncMock()
            mock_cms.return_value = mock_cms_inst
            mock_persist.return_value = MagicMock(start=AsyncMock(), stop=AsyncMock())
            mock_skills.return_value = MagicMock(load_bundled=MagicMock())

            async with lifespan(mock_app):
                pass

            mock_ensure.assert_called_once()
            # get_folio is called twice: once in executor for initial load, once to retrieve instance
            assert mock_get.call_count == 2
