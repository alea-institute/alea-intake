"""Tests for TenantProvisioner: schema creation, protocol seeding, admin user.

Covers:
- Multi-tenant provisioning creates DB schema
- Single-tenant provisioning skips schema creation
- Admin user creation with credentials
- Self-service vs admin-approval signup modes
- Default screening protocol seeding
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import DeploymentMode


class TestProvisionTenantMultiTenant:
    """Test provisioning in multi-tenant mode."""

    @pytest.mark.asyncio
    async def test_creates_db_schema(self):
        """Multi-tenant provisioning creates tenant_{slug} schema."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()
        # Mock the execute to return a result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        provisioner = TenantProvisioner(
            session=session, deployment_mode=DeploymentMode.MULTI_TENANT
        )

        with (
            patch.object(provisioner, "_create_schema", new_callable=AsyncMock) as mock_create,
            patch.object(provisioner, "_run_tenant_migration", new_callable=AsyncMock) as mock_migrate,
            patch.object(provisioner, "_seed_screening_protocols", new_callable=AsyncMock),
            patch.object(provisioner, "_create_admin_user", new_callable=AsyncMock, return_value={"user_id": 1, "password": "abc123"}),
            patch.object(provisioner, "_create_org_record", new_callable=AsyncMock, return_value=SimpleNamespace(id=1, slug="acme")),
            patch.object(provisioner, "_create_org_config", new_callable=AsyncMock),
        ):
            result = await provisioner.provision_tenant(
                name="Acme Law", slug="acme", admin_email="admin@acme.com", admin_name="Admin"
            )

            mock_create.assert_called_once_with("acme")
            mock_migrate.assert_called_once_with("acme")
            assert result["slug"] == "acme"

    @pytest.mark.asyncio
    async def test_seeds_default_protocols(self):
        """Provisioning seeds default screening protocols."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        provisioner = TenantProvisioner(
            session=session, deployment_mode=DeploymentMode.MULTI_TENANT
        )

        with (
            patch.object(provisioner, "_create_schema", new_callable=AsyncMock),
            patch.object(provisioner, "_run_tenant_migration", new_callable=AsyncMock),
            patch.object(provisioner, "_seed_screening_protocols", new_callable=AsyncMock) as mock_seed,
            patch.object(provisioner, "_create_admin_user", new_callable=AsyncMock, return_value={"user_id": 1, "password": "abc"}),
            patch.object(provisioner, "_create_org_record", new_callable=AsyncMock, return_value=SimpleNamespace(id=1, slug="acme")),
            patch.object(provisioner, "_create_org_config", new_callable=AsyncMock),
        ):
            await provisioner.provision_tenant(
                name="Acme Law", slug="acme", admin_email="admin@acme.com", admin_name="Admin"
            )

            mock_seed.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_admin_user_and_returns_credentials(self):
        """Provisioning creates admin user and returns credentials."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        provisioner = TenantProvisioner(
            session=session, deployment_mode=DeploymentMode.MULTI_TENANT
        )

        with (
            patch.object(provisioner, "_create_schema", new_callable=AsyncMock),
            patch.object(provisioner, "_run_tenant_migration", new_callable=AsyncMock),
            patch.object(provisioner, "_seed_screening_protocols", new_callable=AsyncMock),
            patch.object(
                provisioner,
                "_create_admin_user",
                new_callable=AsyncMock,
                return_value={"user_id": 99, "password": "s3cret"},
            ),
            patch.object(provisioner, "_create_org_record", new_callable=AsyncMock, return_value=SimpleNamespace(id=10, slug="acme")),
            patch.object(provisioner, "_create_org_config", new_callable=AsyncMock),
        ):
            result = await provisioner.provision_tenant(
                name="Acme Law", slug="acme", admin_email="admin@acme.com", admin_name="Admin"
            )

            assert result["admin_user_id"] == 99
            assert result["admin_password"] == "s3cret"
            assert result["org_id"] == 10


class TestProvisionTenantSingleTenant:
    """Test provisioning in single-tenant mode."""

    @pytest.mark.asyncio
    async def test_skips_schema_creation(self):
        """Single-tenant provisioning skips CREATE SCHEMA."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        provisioner = TenantProvisioner(
            session=session, deployment_mode=DeploymentMode.SINGLE_TENANT
        )

        with (
            patch.object(provisioner, "_create_schema", new_callable=AsyncMock) as mock_create,
            patch.object(provisioner, "_run_tenant_migration", new_callable=AsyncMock) as mock_migrate,
            patch.object(provisioner, "_seed_screening_protocols", new_callable=AsyncMock),
            patch.object(provisioner, "_create_admin_user", new_callable=AsyncMock, return_value={"user_id": 1, "password": "abc"}),
            patch.object(provisioner, "_create_org_record", new_callable=AsyncMock, return_value=SimpleNamespace(id=1, slug="default")),
            patch.object(provisioner, "_create_org_config", new_callable=AsyncMock),
        ):
            result = await provisioner.provision_tenant(
                name="My Firm", slug="default", admin_email="admin@firm.com", admin_name="Admin"
            )

            # Schema creation and migration should NOT be called
            mock_create.assert_not_called()
            mock_migrate.assert_not_called()


class TestSignupModes:
    """Test self-service vs admin-approval signup modes (D-10)."""

    @pytest.mark.asyncio
    async def test_signup_mode_from_settings(self):
        """signup_mode reads from settings.tenant_signup_mode."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()

        with patch("app.deployment.provisioning.get_settings") as mock_gs:
            mock_gs.return_value.tenant_signup_mode = "self_service"
            provisioner = TenantProvisioner(
                session=session, deployment_mode=DeploymentMode.MULTI_TENANT
            )
            assert provisioner.signup_mode == "self_service"

    @pytest.mark.asyncio
    async def test_approve_tenant_marks_active(self):
        """approve_tenant() marks org as active for admin-approval mode."""
        from app.deployment.provisioning import TenantProvisioner

        session = AsyncMock()
        mock_result = MagicMock()
        mock_org = SimpleNamespace(id=1, slug="pending-co", is_active=False)
        mock_result.scalar_one_or_none.return_value = mock_org
        session.execute = AsyncMock(return_value=mock_result)

        provisioner = TenantProvisioner(
            session=session, deployment_mode=DeploymentMode.MULTI_TENANT
        )

        await provisioner.approve_tenant(org_id=1)

        # Should have set is_active to True
        assert mock_org.is_active is True
