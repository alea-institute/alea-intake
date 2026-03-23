"""Tests for audit logging: service, middleware, and query endpoints.

Covers audit log creation, middleware integration, admin-only query access,
and filtering by action, actor, and date range.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


# ── Direct service tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_service_direct(async_session: AsyncSession):
    """AuditService.log_action creates an AuditLog record with all fields."""
    from app.services.audit_service import AuditService

    svc = AuditService(async_session)
    entry = await svc.log_action(
        action="user.login",
        actor_id=1,
        actor_role="admin",
        resource_type="user",
        resource_id=1,
        details={"method": "email_password"},
        ip_address="127.0.0.1",
        request_id=str(uuid.uuid4()),
    )

    assert entry.id is not None
    assert entry.action == "user.login"
    assert entry.actor_id == 1
    assert entry.actor_role == "admin"
    assert entry.resource_type == "user"
    assert entry.resource_id == 1
    assert entry.details == {"method": "email_password"}
    assert entry.ip_address == "127.0.0.1"
    assert entry.request_id is not None


@pytest.mark.asyncio
async def test_audit_service_query_logs(async_session: AsyncSession):
    """AuditService.query_logs returns filtered results ordered by timestamp DESC."""
    from app.services.audit_service import AuditService

    svc = AuditService(async_session)

    # Create multiple entries
    await svc.log_action(action="user.login", actor_id=1)
    await svc.log_action(action="user.register", actor_id=2)
    await svc.log_action(action="user.login", actor_id=3)

    # Query all
    all_logs = await svc.query_logs()
    assert len(all_logs) == 3

    # Filter by action
    login_logs = await svc.query_logs(action="user.login")
    assert len(login_logs) == 2
    assert all(log.action == "user.login" for log in login_logs)

    # Filter by actor_id
    actor_logs = await svc.query_logs(actor_id=2)
    assert len(actor_logs) == 1
    assert actor_logs[0].action == "user.register"


@pytest.mark.asyncio
async def test_audit_service_query_with_limit_offset(async_session: AsyncSession):
    """AuditService.query_logs respects limit and offset."""
    from app.services.audit_service import AuditService

    svc = AuditService(async_session)
    for i in range(5):
        await svc.log_action(action=f"action.{i}", actor_id=i)

    page1 = await svc.query_logs(limit=2, offset=0)
    assert len(page1) == 2

    page2 = await svc.query_logs(limit=2, offset=2)
    assert len(page2) == 2

    page3 = await svc.query_logs(limit=2, offset=4)
    assert len(page3) == 1


# ── Integration tests via HTTP client ────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str, password: str = "StrongPass123!") -> dict:
    """Helper: register a user and return tokens + user info."""
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
    """Helper: register user, promote to admin via DB, re-login for correct JWT."""
    tokens = await _register_and_login(client, email)

    # Promote to admin directly via DB
    import app.db.engine as engine_module

    engine = engine_module._engine
    from sqlalchemy.ext.asyncio import AsyncSession as AS
    from sqlalchemy import update
    from app.models.user import User

    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AS(bind=conn, expire_on_commit=False) as session:
            await session.execute(
                update(User).where(User.email == email).values(role="admin")
            )
            await session.commit()

    # Re-login to get token with refreshed role
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123!"},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    return resp.json()


@pytest.mark.asyncio
async def test_audit_log_created_on_login(async_client: AsyncClient):
    """After a POST /api/v1/auth/login, an AuditLog entry exists with action containing 'login'."""
    await _register_and_login(async_client, "audit_login@example.com")

    # Query audit logs as admin
    admin_tokens = await _make_admin(async_client, "audit_admin@example.com")

    resp = await async_client.get(
        "/api/v1/audit/",
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0

    # Check at least one entry contains a login-related action
    actions = [log["action"] for log in logs]
    assert any("login" in a for a in actions), f"No login action found in {actions}"


@pytest.mark.asyncio
async def test_audit_log_has_request_id(async_client: AsyncClient):
    """Audit log entries have non-null request_id from the middleware."""
    await _register_and_login(async_client, "reqid_user@example.com")
    admin_tokens = await _make_admin(async_client, "reqid_admin@example.com")

    resp = await async_client.get(
        "/api/v1/audit/",
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0
    # At least some entries should have request_id from middleware
    entries_with_request_id = [log for log in logs if log.get("request_id")]
    assert len(entries_with_request_id) > 0


@pytest.mark.asyncio
async def test_audit_log_has_ip_address(async_client: AsyncClient):
    """Audit log entries have ip_address field populated."""
    await _register_and_login(async_client, "ip_user@example.com")
    admin_tokens = await _make_admin(async_client, "ip_admin@example.com")

    resp = await async_client.get(
        "/api/v1/audit/",
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0
    entries_with_ip = [log for log in logs if log.get("ip_address")]
    assert len(entries_with_ip) > 0


@pytest.mark.asyncio
async def test_admin_can_query_audit_logs(async_client: AsyncClient):
    """Admin GET /api/v1/audit returns 200 with audit log entries."""
    admin_tokens = await _make_admin(async_client, "admin_query@example.com")

    resp = await async_client.get(
        "/api/v1/audit/",
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_consumer_cannot_query_audit_logs(async_client: AsyncClient):
    """Consumer GET /api/v1/audit returns 403."""
    consumer_tokens = await _register_and_login(async_client, "consumer_audit@example.com")

    resp = await async_client.get(
        "/api/v1/audit/",
        headers={
            "Authorization": f"Bearer {consumer_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_filter_by_action(async_client: AsyncClient):
    """GET /api/v1/audit?action=user.login filters correctly."""
    # Create multiple types of events
    await _register_and_login(async_client, "filter_user1@example.com")
    await _register_and_login(async_client, "filter_user2@example.com")

    admin_tokens = await _make_admin(async_client, "filter_admin@example.com")

    # Filter by login action
    resp = await async_client.get(
        "/api/v1/audit/",
        params={"action": "auth.login"},
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200
    logs = resp.json()
    if logs:
        assert all("login" in log["action"] for log in logs)


@pytest.mark.asyncio
async def test_audit_log_filter_by_date_range(async_client: AsyncClient):
    """GET /api/v1/audit?start_date=X&end_date=Y filters by date range."""
    admin_tokens = await _make_admin(async_client, "daterange_admin@example.com")

    # All logs should be within last minute
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=5)).isoformat()
    end = (now + timedelta(minutes=5)).isoformat()

    resp = await async_client.get(
        "/api/v1/audit/",
        params={"start_date": start, "end_date": end},
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp.status_code == 200

    # Future date range should return empty
    future_start = (now + timedelta(days=1)).isoformat()
    future_end = (now + timedelta(days=2)).isoformat()
    resp2 = await async_client.get(
        "/api/v1/audit/",
        params={"start_date": future_start, "end_date": future_end},
        headers={
            "Authorization": f"Bearer {admin_tokens['access_token']}",
            "X-Tenant-Slug": "test-legal-aid",
        },
    )
    assert resp2.status_code == 200
    assert len(resp2.json()) == 0
