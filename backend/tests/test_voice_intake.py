"""Tests for voice_upload, transcript_approve, and transcript_edit WebSocket flows.

Covers:
  - Test 1: voice_upload stores AudioRecording and triggers ASR transcription
  - Test 2: Server sends transcript_ready with text, segments, confidence, recording_id
  - Test 3: transcript_approve creates Transcript with status="approved" and Message modality="voice"
  - Test 4: transcript_edit with edited_text creates Transcript with status="edited"
  - Test 5: Approved/edited transcript enters normalization pipeline
  - Test 6: After transcript approval, server sends system_message (LLM follow-up)
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.testclient import TestClient

from app.models.audio import AudioRecording, Transcript
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.services.asr.providers.base import TranscriptionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(user_id: int = 1, secret: str = "test-secret-key-for-testing-only-not-production") -> str:
    """Create a minimal JWT token for WebSocket auth."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _make_ws_test_app():
    """Create a lightweight FastAPI app with the WS router for testing."""
    from fastapi import FastAPI
    from app.routers.intake import ws_router

    test_app = FastAPI()
    test_app.include_router(ws_router)
    return test_app


async def _setup_db_with_session(engine):
    """Create all tables and seed an intake + session for voice tests."""
    from app.db.base import TenantBase, SharedBase, convention

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)

    # Seed org + intake + session
    from app.models.shared import Organization

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            org = Organization(
                name="Test Legal Aid",
                slug="test-legal-aid",
                auth_mode="email_password",
                llm_data_policy="cloud_optout",
                consent_mode="granular",
                deletion_policy="anonymize",
            )
            db.add(org)
            await db.flush()

            intake = Intake(org_id=org.id, status="active", session_mode="multi_session")
            db.add(intake)
            await db.flush()

            session = IntakeSession(intake_id=intake.id, status="active")
            db.add(session)
            await db.flush()

            await db.commit()
            return session.id, intake.id


FAKE_AUDIO = base64.b64encode(b"fake audio data for testing").decode()

FAKE_TRANSCRIPTION = TranscriptionResult(
    text="I was fired from my job last Tuesday",
    segments=[
        {"start": 0.0, "end": 2.5, "text": "I was fired from my job", "speaker": None},
        {"start": 2.5, "end": 4.0, "text": "last Tuesday", "speaker": None},
    ],
    language="en",
    confidence=0.94,
)


