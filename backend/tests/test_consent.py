"""Tests for consent management: service, middleware enforcement, and API endpoints.

Covers consent grant, revoke, status check, enforcement middleware for AI
endpoints, and kiosk/anonymous session support.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import ConsentRecord


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "StrongPass123!"
) -> dict:
    """Register a user and return tokens."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    return resp.json()


async def _make_admin(client: AsyncClient, email: str) -> dict:
    """Register user, promote to admin via DB, re-login for correct JWT."""
    await _register_and_login(client, email)

    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS
    from sqlalchemy import update
    from app.models.user import User

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            await session.execute(
                update(User).where(User.email == email).values(role="admin")
            )
            await session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123!"},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    return resp.json()


def _auth_headers(tokens: dict) -> dict:
    """Build auth + tenant headers from token response."""
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }


# ── Direct service tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consent_service_grant(async_session: AsyncSession, test_org, test_user):
    """ConsentService.grant_consent creates a ConsentRecord."""
    from app.services.consent_service import ConsentService

    svc = ConsentService(async_session)
    record = await svc.grant_consent(
        user_id=test_user.id,
        session_id=None,
        consent_version="1.0",
        consent_items={"ai_processing": True, "data_sharing": False},
        ip_address="127.0.0.1",
    )

    assert record.id is not None
    assert record.user_id == test_user.id
    assert record.consent_version == "1.0"
    assert record.consent_items["ai_processing"] is True
    assert record.revoked_at is None


@pytest.mark.asyncio
async def test_consent_service_revoke(async_session: AsyncSession, test_org, test_user):
    """ConsentService.revoke_consent sets revoked_at on active consent."""
    from app.services.consent_service import ConsentService

    svc = ConsentService(async_session)
    await svc.grant_consent(
        user_id=test_user.id,
        session_id=None,
        consent_version="1.0",
        consent_items={"ai_processing": True},
    )

    revoked = await svc.revoke_consent(user_id=test_user.id)
    assert revoked is not None
    assert revoked.revoked_at is not None


@pytest.mark.asyncio
async def test_consent_service_check(async_session: AsyncSession, test_org, test_user):
    """ConsentService.check_consent returns True when ai_processing is granted."""
    from app.services.consent_service import ConsentService

    svc = ConsentService(async_session)

    # No consent yet
    assert await svc.check_consent(user_id=test_user.id) is False

    # Grant consent
    await svc.grant_consent(
        user_id=test_user.id,
        session_id=None,
        consent_version="1.0",
        consent_items={"ai_processing": True},
    )
    assert await svc.check_consent(user_id=test_user.id) is True

    # Revoke
    await svc.revoke_consent(user_id=test_user.id)
    assert await svc.check_consent(user_id=test_user.id) is False


# ── Integration tests via HTTP client ────────────────────────────────────────


@pytest.mark.asyncio
async def test_grant_consent(async_client: AsyncClient):
    """POST /api/v1/consent/grant with valid consent_items returns 201."""
    tokens = await _register_and_login(async_client, "consent_grant@example.com")

    resp = await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True, "data_sharing": False},
        },
        headers=_auth_headers(tokens),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["consent_version"] == "1.0"
    assert data["consent_items"]["ai_processing"] is True
    assert data["revoked_at"] is None


@pytest.mark.asyncio
async def test_revoke_consent(async_client: AsyncClient):
    """POST /api/v1/consent/revoke revokes active consent."""
    tokens = await _register_and_login(async_client, "consent_revoke@example.com")

    # Grant first
    await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True},
        },
        headers=_auth_headers(tokens),
    )

    # Revoke
    resp = await async_client.post(
        "/api/v1/consent/revoke",
        headers=_auth_headers(tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["revoked_at"] is not None


@pytest.mark.asyncio
async def test_consent_status(async_client: AsyncClient):
    """GET /api/v1/consent/status returns current consent state."""
    tokens = await _register_and_login(async_client, "consent_status@example.com")

    # No consent yet
    resp = await async_client.get(
        "/api/v1/consent/status",
        headers=_auth_headers(tokens),
    )
    assert resp.status_code == 200
    assert resp.json() is None or resp.json().get("revoked_at") is not None or resp.json() == {}

    # Grant consent
    await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True},
        },
        headers=_auth_headers(tokens),
    )

    resp2 = await async_client.get(
        "/api/v1/consent/status",
        headers=_auth_headers(tokens),
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["consent_version"] == "1.0"
    assert data["revoked_at"] is None


@pytest.mark.asyncio
async def test_consent_required_for_ai_endpoints(async_client: AsyncClient):
    """Without consent, access to /api/v1/analysis returns 403 with consent message."""
    tokens = await _register_and_login(async_client, "consent_block@example.com")

    resp = await async_client.get(
        "/api/v1/analysis/test",
        headers=_auth_headers(tokens),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Consent required before AI processing can begin"


@pytest.mark.asyncio
async def test_consent_not_required_for_auth(async_client: AsyncClient):
    """POST /api/v1/auth/login works without consent."""
    # Register + login should work without any consent
    tokens = await _register_and_login(async_client, "no_consent_auth@example.com")
    assert "access_token" in tokens


@pytest.mark.asyncio
async def test_revoked_consent_blocks_ai(async_client: AsyncClient):
    """After consent revocation, AI-processing endpoint returns 403."""
    tokens = await _register_and_login(async_client, "consent_revoked_block@example.com")

    # Grant consent
    await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True},
        },
        headers=_auth_headers(tokens),
    )

    # Revoke
    await async_client.post(
        "/api/v1/consent/revoke",
        headers=_auth_headers(tokens),
    )

    # AI endpoint should now be blocked
    resp = await async_client.get(
        "/api/v1/analysis/test",
        headers=_auth_headers(tokens),
    )
    assert resp.status_code == 403
    assert "revoked" in resp.json()["detail"].lower() or "consent" in resp.json()["detail"].lower()
