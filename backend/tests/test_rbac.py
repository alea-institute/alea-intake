"""Tests for RBAC permission sets and FastAPI dependencies.

Includes both unit tests (permission sets, dependency factories)
and integration tests (endpoint-level RBAC enforcement).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from httpx import AsyncClient


class TestRolePermissions:
    """ROLE_PERMISSIONS should define correct permission sets for each role."""

    def test_admin_has_full_permissions(self):
        from app.core.permissions import ROLE_PERMISSIONS
        from app.models.user import Role

        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert "users.read" in admin_perms
        assert "users.write" in admin_perms
        assert "audit.read" in admin_perms
        assert "org.manage" in admin_perms
        assert "cases.read" in admin_perms
        assert "cases.write" in admin_perms
        assert "deletion.execute" in admin_perms

    def test_professional_has_case_permissions(self):
        from app.core.permissions import ROLE_PERMISSIONS
        from app.models.user import Role

        prof_perms = ROLE_PERMISSIONS[Role.PROFESSIONAL]
        assert "cases.read" in prof_perms
        assert "cases.write" in prof_perms
        assert "org.manage" not in prof_perms
        assert "deletion.execute" not in prof_perms

    def test_consumer_has_own_permissions_only(self):
        from app.core.permissions import ROLE_PERMISSIONS
        from app.models.user import Role

        consumer_perms = ROLE_PERMISSIONS[Role.CONSUMER]
        assert "cases.read.own" in consumer_perms
        assert "consent.manage.own" in consumer_perms
        assert "deletion.request" in consumer_perms
        # Consumer should NOT have full access
        assert "cases.read" not in consumer_perms
        assert "users.write" not in consumer_perms


class TestRequireRole:
    """require_role should enforce role-based access."""

    @pytest.mark.asyncio
    async def test_admin_passes_admin_check(self):
        from app.core.permissions import require_role
        from app.models.user import Role

        dep = require_role(Role.ADMIN)
        # Create a mock user with admin role
        mock_user = MagicMock()
        mock_user.role = Role.ADMIN.value
        # The dependency should not raise
        result = await dep(mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_consumer_fails_admin_check(self):
        from app.core.permissions import require_role
        from app.models.user import Role

        dep = require_role(Role.ADMIN)
        mock_user = MagicMock()
        mock_user.role = Role.CONSUMER.value
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_user)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_professional_fails_admin_check(self):
        from app.core.permissions import require_role
        from app.models.user import Role

        dep = require_role(Role.ADMIN)
        mock_user = MagicMock()
        mock_user.role = Role.PROFESSIONAL.value
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_user)
        assert exc_info.value.status_code == 403


class TestRequirePermission:
    """require_permission should check granular permissions."""

    @pytest.mark.asyncio
    async def test_admin_has_org_manage(self):
        from app.core.permissions import require_permission
        from app.models.user import Role

        dep = require_permission("org.manage")
        mock_user = MagicMock()
        mock_user.role = Role.ADMIN.value
        result = await dep(mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_consumer_lacks_org_manage(self):
        from app.core.permissions import require_permission
        from app.models.user import Role

        dep = require_permission("org.manage")
        mock_user = MagicMock()
        mock_user.role = Role.CONSUMER.value
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_user)
        assert exc_info.value.status_code == 403


class TestEndpointRBAC:
    """Integration tests for RBAC enforcement at the endpoint level."""

    @pytest.fixture
    async def admin_token(self, async_client: AsyncClient):
        """Register an admin user and return access token."""
        # Register as consumer first, then we'll need to handle role.
        # For integration testing, register a user then manually set role.
        # The auth service defaults to consumer, so we test admin via direct token creation.
        from app.core.security import create_access_token

        # We need an actual admin user in the DB for get_current_user to work.
        # Register a user first, then create a token for them with the admin role.
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin@example.com",
                "password": "AdminPass123!",
                "full_name": "Admin User",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        data = response.json()
        return data["access_token"]

    @pytest.fixture
    async def consumer_token(self, async_client: AsyncClient):
        """Register a consumer user and return access token."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "consumer@example.com",
                "password": "ConsumerPass123!",
                "full_name": "Consumer User",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        data = response.json()
        return data["access_token"]

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, async_client: AsyncClient):
        """Admin should be able to access GET /api/v1/users."""
        # Register user, then update their role to admin in the DB
        reg_response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "admin-list@example.com",
                "password": "AdminPass123!",
                "full_name": "Admin Lister",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        tokens = reg_response.json()

        # Decode token to get user_id
        from app.core.security import decode_token, create_access_token

        payload = decode_token(
            tokens["access_token"],
            "test-secret-key-for-testing-only-not-production",
        )
        user_id = int(payload["sub"])

        # Update user role to admin directly in DB
        from sqlalchemy import text, update
        from app.db.engine import get_engine
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.user import User

        engine = get_engine()
        async with engine.connect() as conn:
            conn = await conn.execution_options(
                schema_translate_map={"tenant": None, "shared": None}
            )
            await conn.execute(
                update(User).where(User.id == user_id).values(role="admin")
            )
            await conn.commit()

        # Create admin token matching the DB role
        admin_token = create_access_token(
            user_id=user_id,
            org_id=int(payload["org"]),
            role="admin",
            secret_key="test-secret-key-for-testing-only-not-production",
        )

        response = await async_client.get(
            "/api/v1/users",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_consumer_cannot_list_users(self, async_client: AsyncClient, consumer_token):
        """Consumer should get 403 on GET /api/v1/users."""
        response = await async_client.get(
            "/api/v1/users",
            headers={
                "Authorization": f"Bearer {consumer_token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions for this action"

    @pytest.mark.asyncio
    async def test_consumer_can_read_own_profile(self, async_client: AsyncClient, consumer_token):
        """Consumer should access GET /api/v1/users/me."""
        response = await async_client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {consumer_token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "consumer@example.com"

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, async_client: AsyncClient):
        """No token should return 401 on protected endpoints."""
        response = await async_client.get(
            "/api/v1/users/me",
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 401
