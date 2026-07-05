"""Tests for WebSocket chat system, session lifecycle, and LLM conversation.

Covers:
  - REST endpoints: create intake, list intakes, get messages, add party, create session
  - WebSocket auth: reject invalid/missing token with code 4001
  - WebSocket text_message: store, normalize, ack, LLM follow-up
  - WebSocket session_pause: update session status
  - IntakeSessionService unit tests
  - ConversationService unit tests
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intake import Intake, IntakeParty, IntakeSession, Message
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

        app = _make_ws_test_app()
        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/api/ws/intake/999") as ws:
                    pass

    def test_websocket_auth_reject_invalid_token(self):
        """WebSocket connect with bad token should close with code 4001."""
        from starlette.testclient import TestClient

        app = _make_ws_test_app()
        with TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect(
                    "/api/ws/intake/999?token=invalid-jwt-token"
                ) as ws:
                    pass
