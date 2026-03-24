"""Tests for FOLIO admin API: OWL lifecycle management and unmapped concept review.

Validates admin endpoints for OWL status, manual update trigger, rollback,
unmapped concept listing with pagination/org filtering, and role enforcement.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession as AS

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
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }


# ── OWL Status Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owl_status_returns_200(async_client: AsyncClient):
    """GET /api/v1/admin/folio/owl/status returns 200 with status keys."""
    admin_tokens = await _make_admin(async_client, "owladmin@test.com")

    with patch("app.routers.folio_admin.get_owl_status", return_value={
        "cached": True,
        "etag": "abc123",
        "last_checked": "2026-03-24T10:00:00Z",
        "content_hash": "deadbeef12345678",
    }) as mock_status:
        resp = await async_client.get(
            "/api/v1/admin/folio/owl/status",
            headers=_auth_headers(admin_tokens),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "cached" in data
    assert data["cached"] is True
    assert data["etag"] == "abc123"


# ── OWL Update Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owl_update_triggers_check(async_client: AsyncClient):
    """POST /api/v1/admin/folio/owl/update triggers check_and_update."""
    admin_tokens = await _make_admin(async_client, "updateadmin@test.com")

    mock_manager = MagicMock()
    mock_manager.check_and_update = AsyncMock(return_value=True)

    with patch("app.routers.folio_admin.OWLUpdateManager") as MockClass:
        MockClass.get_instance.return_value = mock_manager
        resp = await async_client.post(
            "/api/v1/admin/folio/owl/update",
            headers=_auth_headers(admin_tokens),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] is True
    mock_manager.check_and_update.assert_awaited_once()


# ── OWL Rollback Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owl_rollback_triggers_restore(async_client: AsyncClient):
    """POST /api/v1/admin/folio/owl/rollback triggers rollback and reload."""
    admin_tokens = await _make_admin(async_client, "rollbackadmin@test.com")

    with patch("app.routers.folio_admin.rollback_owl", return_value=True) as mock_rollback, \
         patch("app.routers.folio_admin.reload_folio") as mock_reload, \
         patch("app.routers.folio_admin.FOLIO") as mock_folio_cls, \
         patch("app.routers.folio_admin.get_settings") as mock_settings:
        mock_settings.return_value.folio_owl_branch = "main"
        mock_folio_cls.return_value = MagicMock()

        resp = await async_client.post(
            "/api/v1/admin/folio/owl/rollback",
            headers=_auth_headers(admin_tokens),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rolled_back"] is True
    mock_rollback.assert_called_once()


# ── Unmapped List Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unmapped_list_returns_paginated(async_client: AsyncClient):
    """GET /api/v1/admin/folio/unmapped returns paginated list."""
    admin_tokens = await _make_admin(async_client, "listadmin@test.com")

    # Seed unmapped concepts directly in the DB
    import app.db.engine as engine_module
    from app.models.folio_concepts import UnmappedConceptRecord

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            for i in range(3):
                session.add(UnmappedConceptRecord(
                    intake_id=1,
                    local_iri=f"https://folio.openlegalstandard.org/unmapped{i:03d}",
                    original_text=f"Unmapped concept {i}",
                    suggested_branch=None,
                    unmapped_confidence=0.9,
                    nearest_iris=[],
                    org_id=1,
                ))
            await session.commit()

    resp = await async_client.get(
        "/api/v1/admin/folio/unmapped",
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_unmapped_filters_by_org(async_client: AsyncClient):
    """GET /api/v1/admin/folio/unmapped?org_id=1 filters by organization."""
    admin_tokens = await _make_admin(async_client, "filteradmin@test.com")

    # Seed unmapped concepts for org 1 and org 999
    import app.db.engine as engine_module
    from app.models.folio_concepts import UnmappedConceptRecord

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            session.add(UnmappedConceptRecord(
                intake_id=10,
                local_iri="https://folio.openlegalstandard.org/org1concept",
                original_text="Org 1 concept",
                unmapped_confidence=0.7,
                nearest_iris=[],
                org_id=1,
            ))
            session.add(UnmappedConceptRecord(
                intake_id=11,
                local_iri="https://folio.openlegalstandard.org/org999concept",
                original_text="Org 999 concept",
                unmapped_confidence=0.8,
                nearest_iris=[],
                org_id=999,
            ))
            await session.commit()

    resp = await async_client.get(
        "/api/v1/admin/folio/unmapped?org_id=999",
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["org_id"] == 999


# ── Role Enforcement Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_role(async_client: AsyncClient):
    """Non-admin users get 403 on admin FOLIO endpoints."""
    consumer_tokens = await _register_and_login(async_client, "consumer@test.com")
    headers = _auth_headers(consumer_tokens)

    # All admin endpoints should return 403
    endpoints = [
        ("GET", "/api/v1/admin/folio/owl/status"),
        ("POST", "/api/v1/admin/folio/owl/update"),
        ("POST", "/api/v1/admin/folio/owl/rollback"),
        ("GET", "/api/v1/admin/folio/unmapped"),
        ("GET", "/api/v1/admin/folio/config"),
    ]

    for method, path in endpoints:
        if method == "GET":
            resp = await async_client.get(path, headers=headers)
        else:
            resp = await async_client.post(path, headers=headers)
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}, expected 403"


# ── Config Endpoint Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_folio_config_returns_settings(async_client: AsyncClient):
    """GET /api/v1/admin/folio/config returns FOLIO configuration."""
    admin_tokens = await _make_admin(async_client, "configadmin@test.com")

    resp = await async_client.get(
        "/api/v1/admin/folio/config",
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "owl_branch" in data
    assert "update_interval_hours" in data
    assert "confidence_threshold" in data
    assert "traversal_depth" in data
    assert "cache_dir" in data


# ── Router Wiring Tests ─────────────────────────────────────────────────────


def test_folio_admin_router_is_registered():
    """The folio_admin_router is wired into the FastAPI app via include_router."""
    from app.main import app as fastapi_app

    # Verify the folio admin routes are in the app's routes
    route_paths = [route.path for route in fastapi_app.routes]
    assert "/api/v1/admin/folio/owl/status" in route_paths, (
        "folio_admin_router not registered -- /api/v1/admin/folio/owl/status missing from routes"
    )
    assert "/api/v1/admin/folio/owl/update" in route_paths
    assert "/api/v1/admin/folio/owl/rollback" in route_paths
    assert "/api/v1/admin/folio/unmapped" in route_paths
    assert "/api/v1/admin/folio/config" in route_paths
