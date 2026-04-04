"""Intake API endpoints: REST CRUD and WebSocket real-time chat.

REST endpoints handle intake lifecycle (create, list, get messages, add party,
create session). The WebSocket endpoint handles real-time chat with JWT
authentication, message storage, normalization, and LLM-guided conversation.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

import jwt as pyjwt
from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.models.user import User
from app.services.intake.conversation import ConversationService
from app.services.intake.message_pipeline import normalize_text
from app.services.intake.session_service import IntakeSessionService

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
    """Handle an incoming text_message: store, normalize, ack, generate LLM response."""
    content = data.get("content", "")
    party_id = data.get("party_id")

    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
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