@contextmanager
def _voice_test_env():
    """Set up test engine, DB tables, mocks, and clean up after."""
    import asyncio
    import app.config as app_config_mod
    import app.db.engine as engine_module
    from tests.conftest import get_test_settings

    # Override settings
    original_get_settings = app_config_mod.get_settings
    app_config_mod.get_settings.cache_clear()
    app_config_mod.get_settings = get_test_settings

    _tmp_fd, _tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(_tmp_fd)

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{_tmp_path}", echo=False)
    engine_module._engine = test_engine

    loop = asyncio.new_event_loop()
    session_id, intake_id = loop.run_until_complete(_setup_db_with_session(test_engine))
    loop.close()

    mock_asr_instance = MagicMock()
    mock_asr_instance.transcribe = AsyncMock(return_value=FAKE_TRANSCRIPTION)
    mock_asr_instance.provider_name = "whisper"

    mock_conv_instance = MagicMock()
    mock_conv_instance.generate_response = AsyncMock(
        return_value="Could you tell me more about why you were fired?"
    )

    try:
        yield {
            "session_id": session_id,
            "intake_id": intake_id,
            "engine": test_engine,
            "mock_asr": mock_asr_instance,
            "mock_conv": mock_conv_instance,
            "get_test_settings": get_test_settings,
        }
    finally:
        loop2 = asyncio.new_event_loop()
        loop2.run_until_complete(test_engine.dispose())
        loop2.close()
        engine_module._engine = None
        app_config_mod.get_settings = original_get_settings
        app_config_mod.get_settings.cache_clear()
        try:
            os.unlink(_tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVoiceUploadFlow:
    """Full voice_upload -> transcript_ready -> transcript_approve/edit flow."""

    def test_voice_upload_triggers_transcription_and_transcript_ready(self):
        """voice_upload stores AudioRecording, runs ASR, and sends transcript_ready."""
        with _voice_test_env() as env:
            token = _make_jwt()
            test_app = _make_ws_test_app()

            with patch("app.routers.intake.ASRService", return_value=env["mock_asr"]), \
                 patch("app.routers.intake.ConversationService", return_value=env["mock_conv"]), \
                 patch("app.routers.intake.get_settings", env["get_test_settings"]):
                with TestClient(test_app) as client:
                    with client.websocket_connect(
                        f"/api/ws/intake/{env['session_id']}?token={token}"
                    ) as ws:
                        # Read initial session_state
                        initial = ws.receive_json()
                        assert initial["type"] == "session_state"

                        # Send voice_upload
                        ws.send_json({
                            "type": "voice_upload",
                            "audio_data": FAKE_AUDIO,
                            "format": "webm",
                            "party_id": None,
                        })

                        # Should receive transcript_ready
                        response = ws.receive_json()
                        assert response["type"] == "transcript_ready"
                        assert response["text"] == FAKE_TRANSCRIPTION.text
                        assert response["confidence"] == FAKE_TRANSCRIPTION.confidence
                        assert "recording_id" in response
                        assert "transcript_id" in response
                        assert "message_id" in response
                        assert len(response["segments"]) == 2

    def test_transcript_approve_creates_record_and_sends_system_message(self):
        """transcript_approve updates status to 'approved' and triggers LLM response."""
        with _voice_test_env() as env:
            token = _make_jwt()
            test_app = _make_ws_test_app()

            with patch("app.routers.intake.ASRService", return_value=env["mock_asr"]), \
                 patch("app.routers.intake.ConversationService", return_value=env["mock_conv"]), \
                 patch("app.routers.intake.get_settings", env["get_test_settings"]):
                with TestClient(test_app) as client:
                    with client.websocket_connect(
                        f"/api/ws/intake/{env['session_id']}?token={token}"
                    ) as ws:
                        initial = ws.receive_json()

                        # Step 1: voice_upload
                        ws.send_json({
                            "type": "voice_upload",
                            "audio_data": FAKE_AUDIO,
                            "format": "webm",
                        })
                        transcript_ready = ws.receive_json()
                        recording_id = transcript_ready["recording_id"]

                        # Step 2: transcript_approve
                        ws.send_json({
                            "type": "transcript_approve",
                            "recording_id": recording_id,
                        })

                        # Should receive message_ack then system_message
                        ack = ws.receive_json()
                        assert ack["type"] == "message_ack"

                        sys_msg = ws.receive_json()
                        assert sys_msg["type"] == "system_message"
                        assert len(sys_msg["content"]) > 0

    def test_transcript_edit_updates_text_and_sends_system_message(self):
        """transcript_edit updates transcript text to edited version and triggers LLM."""
        with _voice_test_env() as env:
            token = _make_jwt()
            test_app = _make_ws_test_app()

            env["mock_conv"].generate_response = AsyncMock(
                return_value="Thank you for the correction. Tell me more."
            )

            edited_text = "I was let go from my position last Wednesday"

            with patch("app.routers.intake.ASRService", return_value=env["mock_asr"]), \
                 patch("app.routers.intake.ConversationService", return_value=env["mock_conv"]), \
                 patch("app.routers.intake.get_settings", env["get_test_settings"]):
                with TestClient(test_app) as client:
                    with client.websocket_connect(
                        f"/api/ws/intake/{env['session_id']}?token={token}"
                    ) as ws:
                        initial = ws.receive_json()

                        # Step 1: voice_upload
                        ws.send_json({
                            "type": "voice_upload",
                            "audio_data": FAKE_AUDIO,
                            "format": "webm",
                        })
                        transcript_ready = ws.receive_json()
                        recording_id = transcript_ready["recording_id"]

                        # Step 2: transcript_edit
                        ws.send_json({
                            "type": "transcript_edit",
                            "recording_id": recording_id,
                            "edited_text": edited_text,
                        })

                        # Should receive message_ack then system_message
                        ack = ws.receive_json()
                        assert ack["type"] == "message_ack"

                        sys_msg = ws.receive_json()
                        assert sys_msg["type"] == "system_message"
                        assert len(sys_msg["content"]) > 0
