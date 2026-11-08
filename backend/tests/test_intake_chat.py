"""Tests for WebSocket chat system, session lifecycle, and LLM conversation.

Covers:
  - REST endpoints: create intake, list intakes, get messages, add party, create session
  - WebSocket auth: reject invalid/missing token with code 4001
  - WebSocket text_message: store, normalize, ack, LLM follow-up
  - WebSocket session_pause: update session status
  - IntakeSessionService unit tests
  - ConversationService unit tests
"""

from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from tests.test_showcase_mode import showcase as showcase, guest  # noqa: F401

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.intake.session_service import IntakeSessionService
from app.services.intake.conversation import ConversationService, INTAKE_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helper: register, login, and grant consent (needed for intake endpoints)
# ---------------------------------------------------------------------------

async def _setup_authed_user(async_client: AsyncClient, email: str) -> str:
    """Register a user, login, grant AI consent, return the access token."""
    headers = {"X-Tenant-Slug": "test-legal-aid"}

    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Test1234!Strong",
            "full_name": "Intake Tester",
        },
        headers=headers,
    )
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test1234!Strong"},
        headers=headers,
    )
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}", **headers}

    # Grant AI processing consent so the ConsentMiddleware allows intake endpoints
    await async_client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True, "data_sharing": False},
        },
        headers=auth_headers,
    )

    return token


# ---------------------------------------------------------------------------
# IntakeSessionService unit tests (pure DB layer)
# ---------------------------------------------------------------------------

