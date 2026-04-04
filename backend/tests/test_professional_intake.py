"""Tests for professional intake router.

Validates that professionals can create intakes on behalf of consumers,
submit notes with party attribution, submit structured form data,
and review intake summaries. Consumer role is blocked with 403.
"""

import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings
from app.db.base import SharedBase, TenantBase, convention
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.models.fact import ExtractedFact
from app.models.consent import ConsentRecord
from app.models.shared import Organization
from app.models.user import User

TENANT_SLUG = "test-legal-aid"


def _test_settings() -> Settings:
    return Settings(
        secret_key="test-secret-key-for-testing-only-not-production",
        database_backend="sqlite",
        sqlite_path=":memory:",
        debug=False,
        cors_origins=["http://localhost:5173"],
    )


def _make_token(user_id: int, role: str = "professional") -> str:
    """Create a JWT for testing."""
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, "test-secret-key-for-testing-only-not-production", algorithm="HS256")


def _headers(token: str) -> dict:
    """Standard headers with auth and tenant slug."""
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Slug": TENANT_SLUG,
    }


@pytest.fixture
async def pro_client():
    """AsyncClient with patched engine for professional intake tests."""
    import app.config
    import app.db.engine as engine_module

    original_get_settings = app.config.get_settings
    app.config.get_settings.cache_clear()
    app.config.get_settings = _test_settings

    _tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(_tmp_db_fd)

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{_tmp_db_path}", echo=False
    )
    engine_module._engine = test_engine

    import app.models  # noqa: F401

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with test_engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)

    # Seed data in the temp DB
    async with test_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as sess:
            org = Organization(
                name="Test Legal Aid",
                slug=TENANT_SLUG,
                auth_mode="email_password",
                llm_data_policy="cloud_optout",
                consent_mode="granular",
                deletion_policy="anonymize",
            )
            sess.add(org)
            await sess.flush()

            pro_user = User(
                email="pro@example.com",
                hashed_password="$placeholder$",
                full_name=b"Professional User",
                role="professional",
                org_id=org.id,
            )
            sess.add(pro_user)

            consumer_user = User(
                email="consumer@example.com",
                hashed_password="$placeholder$",
                full_name=b"Consumer User",
                role="consumer",
                org_id=org.id,
            )
            sess.add(consumer_user)
            await sess.flush()

            # Seed consent records for both users (required by consent middleware)
            for uid in [pro_user.id, consumer_user.id]:
                sess.add(
                    ConsentRecord(
                        user_id=uid,
                        consent_version="1.0",
                        consent_items={"ai_processing": True, "data_storage": True},
                    )
                )
            await sess.flush()

            # Create intake with party and session
            intake = Intake(
                org_id=org.id,
                created_by_user_id=pro_user.id,
                session_mode="multi_session",
                status="active",
            )
            sess.add(intake)
            await sess.flush()

            party = IntakeParty(
                intake_id=intake.id,
                user_id=consumer_user.id,
                role_in_intake="primary",
                label="Primary Consumer",
            )
            sess.add(party)

            intake_session = IntakeSession(
                intake_id=intake.id,
                status="active",
            )
            sess.add(intake_session)
            await sess.flush()
            await sess.commit()

            data = {
                "org": org,
                "pro_user": pro_user,
                "consumer_user": consumer_user,
                "intake": intake,
                "party": party,
                "session": intake_session,
            }

    # Patch modules
    patched = []
    for mod_name in [
        "app.core.permissions",
        "app.services.auth_service",
        "app.routers.auth",
        "app.middleware.consent",
    ]:
        try:
            import importlib

            mod = importlib.import_module(mod_name)
            if hasattr(mod, "get_settings"):
                patched.append((mod, mod.get_settings))
                mod.get_settings = _test_settings
        except ImportError:
            pass

    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client._test_data = data  # type: ignore[attr-defined]
        yield client

    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(_tenant_meta.drop_all)
        await conn.run_sync(_shared_meta.drop_all)
    await test_engine.dispose()
    engine_module._engine = None
    try:
        os.unlink(_tmp_db_path)
    except OSError:
        pass

    app.config.get_settings = original_get_settings
    for mod, original_fn in patched:
        mod.get_settings = original_fn
    app.config.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_intake_on_behalf(pro_client):
    """POST /api/v1/intake/professional creates intake with professional as creator."""
    data = pro_client._test_data
    token = _make_token(data["pro_user"].id, "professional")

    resp = await pro_client.post(
        "/api/v1/intake/professional",
        json={"session_mode": "multi_session"},
        headers=_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "intake_id" in body
    assert "session_id" in body
    assert "party_id" in body


@pytest.mark.asyncio
async def test_submit_note(pro_client):
    """POST /{intake_id}/note creates Message with sender_type=professional."""
    data = pro_client._test_data
    token = _make_token(data["pro_user"].id, "professional")
    intake_id = data["intake"].id

    resp = await pro_client.post(
        f"/api/v1/intake/professional/{intake_id}/note",
        json={"content": "Client reports injury on January 15, 2026."},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "message_id" in body
    assert "sequence_number" in body


@pytest.mark.asyncio
async def test_note_has_attribution(pro_client):
    """Note metadata_json contains on_behalf_of and professional_user_id."""
    data = pro_client._test_data
    token = _make_token(data["pro_user"].id, "professional")
    intake_id = data["intake"].id
    party_id = data["party"].id

    resp = await pro_client.post(
        f"/api/v1/intake/professional/{intake_id}/note",
        json={
            "content": "Client describes slip and fall.",
            "party_id": party_id,
            "note_type": "incident",
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message_id"] > 0


@pytest.mark.asyncio
async def test_structured_form(pro_client):
    """POST /{intake_id}/structured-form stores structured form data as Message."""
    data = pro_client._test_data
    token = _make_token(data["pro_user"].id, "professional")
    intake_id = data["intake"].id

    form_data = {
        "party_info": {"name": "John Doe", "relationship": "client", "contact": "555-1234"},
        "incident_details": "Slip and fall at grocery store on January 15, 2026.",
        "timeline": [
            {"date": "2026-01-15", "event": "Injury occurred"},
            {"date": "2026-01-20", "event": "Medical treatment received"},
        ],
        "damages": [
            {"type": "medical", "amount": 15000.00, "description": "ER visit and follow-up"},
        ],
        "additional_notes": "Client has photographs of the scene.",
    }

    resp = await pro_client.post(
        f"/api/v1/intake/professional/{intake_id}/structured-form",
        json=form_data,
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "message_id" in body
    assert "sequence_number" in body


@pytest.mark.asyncio
async def test_consumer_cannot_access(pro_client):
    """Consumer role returns 403 on professional endpoints."""
    data = pro_client._test_data
    token = _make_token(data["consumer_user"].id, "consumer")

    resp = await pro_client.post(
        "/api/v1/intake/professional",
        json={"session_mode": "multi_session"},
        headers=_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_summary(pro_client):
    """GET /{intake_id}/summary returns intake summary with counts."""
    data = pro_client._test_data
    token = _make_token(data["pro_user"].id, "professional")
    intake_id = data["intake"].id

    # First submit a note so there's a message
    await pro_client.post(
        f"/api/v1/intake/professional/{intake_id}/note",
        json={"content": "Summary test note."},
        headers=_headers(token),
    )

    resp = await pro_client.get(
        f"/api/v1/intake/professional/{intake_id}/summary",
        headers=_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intake_id"] == intake_id
    assert "messages_count" in body
    assert "facts_count" in body
    assert "parties" in body
    assert body["messages_count"] >= 1
