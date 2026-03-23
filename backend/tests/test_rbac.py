"""Tests for RBAC permission sets and FastAPI dependencies.

TDD RED: These tests define the expected behavior of backend/app/core/permissions.py
before the implementation exists.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException


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
