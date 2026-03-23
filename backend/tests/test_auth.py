"""Integration tests for the auth API endpoints.

TDD RED: These tests define the expected behavior of the auth service and
router endpoints before the implementation exists.
"""

import pytest
from datetime import timedelta
from httpx import AsyncClient


@pytest.fixture
async def registered_user(async_client: AsyncClient):
    """Register a user and return the response data."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "StrongPass123!",
            "full_name": "Test User",
        },
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    assert response.status_code == 201
    return response.json()


class TestRegister:
    """POST /api/v1/auth/register should create users and return tokens."""

    @pytest.mark.asyncio
    async def test_register_success(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "StrongPass123!",
                "full_name": "New User",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client: AsyncClient):
        # Register first
        await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "StrongPass123!",
                "full_name": "First User",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        # Try registering again with same email
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "AnotherPass456!",
                "full_name": "Second User",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 409


class TestLogin:
    """POST /api/v1/auth/login should authenticate users."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client: AsyncClient, registered_user):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "StrongPass123!",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, async_client: AsyncClient, registered_user):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "WrongPassword!",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "SomePass123!",
            },
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"


class TestRefreshToken:
    """POST /api/v1/auth/refresh should rotate tokens."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, async_client: AsyncClient, registered_user):
        refresh_token = registered_user["refresh_token"]
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New tokens should differ from the old ones
        assert data["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_token_reuse_detection(self, async_client: AsyncClient, registered_user):
        old_refresh_token = registered_user["refresh_token"]

        # Use the refresh token once (valid)
        response1 = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response1.status_code == 200

        # Try to use the old refresh token again (reuse attack)
        response2 = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh_token},
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response2.status_code == 401


class TestLogout:
    """POST /api/v1/auth/logout should invalidate refresh tokens."""

    @pytest.mark.asyncio
    async def test_logout(self, async_client: AsyncClient, registered_user):
        access_token = registered_user["access_token"]
        refresh_token = registered_user["refresh_token"]

        # Logout
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert response.status_code == 200

        # Try to refresh after logout -- should fail
        response2 = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert response2.status_code == 401


class TestExpiredToken:
    """Expired access tokens should return 401 with specific message."""

    @pytest.mark.asyncio
    async def test_expired_access_token(self, async_client: AsyncClient):
        from app.core.security import create_access_token

        # Create an already-expired token
        token = create_access_token(
            user_id=1, org_id=1, role="consumer",
            secret_key="test-secret-key-for-testing-only-not-production",
            expires_delta=timedelta(seconds=-1),
        )
        response = await async_client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired. Please log in again."
