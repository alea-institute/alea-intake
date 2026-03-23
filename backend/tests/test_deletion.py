"""Tests for right-to-delete cascade: preview, confirm, and org-configurable policies.

Covers deletion preview with record counts, hash confirmation, stale preview
detection, and three deletion policies (full_delete, anonymize, time_based).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.consent import ConsentRecord
from app.models.shared import Organization
from app.models.user import User


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
    """Register user, promote to admin, re-login."""
    await _register_and_login(client, email)

    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS

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


async def _get_user_id(email: str) -> int:
    """Get user ID by email from the test DB."""
    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one()
            return user.id


def _auth_headers(tokens: dict) -> dict:
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }


# ── Direct service tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deletion_service_preview(async_session: AsyncSession, test_org, test_user):
    """DeletionService.preview_deletion returns record counts and preview_hash."""
    from app.services.deletion_service import DeletionService

    # Create some consent records for the user
    cr = ConsentRecord(
        user_id=test_user.id,
        consent_version="1.0",
        consent_items={"ai_processing": True},
    )
    async_session.add(cr)
    await async_session.flush()

    svc = DeletionService(async_session, test_org)
    preview = await svc.preview_deletion(test_user.id)

    assert "records_affected" in preview
    assert "categories" in preview
    assert "preview_hash" in preview
    assert preview["categories"]["consent_records"] >= 1
    assert preview["categories"]["users"] == 1
    assert len(preview["preview_hash"]) == 64  # SHA-256 hex


# ── Integration tests via HTTP client ────────────────────────────────────────


@pytest.mark.asyncio
async def test_deletion_preview(async_client: AsyncClient):
    """GET /api/v1/admin/deletion/preview/{user_id} returns preview with counts."""
    # Create a user to delete
    await _register_and_login(async_client, "delete_me@example.com")
    target_user_id = await _get_user_id("delete_me@example.com")

    admin_tokens = await _make_admin(async_client, "del_admin@example.com")

    resp = await async_client.get(
        f"/api/v1/admin/deletion/preview/{target_user_id}",
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "records_affected" in data
    assert "categories" in data
    assert "preview_hash" in data


@pytest.mark.asyncio
async def test_deletion_confirm(async_client: AsyncClient):
    """POST /api/v1/admin/deletion/confirm with valid hash deletes all user records."""
    # Create user to delete
    await _register_and_login(async_client, "del_confirm@example.com")
    target_id = await _get_user_id("del_confirm@example.com")

    admin_tokens = await _make_admin(async_client, "del_conf_admin@example.com")

    # Get preview
    preview_resp = await async_client.get(
        f"/api/v1/admin/deletion/preview/{target_id}",
        headers=_auth_headers(admin_tokens),
    )
    preview_hash = preview_resp.json()["preview_hash"]

    # Confirm deletion
    resp = await async_client.post(
        "/api/v1/admin/deletion/confirm",
        json={"user_id": target_id, "preview_hash": preview_hash},
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 200
    assert "Deletion complete" in resp.json()["message"]

    # Verify user is gone
    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            result = await session.execute(
                select(User).where(User.id == target_id)
            )
            assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_deletion_requires_hash(async_client: AsyncClient):
    """POST /api/v1/admin/deletion/confirm without preview_hash returns 400."""
    admin_tokens = await _make_admin(async_client, "del_hash_admin@example.com")

    resp = await async_client.post(
        "/api/v1/admin/deletion/confirm",
        json={"user_id": 999},
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 400 or resp.status_code == 422
    # 422 if pydantic requires the field, 400 if manual check


@pytest.mark.asyncio
async def test_deletion_stale_preview(async_client: AsyncClient):
    """POST /api/v1/admin/deletion/confirm with wrong hash returns 400."""
    await _register_and_login(async_client, "del_stale@example.com")
    target_id = await _get_user_id("del_stale@example.com")

    admin_tokens = await _make_admin(async_client, "del_stale_admin@example.com")

    resp = await async_client.post(
        "/api/v1/admin/deletion/confirm",
        json={"user_id": target_id, "preview_hash": "wrong_hash_12345"},
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 400
    assert "stale" in resp.json()["detail"].lower() or "Preview" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_deletion_anonymize_policy(async_client: AsyncClient):
    """With deletion_policy='anonymize', audit log entries have actor_id=null after deletion."""
    # Create user to delete
    await _register_and_login(async_client, "del_anon@example.com")
    target_id = await _get_user_id("del_anon@example.com")

    # Set org to anonymize policy (default in test fixtures)
    admin_tokens = await _make_admin(async_client, "del_anon_admin@example.com")

    # Get preview and confirm
    preview_resp = await async_client.get(
        f"/api/v1/admin/deletion/preview/{target_id}",
        headers=_auth_headers(admin_tokens),
    )
    preview_hash = preview_resp.json()["preview_hash"]

    resp = await async_client.post(
        "/api/v1/admin/deletion/confirm",
        json={"user_id": target_id, "preview_hash": preview_hash},
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 200

    # Check audit entries are anonymized (actor_id set to null for the deleted user)
    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            # All audit entries that previously had this actor should now be anonymized
            result = await session.execute(
                select(AuditLog).where(AuditLog.actor_id == target_id)
            )
            entries = list(result.scalars().all())
            assert len(entries) == 0  # No entries should reference the deleted user


@pytest.mark.asyncio
async def test_deletion_full_delete_policy(async_client: AsyncClient):
    """With deletion_policy='full_delete', audit log entries for user are deleted."""
    # Create user
    await _register_and_login(async_client, "del_full@example.com")
    target_id = await _get_user_id("del_full@example.com")

    admin_tokens = await _make_admin(async_client, "del_full_admin@example.com")

    # Change org policy to full_delete
    import app.db.engine as engine_module
    from sqlalchemy.ext.asyncio import AsyncSession as AS

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            await session.execute(
                update(Organization)
                .where(Organization.slug == "test-legal-aid")
                .values(deletion_policy="full_delete")
            )
            await session.commit()

    # Get preview and confirm
    preview_resp = await async_client.get(
        f"/api/v1/admin/deletion/preview/{target_id}",
        headers=_auth_headers(admin_tokens),
    )
    preview_hash = preview_resp.json()["preview_hash"]

    resp = await async_client.post(
        "/api/v1/admin/deletion/confirm",
        json={"user_id": target_id, "preview_hash": preview_hash},
        headers=_auth_headers(admin_tokens),
    )
    assert resp.status_code == 200

    # Verify no audit entries reference the deleted user
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.actor_id == target_id)
            )
            entries = list(result.scalars().all())
            assert len(entries) == 0


@pytest.mark.asyncio
async def test_only_admin_can_delete(async_client: AsyncClient):
    """Consumer trying deletion preview returns 403."""
    consumer_tokens = await _register_and_login(async_client, "del_consumer@example.com")

    resp = await async_client.get(
        "/api/v1/admin/deletion/preview/1",
        headers=_auth_headers(consumer_tokens),
    )
    assert resp.status_code == 403