class TestIntakeSessionService:
    @pytest.mark.asyncio
    async def test_create_intake(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=10, session_mode="multi_session")
        assert intake.id is not None
        assert intake.status == "active"
        assert intake.org_id == 1
        assert intake.session_mode == "multi_session"

    @pytest.mark.asyncio
    async def test_create_session(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        session = await svc.create_session(intake.id)
        assert session.id is not None
        assert session.status == "active"
        assert session.intake_id == intake.id

    @pytest.mark.asyncio
    async def test_add_party(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        party = await svc.add_party(intake.id, user_id=5, role_in_intake="primary", label="Consumer")
        assert party.id is not None
        assert party.intake_id == intake.id
        assert party.role_in_intake == "primary"
        assert party.label == "Consumer"

    @pytest.mark.asyncio
    async def test_store_message_and_sequence(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        session = await svc.create_session(intake.id)

        msg1 = await svc.store_message(session.id, "consumer", "text", "Hello")
        assert msg1.sequence_number == 1
        assert msg1.sender_type == "consumer"
        assert msg1.modality == "text"

        msg2 = await svc.store_message(session.id, "system", "text", "How can I help?")
        assert msg2.sequence_number == 2

    @pytest.mark.asyncio
    async def test_pause_session(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        session = await svc.create_session(intake.id)

        paused = await svc.pause_session(session.id)
        assert paused.status == "paused"
        assert paused.ended_at is not None

    @pytest.mark.asyncio
    async def test_resume_session(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        session = await svc.create_session(intake.id)
        await svc.pause_session(session.id)

        resumed = await svc.resume_session(session.id)
        assert resumed.status == "active"
        assert resumed.ended_at is None

    @pytest.mark.asyncio
    async def test_list_intakes(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        await svc.create_intake(org_id=1, user_id=None)
        await svc.create_intake(org_id=1, user_id=None)

        intakes = await svc.list_intakes(org_id=1)
        assert len(intakes) >= 2

    @pytest.mark.asyncio
    async def test_get_messages_ordered(self, async_session: AsyncSession):
        svc = IntakeSessionService(async_session)
        intake = await svc.create_intake(org_id=1, user_id=None)
        session = await svc.create_session(intake.id)

        await svc.store_message(session.id, "consumer", "text", "First")
        await svc.store_message(session.id, "system", "text", "Second")
        await svc.store_message(session.id, "consumer", "text", "Third")

        messages = await svc.get_messages(session.id)
        assert len(messages) == 3
        assert messages[0].sequence_number < messages[1].sequence_number < messages[2].sequence_number


# ---------------------------------------------------------------------------
# ConversationService unit tests
# ---------------------------------------------------------------------------

class TestConversationService:
    def test_intake_system_prompt_exists(self):
        assert INTAKE_SYSTEM_PROMPT is not None
        assert len(INTAKE_SYSTEM_PROMPT) > 20

    @pytest.mark.asyncio
    async def test_generate_welcome_message_consumer(self):
        mock_llm = AsyncMock()
        svc = ConversationService(mock_llm)
        msg = await svc.generate_welcome_message(session_mode="multi_session", is_professional=False)
        assert isinstance(msg, str)
        assert len(msg) > 10

    @pytest.mark.asyncio
    async def test_generate_welcome_message_professional(self):
        mock_llm = AsyncMock()
        svc = ConversationService(mock_llm)
        msg = await svc.generate_welcome_message(session_mode="multi_session", is_professional=True)
        assert isinstance(msg, str)
        assert "client" in msg.lower() or "information" in msg.lower()

    @pytest.mark.asyncio
    async def test_generate_response(self):
        mock_llm = MagicMock()
        mock_llm.acomplete = AsyncMock(return_value="Tell me more about the repairs.")
        svc = ConversationService(mock_llm)
        result = await svc.generate_response(
            messages=[{"role": "user", "content": "My landlord won't fix the plumbing"}]
        )
        assert isinstance(result, str)
        assert result == "Tell me more about the repairs."


# ---------------------------------------------------------------------------
# REST endpoint tests (via async_client fixture)
# ---------------------------------------------------------------------------

class TestIntakeRESTEndpoints:
    @pytest.mark.asyncio
    async def test_create_intake(self, async_client):
        token = await _setup_authed_user(async_client, "intake-create@example.com")

        resp = await async_client.post(
            "/api/v1/intake/",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "active"
        assert "session_id" in data
        assert "party_id" in data

    @pytest.mark.asyncio
    async def test_list_intakes(self, async_client):
        token = await _setup_authed_user(async_client, "intake-list@example.com")

        resp = await async_client.get(
            "/api/v1/intake/",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": "test-legal-aid",
            },
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_messages(self, async_client):
        token = await _setup_authed_user(async_client, "intake-msg@example.com")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Slug": "test-legal-aid",
        }

        create_resp = await async_client.post("/api/v1/intake/", headers=headers)
        data = create_resp.json()
        intake_id = data["id"]
        session_id = data["session_id"]

        resp = await async_client.get(
            f"/api/v1/intake/{intake_id}/messages?session_id={session_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# WebSocket tests (using lightweight Starlette app to avoid FOLIO lifespan)
# ---------------------------------------------------------------------------

def _make_ws_test_app():
    """Create a lightweight FastAPI app with only the WS router for testing.

    Avoids the heavy FOLIO lifespan that the main app uses.
    """
    from fastapi import FastAPI
    from app.routers.intake import ws_router

    test_app = FastAPI()
    test_app.include_router(ws_router)
    return test_app


class TestWebSocketEndpoints:
    def test_websocket_auth_reject_no_token(self):
        """WebSocket connect without token should close with code 4001."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        app = _make_ws_test_app()
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc:
                with client.websocket_connect("/api/ws/intake/999") as ws:
                    ws.send_json({"type": "auth"})
                    ws.receive_json()
            assert exc.value.code == 4001

    def test_websocket_auth_reject_invalid_token(self):
        """WebSocket connect with bad token should close with code 4001."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        app = _make_ws_test_app()
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc:
                with client.websocket_connect(
                    "/api/ws/intake/999?token=invalid-jwt-token"
                ) as ws:
                    ws.receive_json()
            assert exc.value.code == 4001


@pytest.mark.parametrize('query_token', [False, True])
async def test_standard_socket_rejects_another_consumers_session(showcase, query_token):
    client, settings, app = showcase
    owner, other = await guest(client), await guest(client)
    created = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    settings.showcase_mode = False
    path = f'/api/ws/intake/{created["session_id"]}'
    if query_token:
        path += '?token=' + other['Authorization'][7:]
    with TestClient(app) as sync:
        with pytest.raises(WebSocketDisconnect) as exc:
            with sync.websocket_connect(path) as ws:
                if not query_token:
                    ws.send_json({'type': 'auth', 'token': other['Authorization'][7:]})
                ws.receive_json()
        assert exc.value.code == 4003


async def test_standard_socket_uses_auth_frame_key_with_real_header_parser(showcase, monkeypatch):
    client, settings, app = showcase
    owner = await guest(client)
    created = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    settings.showcase_mode = False
    reply = AsyncMock(return_value='When were your wages due?')
    monkeypatch.setattr('app.routers.intake.ConversationService.generate_response', reply)
    monkeypatch.setattr('app.routers.intake.screen_message_fast', AsyncMock(return_value=None))
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({'type': 'auth', 'token': owner['Authorization'][7:], 'llm_api_key': 'visitor-key'})
            assert ws.receive_json()['type'] == 'session_state'
            ws.send_json({'type': 'text_message', 'content': 'My wages are unpaid.'})
            assert ws.receive_json()['type'] == 'message_ack'
            response = ws.receive_json()
            assert response['type'] == 'system_message'
            assert response['content'] == 'When were your wages due?'
    reply.assert_awaited_once()


@pytest.mark.parametrize('showcase_mode', [False, True])
@pytest.mark.parametrize('key', [123, ['not', 'a', 'key'], {'key': 'invalid'}, 'bad\nkey'])
async def test_socket_malformed_key_closes_4001(showcase, showcase_mode, key):
    client, settings, app = showcase
    owner = await guest(client)
    created = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    settings.showcase_mode = showcase_mode
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({'type': 'auth', 'token': owner['Authorization'][7:], 'llm_api_key': key})
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4001


async def test_socket_closes_4004_when_guest_touch_fails(showcase, monkeypatch):
    client, _, app = showcase
    owner = await guest(client)
    created = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({'type': 'auth', 'token': owner['Authorization'][7:], 'llm_api_key': 'visitor-key'})
            assert ws.receive_json()['type'] == 'session_state'
            monkeypatch.setattr('app.db.retention.touch_guest', AsyncMock(return_value=False))
            ws.send_json({'type': 'text_message', 'content': 'My wages are unpaid.'})
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4004


@pytest.mark.parametrize('role', ['admin', 'professional'])
@pytest.mark.parametrize('same_org', [True, False])
async def test_standard_socket_respects_staff_org_access(showcase, role, same_org):
    from app.db.engine import get_engine
    from app.models import User, Intake
    from sqlalchemy import select, update

    client, settings, app = showcase
    owner, staff = await guest(client), await guest(client)
    created = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    async with get_engine().begin() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        owner_id = (await conn.execute(select(Intake.created_by_user_id).where(
            Intake.id == created['id']))).scalar_one()
        await conn.execute(update(User).where(User.id != owner_id).values(
            role=role, org_id=1 if same_org else 999))
    settings.showcase_mode = False
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({'type': 'auth', 'token': staff['Authorization'][7:]})
            if same_org:
                assert ws.receive_json()['type'] == 'session_state'
            else:
                with pytest.raises(WebSocketDisconnect) as exc:
                    ws.receive_json()
                assert exc.value.code == 4003
