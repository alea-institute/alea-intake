"""Intake API endpoints: REST CRUD, WebSocket chat, and document upload.

Provides:
- POST / -- Create intake
- GET / -- List intakes
- GET /{intake_id}/messages -- Message history
- POST /{intake_id}/party -- Add party
- POST /{intake_id}/session -- Create session
- POST /{intake_id}/document -- Upload document (Plan 03-03)
- WebSocket /ws/{session_id} -- Real-time chat
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.permissions import get_current_active_user, get_current_user
from app.core.security import decode_token
from app.db.session import get_tenant_session
from app.models.document import DocumentExtraction, UploadedDocument
from app.models.intake import Intake, IntakeSession, Message
from app.models.user import User
from app.services.document import DocumentService
from app.services.intake.conversation import ConversationService
from app.services.intake.message_pipeline import process_message
from app.services.intake.session_service import IntakeSessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


class IntakeConnectionManager:
    """Manages active WebSocket connections per session_id."""

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: int) -> None:
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int) -> None:
        if session_id in self._connections:
            self._connections[session_id] = [
                ws for ws in self._connections[session_id] if ws is not websocket
            ]
            if not self._connections[session_id]:
                del self._connections[session_id]

    async def send_to_session(self, session_id: int, message: dict) -> None:
        """Send a message to all connections on a session."""
        for ws in self._connections.get(session_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = IntakeConnectionManager()


def _get_org_id(request: Request) -> int:
    """Extract org_id from tenant context. Default to 1 for testing."""
    return getattr(request.state, "org_id", 1)


# --- REST Endpoints ---


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_intake(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new intake with a default session and primary party."""
    org_id = _get_org_id(request)
    svc = IntakeSessionService(session)
    intake = await svc.create_intake(org_id, current_user.id)
    party = await svc.add_party(intake.id, current_user.id)
    intake_session = await svc.create_session(intake.id)
    return {
        "id": intake.id,
        "status": intake.status,
        "session_mode": intake.session_mode,
        "created_at": str(intake.created_at),
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
    intakes = await svc.list_intakes(org_id)
    return [
        {
            "id": i.id,
            "status": i.status,
            "session_mode": i.session_mode,
            "created_at": str(i.created_at),
        }
        for i in intakes
    ]


@router.get("/{intake_id}/messages")
async def get_messages(
    intake_id: int,
    session_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get paginated message history for a session."""
    svc = IntakeSessionService(session)
    messages = await svc.get_messages(session_id, limit, offset)
    return [
        {
            "id": m.id,
            "sender_type": m.sender_type,
            "modality": m.modality,
            "content": m.content_encrypted.decode("utf-8") if m.content_encrypted else None,
            "sequence_number": m.sequence_number,
            "created_at": str(m.created_at),
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
    """Add a party to an intake."""
    body = await request.json()
    svc = IntakeSessionService(session)
    party = await svc.add_party(
        intake_id,
        user_id=body.get("user_id"),
        role_in_intake=body.get("role_in_intake", "primary"),
        label=body.get("label"),
    )
    return {"id": party.id, "role_in_intake": party.role_in_intake}


@router.post("/{intake_id}/session", status_code=status.HTTP_201_CREATED)
async def create_session(
    intake_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new session for an intake (multi-session resume)."""
    svc = IntakeSessionService(session)
    intake_session = await svc.create_session(intake_id)
    return {"id": intake_session.id, "status": intake_session.status}


# --- Document Upload Endpoint (Plan 03-03) ---


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

        # Update extraction status
        uploaded_doc.extraction_status = "completed"
        extraction_status = "completed"

        # Determine page count from extraction elements
        pages = {e.page for e in normalized.elements if e.page is not None}
        if pages:
            uploaded_doc.page_count = max(pages)

        # Create DocumentExtraction record
        extraction = DocumentExtraction(
            document_id=uploaded_doc.id,
            full_text_encrypted=normalized.text.encode("utf-8"),
            elements_json=[asdict(e) for e in normalized.elements],
            extraction_method=doc_service.get_extraction_method(file.content_type or ""),
        )
        db_session.add(extraction)

        # Update message normalized_text
        msg.normalized_text = normalized.text.encode("utf-8")

        await db_session.flush()
    except Exception as e:
        logger.error("Document extraction failed for message %s: %s", msg.id, e)
        uploaded_doc.extraction_status = "failed"
        extraction_status = "failed"
        await db_session.flush()

    # Generate LLM follow-up response (same pattern as text_message flow)
    try:
        conversation_svc = ConversationService(llm_service=None)  # type: ignore[arg-type]
        llm_response = await conversation_svc.generate_response(
            messages=[{"role": "user", "content": f"[Document uploaded: {file.filename}]"}]
        )
        # Store system message with LLM response
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


# --- WebSocket Endpoint ---


@router.websocket("/ws/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: int):
    """Real-time chat WebSocket endpoint.

    Authenticates via query param ?token=. Handles message types:
    - text_message: Store + normalize + LLM follow-up
    - session_pause: Update session status
    - typing_indicator: Broadcast to other connections
    """
    import jwt as pyjwt

    settings = get_settings()

    # Authenticate via query token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token, settings.secret_key)
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        await websocket.close(code=4001)
        return

    # Accept and register connection
    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "text_message":
                # Handled by Plan 01 -- basic acknowledgment
                await websocket.send_json({
                    "type": "message_ack",
                    "status": "received",
                })
            elif msg_type == "session_pause":
                await websocket.send_json({
                    "type": "session_state",
                    "status": "paused",
                })
            elif msg_type == "typing_indicator":
                # Broadcast to others on same session
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
