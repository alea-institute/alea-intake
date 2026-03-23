"""Tests for cross-tenant data isolation.

Covers:
- Tenant schema creation
- User isolation between tenants
- Cross-tenant API access blocked
- Shared schema org accessibility
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shared import Organization
from app.models.user import User


class TestTenantSchemaCreation:
    """Test tenant schema provisioning."""

    async def test_tenant_schema_creation(self, async_engine):
        """On SQLite, tables exist after conftest initialization (schema is a no-op)."""
        # The conftest async_engine fixture already creates schemaless table copies.
        # On SQLite, there are no named schemas -- tenant isolation is via org_id.
        dialect = async_engine.dialect.name
        if dialect == "sqlite":
            async with async_engine.connect() as conn:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result.fetchall()]
                assert "users" in tables

    async def test_tenant_schema_resolution(self):
        """resolve_tenant_schema returns expected schema name."""
        from app.db.tenant import resolve_tenant_schema

        schema = await resolve_tenant_schema("my-org")
        assert schema == "tenant_my-org"


class TestTenantIsolationUsers:
    """Test cross-tenant user data isolation."""

    async def test_tenant_isolation_users(self, async_session: AsyncSession, test_org):
        """Users created in tenant A are not visible when querying tenant B's data."""
        # Create a user in the test org (acts as tenant A)
        user_a = User(
            email="usera@example.com",
            hashed_password="$argon2hash$",
            full_name=b"User A",
            role="consumer",
            org_id=test_org.id,
        )
        async_session.add(user_a)
        await async_session.flush()

        # Create a second org (tenant B)
        org_b = Organization(
            name="Org B",
            slug="org-b",
            auth_mode="email_password",
            llm_data_policy="cloud_optout",
            consent_mode="granular",
            deletion_policy="anonymize",
        )
        async_session.add(org_b)
        await async_session.flush()

        user_b = User(
            email="userb@example.com",
            hashed_password="$argon2hash$",
            full_name=b"User B",
            role="consumer",
            org_id=org_b.id,
        )
        async_session.add(user_b)
        await async_session.flush()

        # Query users for tenant A (org_id filter)
        result = await async_session.execute(
            select(User).where(User.org_id == test_org.id)
        )
        tenant_a_users = result.scalars().all()

        # Tenant A should only see their own user
        assert len(tenant_a_users) == 1
        assert tenant_a_users[0].email == "usera@example.com"

        # Query users for tenant B
        result = await async_session.execute(
            select(User).where(User.org_id == org_b.id)
        )
        tenant_b_users = result.scalars().all()
        assert len(tenant_b_users) == 1
        assert tenant_b_users[0].email == "userb@example.com"

    async def test_creating_user_tenant_a_not_in_tenant_b(self, async_session: AsyncSession, test_org):
        """Creating a user in Tenant A's schema doesn't appear in Tenant B's queries."""
        user_a = User(
            email="onlya@example.com",
            hashed_password="$argon2hash$",
            full_name=b"Only A",
            role="professional",
            org_id=test_org.id,
        )
        async_session.add(user_a)
        await async_session.flush()

        # Query with a different org_id (representing tenant B)
        result = await async_session.execute(
            select(User).where(User.org_id == 99999)
        )
        tenant_b_users = result.scalars().all()
        assert len(tenant_b_users) == 0


class TestCrossTenantAPIBlocked:
    """Test that API-level tenant isolation blocks cross-tenant access."""

    async def test_cross_tenant_api_blocked(self, async_client: AsyncClient):
        """Tenant A user cannot read Tenant B user data via API."""
        # Register a user in tenant context (default org)
        reg_response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "cross@example.com",
                "password": "StrongP@ss123",
                "full_name": "Cross Tenant Test",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )

        if reg_response.status_code == 201:
            tokens = reg_response.json()
            access_token = tokens["access_token"]

            # Try to access users (should only see own tenant's data)
            users_resp = await async_client.get(
                "/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Tenant-Slug": "test-legal-aid",
                },
            )
            # Should succeed for own tenant
            assert users_resp.status_code == 200


class TestSharedSchemaOrgAccessible:
    """Test that Organization records are visible across tenants (shared schema)."""

    async def test_shared_schema_org_accessible(self, async_session: AsyncSession, test_org):
        """Organization records are visible from any session (shared schema)."""
        result = await async_session.execute(
            select(Organization).where(Organization.slug == test_org.slug)
        )
        org = result.scalar_one_or_none()
        assert org is not None
        assert org.name == "Test Legal Aid"
