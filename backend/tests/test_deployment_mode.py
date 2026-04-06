"""Tests for deployment mode branching and auto-migration runner.

Covers:
- get_deployment_mode() returns correct mode from settings
- is_multi_tenant() convenience helper
- get_schema_translate_map() for both deployment modes
- TenantMiddleware single-tenant bypass
- run_startup_migrations() for both modes with failure isolation
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import DeploymentMode, Settings


# ---------------------------------------------------------------------------
# Deployment mode helpers
# ---------------------------------------------------------------------------


class TestGetDeploymentMode:
    """Test get_deployment_mode() reads from settings."""

    def test_returns_multi_tenant_when_configured(self, monkeypatch):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.MULTI_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import get_deployment_mode

            assert get_deployment_mode() == DeploymentMode.MULTI_TENANT

    def test_returns_single_tenant_when_configured(self, monkeypatch):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.SINGLE_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import get_deployment_mode

            assert get_deployment_mode() == DeploymentMode.SINGLE_TENANT


class TestIsMultiTenant:
    """Test is_multi_tenant() convenience helper."""

    def test_true_for_multi_tenant(self):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.MULTI_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import is_multi_tenant

            assert is_multi_tenant() is True

    def test_false_for_single_tenant(self):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.SINGLE_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import is_multi_tenant

            assert is_multi_tenant() is False


class TestGetSchemaTranslateMap:
    """Test get_schema_translate_map() for both deployment modes."""

    def test_multi_tenant_returns_schema_mapping(self):
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.MULTI_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import get_schema_translate_map

            result = get_schema_translate_map("acme")
            assert result == {"tenant": "tenant_acme", "shared": "shared"}

    def test_single_tenant_returns_none_mapping(self):
        """Pitfall 7: single-tenant uses public schema with no prefixes."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.SINGLE_TENANT
        with patch("app.deployment.mode.get_settings", return_value=mock_settings):
            from app.deployment.mode import get_schema_translate_map

            result = get_schema_translate_map()
            assert result == {"tenant": None, "shared": None}


# ---------------------------------------------------------------------------
# TenantMiddleware mode-aware behavior
# ---------------------------------------------------------------------------


class TestTenantMiddlewareModeAware:
    """Test TenantMiddleware dispatches differently based on deployment mode."""

    @pytest.mark.asyncio
    async def test_single_tenant_skips_resolution(self):
        """In single-tenant mode, all requests pass through without tenant ID."""
        with patch("app.middleware.tenant.is_multi_tenant", return_value=False):
            from app.middleware.tenant import TenantMiddleware

            app = MagicMock()
            middleware = TenantMiddleware(app)

            request = MagicMock()
            request.url.path = "/api/v1/intake/sessions"
            request.headers = {}
            request.state = SimpleNamespace()

            next_response = MagicMock()
            call_next = AsyncMock(return_value=next_response)

            response = await middleware.dispatch(request, call_next)

            # Should pass through without error
            call_next.assert_called_once_with(request)
            assert request.state.tenant_schema is None
            assert request.state.tenant_slug == "default"

    @pytest.mark.asyncio
    async def test_multi_tenant_requires_identification(self):
        """In multi-tenant mode, missing tenant header returns 400."""
        with patch("app.middleware.tenant.is_multi_tenant", return_value=True):
            from app.middleware.tenant import TenantMiddleware

            app = MagicMock()
            middleware = TenantMiddleware(app)

            request = MagicMock()
            request.url.path = "/api/v1/intake/sessions"
            request.headers = {}
            request.state = SimpleNamespace()

            call_next = AsyncMock()

            response = await middleware.dispatch(request, call_next)

            # Should return 400 error
            assert response.status_code == 400
            call_next.assert_not_called()


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


class TestRunStartupMigrations:
    """Test run_startup_migrations() for both deployment modes."""

    @pytest.mark.asyncio
    async def test_single_tenant_runs_upgrade_head(self):
        """Single-tenant: runs alembic upgrade head once."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.SINGLE_TENANT

        with (
            patch("app.deployment.migration_runner.get_settings", return_value=mock_settings),
            patch("app.deployment.migration_runner.subprocess") as mock_subprocess,
            patch("app.deployment.migration_runner.is_multi_tenant", return_value=False),
            patch.dict("os.environ", {"ALEA_SKIP_MIGRATIONS": ""}, clear=False),
        ):
            mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            from app.deployment.migration_runner import run_startup_migrations

            await run_startup_migrations()

            # Should have called alembic upgrade head exactly once
            mock_subprocess.run.assert_called_once()
            call_args = mock_subprocess.run.call_args
            assert "upgrade" in call_args[0][0]
            assert "head" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_multi_tenant_runs_shared_then_tenant_schemas(self):
        """Pitfall 1: Multi-tenant runs shared schema first, then each tenant."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.MULTI_TENANT

        mock_orgs = [
            SimpleNamespace(slug="acme"),
            SimpleNamespace(slug="globex"),
        ]

        with (
            patch("app.deployment.migration_runner.get_settings", return_value=mock_settings),
            patch("app.deployment.migration_runner.subprocess") as mock_subprocess,
            patch("app.deployment.migration_runner.is_multi_tenant", return_value=True),
            patch("app.deployment.migration_runner._get_active_orgs", return_value=mock_orgs),
            patch.dict("os.environ", {"ALEA_SKIP_MIGRATIONS": ""}, clear=False),
        ):
            mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            from app.deployment.migration_runner import run_startup_migrations

            await run_startup_migrations()

            # 1 shared + 2 tenant = 3 calls
            assert mock_subprocess.run.call_count == 3

            # First call: shared schema (no -x tenant=...)
            first_call = mock_subprocess.run.call_args_list[0][0][0]
            assert "upgrade" in first_call
            assert "head" in first_call
            # Should NOT have -x tenant= for shared
            assert "-x" not in first_call or "tenant=" not in str(first_call)

    @pytest.mark.asyncio
    async def test_migration_failure_isolation(self):
        """One tenant schema failing does not block other tenants."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.deployment_mode = DeploymentMode.MULTI_TENANT

        mock_orgs = [
            SimpleNamespace(slug="acme"),
            SimpleNamespace(slug="broken"),
            SimpleNamespace(slug="globex"),
        ]

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            if "tenant_broken" in str(cmd):
                result.returncode = 1
                result.stderr = "migration error"
                result.stdout = ""
            else:
                result.returncode = 0
                result.stderr = ""
                result.stdout = ""
            return result

        with (
            patch("app.deployment.migration_runner.get_settings", return_value=mock_settings),
            patch("app.deployment.migration_runner.subprocess") as mock_subprocess,
            patch("app.deployment.migration_runner.is_multi_tenant", return_value=True),
            patch("app.deployment.migration_runner._get_active_orgs", return_value=mock_orgs),
            patch.dict("os.environ", {"ALEA_SKIP_MIGRATIONS": ""}, clear=False),
        ):
            mock_subprocess.run.side_effect = mock_run

            from app.deployment.migration_runner import run_startup_migrations

            # Should NOT raise despite broken tenant
            result = await run_startup_migrations()

            # All 4 calls should have been made (1 shared + 3 tenants)
            assert mock_subprocess.run.call_count == 4

    @pytest.mark.asyncio
    async def test_skip_migrations_env_var(self):
        """ALEA_SKIP_MIGRATIONS=true skips all migrations."""
        with patch.dict("os.environ", {"ALEA_SKIP_MIGRATIONS": "true"}, clear=False):
            from app.deployment.migration_runner import run_startup_migrations

            # Should return without doing anything
            await run_startup_migrations()
