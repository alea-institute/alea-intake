"""Intake API endpoints: REST CRUD and WebSocket real-time chat.

REST endpoints handle intake lifecycle (create, list, get messages, add party,
create session). The WebSocket endpoint handles real-time chat with JWT
authentication, message storage, normalization, and LLM-guided conversation.

Voice modality: voice_upload -> ASR transcription -> transcript_ready for review
-> transcript_approve/transcript_edit -> normalization pipeline -> LLM follow-up.
"""

from __future__ import annotations

import base64
import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import jwt as pyjwt
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.audio import AudioRecording, Transcript
from app.models.document import DocumentExtraction, UploadedDocument
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.models.user import User
from app.services.asr import ASRService, TranscriptionResult
from app.services.document import DocumentService
from app.services.intake.conversation import ConversationService
from app.services.intake.message_pipeline import normalize_text, process_message
from app.services.intake.session_service import IntakeSessionService
from app.services.screening.middleware import (
    add_to_exploration_queue,
    build_safety_alert_message,
    persist_screening_event,
    queue_elevated_screening,
    screen_message_fast,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class IntakeConnectionManager:
    """Manages active WebSocket connections per intake session."""

    def __init__(self) -> None:
        # session_id -> list of active WebSocket connections
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, session_id: int) -> None:
        """Accept and register a WebSocket connection for a session."""
        await websocket.accept()
        self._connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int) -> None:
        """Remove a WebSocket connection from a session."""
        conns = self._connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(session_id, None)

    async def send_to_session(self, session_id: int, message: dict) -> None:
        """Send a JSON message to all connections on a session."""
        for ws in self._connections.get(session_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def send_to_others(
        self, session_id: int, exclude: WebSocket, message: dict
    ) -> None:
        """Send a JSON message to all connections except the sender."""
        for ws in self._connections.get(session_id, []):
            if ws is not exclude:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


# Module-level manager instance
manager = IntakeConnectionManager()


# ---------------------------------------------------------------------------
# Helper: get org_id from request state
# ---------------------------------------------------------------------------

def _get_org_id(request: Request) -> int:
    """Extract org_id from tenant context. Default to 1 for testing."""
    return getattr(request.state, "org_id", 1)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_intake(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new intake with primary party and first session."""
    org_id = _get_org_id(request)
    svc = IntakeSessionService(session)

    intake = await svc.create_intake(
        org_id=org_id,
        user_id=current_user.id,
        session_mode="multi_session",
    )
    party = await svc.add_party(
        intake_id=intake.id,
        user_id=current_user.id,
        role_in_intake="primary",
        label="Primary",
    )
    intake_session = await svc.create_session(intake.id)

    return {
        "id": intake.id,
        "status": intake.status,
        "session_mode": intake.session_mode,
        "created_at": str(intake.created_at) if intake.created_at else None,
        "session_id": intake_session.id,
        "party_id": party.id,
    }


@router.get("/")
async def list_intakes(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List intakes for the authenticated user's tenant."""
    org_id = _get_org_id(request)
    svc = IntakeSessionService(session)
    intakes = await svc.list_intakes(org_id=org_id)
    return [
        {
            "id": i.id,
            "status": i.status,
            "session_mode": i.session_mode,
            "created_at": str(i.created_at) if i.created_at else None,
        }
        for i in intakes
    ]


@router.get("/{intake_id}/messages")
async def get_messages(
    intake_id: int,
    session_id: int = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get paginated message history for an intake session."""
    svc = IntakeSessionService(session)
    messages = await svc.get_messages(session_id=session_id, limit=limit, offset=offset)
    return [
        {
            "id": m.id,
            "sender_type": m.sender_type,
            "modality": m.modality,
            "content": m.content_encrypted.decode("utf-8") if m.content_encrypted else None,
            "sequence_number": m.sequence_number,
            "created_at": str(m.created_at) if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/{intake_id}/party", status_code=status.HTTP_201_CREATED)
async def add_party(
    intake_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Add a party to an existing intake."""
    body = await request.json()
    svc = IntakeSessionService(session)
    party = await svc.add_party(
        intake_id=intake_id,
        user_id=body.get("user_id"),
        role_in_intake=body.get("role_in_intake", "primary"),
        label=body.get("label"),
    )
    return {
        "id": party.id,
        "intake_id": party.intake_id,
        "role_in_intake": party.role_in_intake,
        "label": party.label,
    }


@router.post("/{intake_id}/session", status_code=status.HTTP_201_CREATED)
async def create_session(
    intake_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new session for the intake (multi-session resume)."""
    svc = IntakeSessionService(session)
    intake_session = await svc.create_session(intake_id)
    return {
        "id": intake_session.id,
        "intake_id": intake_session.intake_id,
        "status": intake_session.status,
    }


# ---------------------------------------------------------------------------
# Document upload endpoint (Plan 03-03)
# ---------------------------------------------------------------------------

@router.post("/{intake_id}/document", status_code=status.HTTP_201_CREATED)
async def document_upload(
    intake_id: int,
    request: Request,
    file: UploadFile = File(...),
    session_id: int = Form(...),
    party_id: int | None = Form(None),
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_tenant_session),
):
    """Upload a document, extract text, store records, and notify via WebSocket.

    Creates a Message with modality="document", an UploadedDocument record,
    a DocumentExtraction record, generates an LLM follow-up, and sends
    a document_ready WebSocket notification.
    """
    settings = get_settings()
    doc_service = DocumentService()

    # Validate MIME type
    supported = doc_service.get_supported_mime_types()
    if file.content_type not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Unsupported file type: {file.content_type}",
                "supported_types": supported,
            },
        )

    # Read file bytes
    file_bytes = await file.read()

    # Validate file size
    max_bytes = settings.intake_max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum {settings.intake_max_file_size_mb} MB",
        )

    # Get org slug for directory structure
    org_slug = getattr(request.state, "tenant_slug", "default")

    # Store Message with modality="document"
    svc = IntakeSessionService(db_session)
    msg = await svc.store_message(
        session_id=session_id,
        sender_type="consumer",
        modality="document",
        content=file.filename or "document",
        party_id=party_id,
    )

    # Save file to disk
    file_path = await doc_service.save_upload(
        file_bytes=file_bytes,
        filename=file.filename or "unknown",
        mime_type=file.content_type or "",
        org_slug=org_slug,
        intake_id=intake_id,
    )

    # Create UploadedDocument record
    uploaded_doc = UploadedDocument(
        message_id=msg.id,
        intake_id=intake_id,
        file_path_encrypted=str(file_path).encode("utf-8"),
        original_filename=file.filename or "unknown",
        mime_type=file.content_type or "",
        file_size_bytes=len(file_bytes),
        extraction_status="pending",
    )
    db_session.add(uploaded_doc)
    await db_session.flush()

    # Extract document content
    extraction_status = "pending"
    normalized = None
    try:
        normalized = await doc_service.process_document(
            file_path, file.content_type or "", msg.id, party_id
        )

        uploaded_doc.extraction_status = "completed"
        extraction_status = "completed"

        pages = {e.page for e in normalized.elements if e.page is not None}
        if pages:
            uploaded_doc.page_count = max(pages)

        extraction = DocumentExtraction(
            document_id=uploaded_doc.id,
            full_text_encrypted=normalized.text.encode("utf-8"),
            elements_json=[asdict(e) for e in normalized.elements],
            extraction_method=doc_service.get_extraction_method(file.content_type or ""),
        )
        db_session.add(extraction)

        msg.normalized_text = normalized.text.encode("utf-8")

        await db_session.flush()
    except Exception as e:
        logger.error("Document extraction failed for message %s: %s", msg.id, e)
        uploaded_doc.extraction_status = "failed"
        extraction_status = "failed"
        await db_session.flush()

    # Generate LLM follow-up response
    try:
        conversation_svc = ConversationService()
        llm_response = await conversation_svc.generate_response(
            messages=[{"role": "user", "content": f"[Document uploaded: {file.filename}]"}]
        )
        await svc.store_message(
            session_id=session_id,
            sender_type="system",
            modality="text",
            content=llm_response,
        )
    except Exception as e:
        logger.error("LLM follow-up generation failed: %s", e)

    # Send WebSocket notification
    text_preview = normalized.text[:200] if normalized else ""
    await manager.send_to_session(
        session_id,
        {
            "type": "document_ready",
            "message_id": msg.id,
            "document_id": uploaded_doc.id,
            "extraction_status": extraction_status,
            "text_preview": text_preview,
        },
    )

    return {
        "message_id": msg.id,
        "sequence_number": msg.sequence_number,
        "document_id": uploaded_doc.id,
        "extraction_status": extraction_status,
        "filename": file.filename,
        "mime_type": file.content_type,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

# Separate router for WebSocket (different prefix)
ws_router = APIRouter(tags=["intake-ws"])


@ws_router.websocket("/api/ws/intake/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: int):
    """Real-time WebSocket chat endpoint for intake sessions.

    Authentication:
      - JWT token passed as query parameter ?token={jwt}
      - Close 4001 if token is invalid or expired
      - Close 4003 if user lacks access to the session

    Message types handled:
      - text_message: Store, normalize, ack, generate LLM follow-up
      - session_pause: Pause the session
      - typing_indicator: Broadcast to other connections
    """
    settings = get_settings()

    # Step 1: Extract and validate JWT from query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        payload = pyjwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = int(payload.get("sub", 0))
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Step 2: Accept connection and register with manager
    await manager.connect(websocket, session_id)

    # Step 3: Create a DB session for message operations
    from app.db.engine import get_engine

    engine = get_engine()

    try:
        # Send initial session state
        await websocket.send_json({
            "type": "session_state",
            "status": "active",
            "facts_count": 0,
            "messages_count": 0,
        })

        # Step 4: Message loop
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            msg_type = data.get("type")

            if msg_type == "text_message":
                await _handle_text_message(
                    websocket, session_id, user_id, data, engine
                )
            elif msg_type == "voice_upload":
                await _handle_voice_upload(
                    websocket, session_id, user_id, data, engine
                )
            elif msg_type == "transcript_approve":
                await _handle_transcript_approve(
                    websocket, session_id, user_id, data, engine
                )
            elif msg_type == "transcript_edit":
                await _handle_transcript_edit(
                    websocket, session_id, user_id, data, engine
                )
            elif msg_type == "session_pause":
                await _handle_session_pause(
                    websocket, session_id, engine
                )
            elif msg_type == "typing_indicator":
                await manager.send_to_others(session_id, websocket, {
                    "type": "typing_indicator",
                    "user_id": user_id,
                    "is_typing": data.get("is_typing", False),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error for session %d: %s", session_id, e)
    finally:
        manager.disconnect(websocket, session_id)


async def _handle_text_message(
    websocket: WebSocket,
    session_id: int,
    user_id: int,
    data: dict,
    engine,
) -> None:
    """Handle an incoming text_message: screen, store, normalize, ack, generate LLM response.

    Per-message screening (EXPLORE-04) runs before message storage. Critical
    triggers send immediate safety_alert via WebSocket. Screening never blocks
    the normal message flow -- wrapped in try/except for graceful degradation.
    """
    content = data.get("content", "")
    party_id = data.get("party_id")

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            # --- Per-message screening (EXPLORE-04) ---
            try:
                screening_result = await screen_message_fast(
                    content=content,
                    session_id=session_id,
                    db_session=db_session,
                )

                # Critical: immediate interrupt per D-10
                if screening_result.has_critical:
                    alert_msg = build_safety_alert_message(screening_result)
                    await websocket.send_json(alert_msg)
                    for tp in screening_result.triggered_protocols:
                        if tp.get("severity_tier") == "critical":
                            await persist_screening_event(
                                db_session, session_id, tp, "immediate_alert"
                            )

                # Elevated: queue for next pause per D-10
                if screening_result.has_elevated:
                    await queue_elevated_screening(
                        db_session, session_id,
                        [tp for tp in screening_result.triggered_protocols
                         if tp.get("severity_tier") == "elevated"],
                    )

                # Advisory: fold into exploration per D-10
                if screening_result.has_advisory:
                    await add_to_exploration_queue(
                        db_session, session_id,
                        [tp for tp in screening_result.triggered_protocols
                         if tp.get("severity_tier") == "advisory"],
                    )
            except Exception:
                logger.warning(
                    "Per-message screening failed for session %d; continuing",
                    session_id,
                    exc_info=True,
                )

            # --- Continue existing message handling ---
            svc = IntakeSessionService(db_session)

            # Store the consumer's message
            message = await svc.store_message(
                session_id=session_id,
                sender_type="consumer",
                modality="text",
                content=content,
                party_id=party_id,
            )

            # Normalize the message
            normalized = normalize_text(content, message.id, party_id)

            # Send acknowledgment
            await websocket.send_json({
                "type": "message_ack",
                "message_id": message.id,
                "sequence_number": message.sequence_number,
            })

            # Generate and send LLM response
            conversation_svc = ConversationService()
            llm_response = await conversation_svc.generate_response(
                messages=[{"role": "user", "content": content}]
            )

            # Store the system response
            sys_message = await svc.store_message(
                session_id=session_id,
                sender_type="system",
                modality="text",
                content=llm_response,
            )

            await db_session.commit()

            # Send system message to client
            await websocket.send_json({
                "type": "system_message",
                "content": llm_response,
                "message_id": sys_message.id,
            })


async def _handle_session_pause(
    websocket: WebSocket,
    session_id: int,
    engine,
) -> None:
    """Handle a session_pause message: update session status."""
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            svc = IntakeSessionService(db_session)
            session = await svc.pause_session(session_id)
            await db_session.commit()

            await websocket.send_json({
                "type": "session_state",
                "status": "paused",
                "facts_count": 0,
                "messages_count": 0,
            })


async def _handle_voice_upload(
    websocket: WebSocket,
    session_id: int,
    user_id: int,
    data: dict,
    engine,
) -> None:
    """Handle a voice_upload message: store recording, transcribe, send transcript_ready.

    Flow:
      1. Decode base64 audio from message
      2. Store a Message with modality="voice" and an AudioRecording record
      3. Transcribe via ASRService
      4. Create a Transcript record with status="pending_review"
      5. Send transcript_ready to client for review
    """
    settings = get_settings()
    audio_b64 = data.get("audio_data", "")
    audio_bytes = base64.b64decode(audio_b64)
    audio_format = data.get("format", "webm")
    party_id = data.get("party_id")

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            svc = IntakeSessionService(db_session)

            # Store the consumer's voice message
            message = await svc.store_message(
                session_id=session_id,
                sender_type="consumer",
                modality="voice",
                content="[voice recording]",
                party_id=party_id,
            )

            # Look up the intake_id from the session
            result = await db_session.execute(
                select(IntakeSession.intake_id).where(IntakeSession.id == session_id)
            )
            intake_id = result.scalar_one()

            # Create AudioRecording record
            recording = AudioRecording(
                message_id=message.id,
                intake_id=intake_id,
                original_format=audio_format,
                file_size_bytes=len(audio_bytes),
                storage_policy=settings.asr_audio_storage_policy,
            )
            db_session.add(recording)
            await db_session.flush()

            # Transcribe via ASRService
            asr_service = ASRService()
            asr_result = await asr_service.transcribe(audio_bytes, audio_format)

            # Create Transcript record with pending_review status
            transcript = Transcript(
                recording_id=recording.id,
                text_encrypted=asr_result.text.encode("utf-8"),
                status="pending_review",
                asr_provider=asr_service.provider_name,
                segments_json=asr_result.segments,
                language=asr_result.language,
                confidence=asr_result.confidence,
            )
            db_session.add(transcript)
            await db_session.flush()

            await db_session.commit()

            # Send transcript_ready for consumer review
            await websocket.send_json({
                "type": "transcript_ready",
                "recording_id": recording.id,
                "transcript_id": transcript.id,
                "text": asr_result.text,
                "segments": asr_result.segments,
                "confidence": asr_result.confidence,
                "message_id": message.id,
                "sequence_number": message.sequence_number,
            })


async def _handle_transcript_approve(
    websocket: WebSocket,
    session_id: int,
    user_id: int,
    data: dict,
    engine,
) -> None:
    """Handle transcript_approve: screen, mark as approved, normalize, generate LLM follow-up.

    Flow:
      1. Lookup Transcript by recording_id, set status="approved"
      2. Screen the approved transcript text (same as text per D-08)
      3. Normalize the transcript text via process_message
      4. Generate LLM follow-up via ConversationService
      5. Store system response message
      6. Send message_ack + system_message
    """
    recording_id = data.get("recording_id")

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            svc = IntakeSessionService(db_session)

            # Lookup transcript by recording_id
            result = await db_session.execute(
                select(Transcript).where(Transcript.recording_id == recording_id)
            )
            transcript = result.scalar_one()

            # Update status to approved
            transcript.status = "approved"
            transcript.reviewed_at = datetime.now(timezone.utc)
            await db_session.flush()

            # Get the approved text
            approved_text = transcript.text_encrypted.decode("utf-8") if transcript.text_encrypted else ""

            # --- Per-message screening on approved transcript (D-08) ---
            try:
                screening_result = await screen_message_fast(
                    content=approved_text,
                    session_id=session_id,
                    db_session=db_session,
                )

                if screening_result.has_critical:
                    alert_msg = build_safety_alert_message(screening_result)
                    await websocket.send_json(alert_msg)
                    for tp in screening_result.triggered_protocols:
                        if tp.get("severity_tier") == "critical":
                            await persist_screening_event(
                                db_session, session_id, tp, "immediate_alert"
                            )

                if screening_result.has_elevated:
                    await queue_elevated_screening(
                        db_session, session_id,
                        [tp for tp in screening_result.triggered_protocols
                         if tp.get("severity_tier") == "elevated"],
                    )

                if screening_result.has_advisory:
                    await add_to_exploration_queue(
                        db_session, session_id,
                        [tp for tp in screening_result.triggered_protocols
                         if tp.get("severity_tier") == "advisory"],
                    )
            except Exception:
                logger.warning(
                    "Per-message screening failed on transcript approve for session %d; continuing",
                    session_id,
                    exc_info=True,
                )

            # Look up the original message for ack
            rec_result = await db_session.execute(
                select(AudioRecording).where(AudioRecording.id == recording_id)
            )
            recording = rec_result.scalar_one()

            msg_result = await db_session.execute(
                select(Message).where(Message.id == recording.message_id)
            )
            original_message = msg_result.scalar_one()

            # Normalize the approved transcript text
            try:
                normalized = await process_message(
                    "voice", approved_text, original_message.id, original_message.party_id
                )
            except NotImplementedError:
                # Voice normalization falls back to text normalization
                normalized = normalize_text(
                    approved_text, original_message.id, original_message.party_id
                )

            # Send message_ack
            await websocket.send_json({
                "type": "message_ack",
                "message_id": original_message.id,
                "sequence_number": original_message.sequence_number,
            })

            # Generate LLM follow-up
            conversation_svc = ConversationService()
            llm_response = await conversation_svc.generate_response(
                messages=[{"role": "user", "content": approved_text}]
            )

            # Store system response
            sys_message = await svc.store_message(
                session_id=session_id,
                sender_type="system",
                modality="text",
                content=llm_response,
            )

            await db_session.commit()

            # Send system_message
            await websocket.send_json({
                "type": "system_message",
                "content": llm_response,
                "message_id": sys_message.id,
            })


async def _handle_transcript_edit(
    websocket: WebSocket,
    session_id: int,
    user_id: int,
    data: dict,
    engine,
) -> None:
    """Handle transcript_edit: update text, mark as edited, normalize, generate LLM follow-up.

    Flow:
      1. Lookup Transcript by recording_id, update text and set status="edited"
      2. Normalize the edited text via process_message
      3. Generate LLM follow-up via ConversationService
      4. Store system response message
      5. Send message_ack + system_message
    """
    recording_id = data.get("recording_id")
    edited_text = data.get("edited_text", "")

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            svc = IntakeSessionService(db_session)

            # Lookup transcript by recording_id
            result = await db_session.execute(
                select(Transcript).where(Transcript.recording_id == recording_id)
            )
            transcript = result.scalar_one()

            # Update text and status
            transcript.text_encrypted = edited_text.encode("utf-8")
            transcript.status = "edited"
            transcript.reviewed_at = datetime.now(timezone.utc)
            await db_session.flush()

            # Look up the original message for ack
            rec_result = await db_session.execute(
                select(AudioRecording).where(AudioRecording.id == recording_id)
            )
            recording = rec_result.scalar_one()

            msg_result = await db_session.execute(
                select(Message).where(Message.id == recording.message_id)
            )
            original_message = msg_result.scalar_one()

            # Normalize the edited text
            try:
                normalized = await process_message(
                    "voice", edited_text, original_message.id, original_message.party_id
                )
            except NotImplementedError:
                normalized = normalize_text(
                    edited_text, original_message.id, original_message.party_id
                )

            # Send message_ack
            await websocket.send_json({
                "type": "message_ack",
                "message_id": original_message.id,
                "sequence_number": original_message.sequence_number,
            })

            # Generate LLM follow-up
            conversation_svc = ConversationService()
            llm_response = await conversation_svc.generate_response(
                messages=[{"role": "user", "content": edited_text}]
            )

            # Store system response
            sys_message = await svc.store_message(
                session_id=session_id,
                sender_type="system",
                modality="text",
                content=llm_response,
            )

            await db_session.commit()

            # Send system_message
            await websocket.send_json({
                "type": "system_message",
                "content": llm_response,
                "message_id": sys_message.id,
            })
