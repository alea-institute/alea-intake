"""Professional intake router: on-behalf-of note entry, structured forms, summaries.

All endpoints require PROFESSIONAL or ADMIN role. Professionals can create
intakes on behalf of consumers, submit notes with party attribution,
submit structured form data, and review intake summaries.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.fact import ExtractedFact
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.models.user import Role, User
from app.services.intake.message_pipeline import normalize_professional_note
from app.services.intake.session_service import IntakeSessionService


router = APIRouter(
    prefix="/api/v1/intake/professional",
    tags=["intake-professional"],
    dependencies=[Depends(require_role(Role.PROFESSIONAL, Role.ADMIN))],
)


# --- Request/Response schemas ---


class CreateIntakeRequest(BaseModel):
    """Request to create an intake on behalf of a consumer."""

    consumer_user_id: int | None = None
    session_mode: str = "multi_session"
    label: str | None = None


class NoteRequest(BaseModel):
    """Request to submit a professional note."""

    content: str
    party_id: int | None = None
    note_type: str = "general"


class StructuredFormInput(BaseModel):
    """Structured form data from a professional."""

    party_info: dict[str, Any] = Field(default_factory=dict)
    incident_details: str = ""
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    damages: list[dict[str, Any]] = Field(default_factory=list)
    additional_notes: str | None = None


# --- Endpoints ---


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_intake_on_behalf(
    body: CreateIntakeRequest,
    request: Request,
    user: User = Depends(require_role(Role.PROFESSIONAL, Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create an intake on behalf of a consumer."""
    svc = IntakeSessionService(session)

    intake = await svc.create_intake(
        org_id=user.org_id,
        user_id=user.id,
        session_mode=body.session_mode,
    )

    party = await svc.add_party(
        intake_id=intake.id,
        user_id=body.consumer_user_id,
        role_in_intake="primary",
        label=body.label or "Primary",
    )

    intake_session = await svc.create_session(intake_id=intake.id)
    await session.commit()

    return {
        "intake_id": intake.id,
        "session_id": intake_session.id,
        "party_id": party.id,
    }


@router.post("/{intake_id}/note")
async def submit_note(
    intake_id: int,
    body: NoteRequest,
    user: User = Depends(require_role(Role.PROFESSIONAL, Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Submit a professional note for an intake."""
    # Verify intake exists and belongs to same org
    result = await session.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")
    if intake.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get or create a session for storing the message
    sess_result = await session.execute(
        select(IntakeSession)
        .where(IntakeSession.intake_id == intake_id)
        .where(IntakeSession.status == "active")
        .order_by(IntakeSession.started_at.desc())
    )
    intake_session = sess_result.scalar_one_or_none()
    if intake_session is None:
        svc = IntakeSessionService(session)
        intake_session = await svc.create_session(intake_id=intake_id)

    svc = IntakeSessionService(session)
    message = await svc.store_message(
        session_id=intake_session.id,
        sender_type="professional",
        modality="professional_note",
        content=body.content,
        party_id=body.party_id,
        metadata_json={
            "note_type": body.note_type,
            "on_behalf_of": body.party_id,
            "professional_user_id": user.id,
        },
    )

    # Normalize through the pipeline
    normalize_professional_note(body.content, message.id, body.party_id)

    await session.commit()

    return {
        "message_id": message.id,
        "sequence_number": message.sequence_number,
    }


@router.post("/{intake_id}/structured-form")
async def submit_structured_form(
    intake_id: int,
    body: StructuredFormInput,
    user: User = Depends(require_role(Role.PROFESSIONAL, Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Submit structured form data, converted to narrative text."""
    # Verify intake exists and belongs to same org
    result = await session.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")
    if intake.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Convert structured form to narrative text
    narrative_parts: list[str] = []

    if body.party_info:
        pi = body.party_info
        parts = []
        if pi.get("name"):
            parts.append(f"Name: {pi['name']}")
        if pi.get("relationship"):
            parts.append(f"Relationship: {pi['relationship']}")
        if pi.get("contact"):
            parts.append(f"Contact: {pi['contact']}")
        if parts:
            narrative_parts.append("[PARTY INFO] " + "; ".join(parts))

    if body.incident_details:
        narrative_parts.append(f"[INCIDENT] {body.incident_details}")

    if body.timeline:
        timeline_items = [
            f"  - {item.get('date', 'N/A')}: {item.get('event', 'N/A')}"
            for item in body.timeline
        ]
        narrative_parts.append("[TIMELINE]\n" + "\n".join(timeline_items))

    if body.damages:
        damage_items = [
            f"  - {item.get('type', 'N/A')}: ${item.get('amount', 0):,.2f} - {item.get('description', 'N/A')}"
            for item in body.damages
        ]
        narrative_parts.append("[DAMAGES]\n" + "\n".join(damage_items))

    if body.additional_notes:
        narrative_parts.append(f"[NOTES] {body.additional_notes}")

    narrative_text = "\n\n".join(narrative_parts)

    # Get or create a session
    sess_result = await session.execute(
        select(IntakeSession)
        .where(IntakeSession.intake_id == intake_id)
        .where(IntakeSession.status == "active")
        .order_by(IntakeSession.started_at.desc())
    )
    intake_session = sess_result.scalar_one_or_none()
    if intake_session is None:
        svc = IntakeSessionService(session)
        intake_session = await svc.create_session(intake_id=intake_id)

    svc = IntakeSessionService(session)
    message = await svc.store_message(
        session_id=intake_session.id,
        sender_type="professional",
        modality="professional_note",
        content=narrative_text,
        metadata_json={
            "form_type": "structured",
            "original_form_data": body.model_dump(),
            "professional_user_id": user.id,
        },
    )

    # Normalize through the pipeline
    normalize_professional_note(narrative_text, message.id)

    await session.commit()

    return {
        "message_id": message.id,
        "sequence_number": message.sequence_number,
    }


@router.get("/{intake_id}/summary")
async def get_intake_summary(
    intake_id: int,
    user: User = Depends(require_role(Role.PROFESSIONAL, Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get intake summary for professional review."""
    # Verify intake exists and belongs to same org
    result = await session.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")
    if intake.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Count messages across all sessions
    sessions_result = await session.execute(
        select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
    )
    session_ids = [s for s in sessions_result.scalars().all()]

    messages_count = 0
    if session_ids:
        msg_count_result = await session.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id.in_(session_ids))
        )
        messages_count = msg_count_result.scalar() or 0

    # Count facts
    facts_count_result = await session.execute(
        select(func.count())
        .select_from(ExtractedFact)
        .where(ExtractedFact.intake_id == intake_id)
        .where(ExtractedFact.is_active == True)  # noqa: E712
    )
    facts_count = facts_count_result.scalar() or 0

    # Get parties
    parties_result = await session.execute(
        select(IntakeParty).where(IntakeParty.intake_id == intake_id)
    )
    parties = [
        {
            "id": p.id,
            "role": p.role_in_intake,
            "label": p.label,
            "user_id": p.user_id,
        }
        for p in parties_result.scalars().all()
    ]

    return {
        "intake_id": intake.id,
        "status": intake.status,
        "parties": parties,
        "messages_count": messages_count,
        "facts_count": facts_count,
        "created_at": intake.created_at.isoformat() if intake.created_at else None,
        "updated_at": intake.updated_at.isoformat() if intake.updated_at else None,
    }
