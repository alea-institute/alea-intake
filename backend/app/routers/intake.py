"""Consumer intake WebSocket + REST endpoints.

Provides real-time chat via WebSocket and REST endpoints for
intake CRUD and message history.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.user import User
from app.services.intake.session_service import IntakeSessionService


router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_intake(
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new intake."""
    svc = IntakeSessionService(session)
    intake = await svc.create_intake(
        org_id=user.org_id,
        user_id=user.id,
    )
    party = await svc.add_party(intake_id=intake.id, user_id=user.id)
    intake_session = await svc.create_session(intake_id=intake.id)
    await session.commit()
    return {
        "id": intake.id,
        "status": intake.status,
        "session_mode": intake.session_mode,
        "created_at": intake.created_at.isoformat() if intake.created_at else None,
        "session_id": intake_session.id,
        "party_id": party.id,
    }


@router.get("")
async def list_intakes(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List intakes for the authenticated user's tenant."""
    svc = IntakeSessionService(session)
    intakes = await svc.list_intakes(org_id=user.org_id)
    return [
        {
            "id": i.id,
            "status": i.status,
            "session_mode": i.session_mode,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in intakes
    ]
