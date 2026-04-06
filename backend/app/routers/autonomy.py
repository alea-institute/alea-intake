"""Autonomy API endpoints: professional approval workflow.

REST endpoints for listing pending approval requests, approving, rejecting
(with guidance), editing stage output, and switching autonomy mode mid-intake.
All endpoints scoped to the current org via tenant session.

Approval endpoints call ApprovalQueue.resolve to unblock the pipeline.
Every action logs an AutonomyEvent via the audit logger.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.autonomy import ApprovalRequest
from app.models.organization import OrganizationConfig
from app.models.user import Role, User
from app.services.analysis.autonomy.approval_queue import ApprovalQueue
from app.services.analysis.autonomy.audit_logger import AutonomyAuditLogger
from app.services.analysis.autonomy.config import AutonomyConfig
from app.services.analysis.autonomy.schemas import (
    ApprovalAction,
    EditBody,
    ModeSwitchBody,
    RejectBody,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/autonomy",
    tags=["autonomy"],
    dependencies=[Depends(require_role(Role.PROFESSIONAL))],
)

# ---------------------------------------------------------------------------
# Module-scoped ApprovalQueue singleton
# ---------------------------------------------------------------------------

_approval_queue: ApprovalQueue | None = None


def get_approval_queue() -> ApprovalQueue:
    """Return the module-scoped ApprovalQueue instance."""
    if _approval_queue is None:
        raise RuntimeError("ApprovalQueue not initialized -- check lifespan setup")
    return _approval_queue


def set_approval_queue(queue: ApprovalQueue) -> None:
    """Set the module-scoped ApprovalQueue (called from main.py lifespan)."""
    global _approval_queue
    _approval_queue = queue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_request_or_404(
    request_id: int, db: AsyncSession
) -> ApprovalRequest:
    """Load an ApprovalRequest by ID or raise 404."""
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == request_id)
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/pending")
async def get_pending_requests(
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.PROFESSIONAL)),
) -> list[dict[str, Any]]:
    """List pending approval requests for the current org."""
    stmt = select(ApprovalRequest).where(ApprovalRequest.status == "pending")
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "iteration_id": r.iteration_id,
            "stage_name": r.stage_name,
            "status": r.status,
            "safety_triggered": r.safety_triggered,
            "is_rerun": r.is_rerun,
            "rerun_attempt": r.rerun_attempt,
            "guidance_text": r.guidance_text,
            "stage_output_json": r.stage_output_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.PROFESSIONAL)),
) -> dict[str, Any]:
    """Approve a pending approval request."""
    req = await _get_request_or_404(request_id, db)

    # Resolve in the in-memory queue
    queue = get_approval_queue()
    action = ApprovalAction(decision="approve", actor_id=user.id)

    try:
        queue.resolve(request_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        # Request may not be in in-memory queue (e.g., server restarted)
        pass

    # Update DB
    req.status = "approved"
    req.actor_id = user.id
    req.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    # Audit trail
    audit = AutonomyAuditLogger(db)
    await audit.log_approved(
        run_id=req.run_id,
        intake_id=0,  # intake_id not stored on ApprovalRequest; caller provides
        stage_name=req.stage_name,
        actor_id=user.id,
    )

    logger.info("Approved request %d by user %d", request_id, user.id)
    return {"id": request_id, "status": "approved"}


@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    body: RejectBody,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.PROFESSIONAL)),
) -> dict[str, Any]:
    """Reject a pending approval request with guidance text."""
    req = await _get_request_or_404(request_id, db)

    queue = get_approval_queue()
    action = ApprovalAction(
        decision="reject", actor_id=user.id, guidance_text=body.guidance_text
    )

    try:
        queue.resolve(request_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        pass

    req.status = "rejected"
    req.actor_id = user.id
    req.guidance_text = body.guidance_text
    req.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    audit = AutonomyAuditLogger(db)
    await audit.log_rejected(
        run_id=req.run_id,
        intake_id=0,
        stage_name=req.stage_name,
        actor_id=user.id,
        guidance=body.guidance_text,
    )

    logger.info("Rejected request %d by user %d", request_id, user.id)
    return {"id": request_id, "status": "rejected"}


@router.post("/requests/{request_id}/edit")
async def edit_request(
    request_id: int,
    body: EditBody,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.PROFESSIONAL)),
) -> dict[str, Any]:
    """Edit a pending approval request's stage output."""
    req = await _get_request_or_404(request_id, db)

    queue = get_approval_queue()
    action = ApprovalAction(
        decision="edit", actor_id=user.id, edits=body.edits
    )

    try:
        queue.resolve(request_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError:
        pass

    req.status = "edited"
    req.actor_id = user.id
    req.edited_output_json = body.edits
    req.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    audit = AutonomyAuditLogger(db)
    await audit.log_edited(
        run_id=req.run_id,
        intake_id=0,
        stage_name=req.stage_name,
        actor_id=user.id,
        edits=body.edits,
    )

    logger.info("Edited request %d by user %d", request_id, user.id)
    return {"id": request_id, "status": "edited"}


@router.post("/runs/{run_id}/switch-mode")
async def switch_mode(
    run_id: int,
    body: ModeSwitchBody,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.PROFESSIONAL)),
) -> dict[str, Any]:
    """Switch autonomy mode mid-intake (D-05).

    Updates OrganizationConfig.autonomy_config_json and logs a
    mode_change audit event.
    """
    # Load org config
    stmt = select(OrganizationConfig).where(
        OrganizationConfig.org_id == user.org_id
    )
    result = await db.execute(stmt)
    org_config = result.scalar_one_or_none()

    if org_config is None:
        raise HTTPException(
            status_code=404, detail="Organization config not found"
        )

    old_config_dict = org_config.autonomy_config_json or {}
    new_config_dict = body.config.model_dump()

    org_config.autonomy_config_json = new_config_dict
    await db.flush()

    # Audit trail
    audit = AutonomyAuditLogger(db)
    await audit.log_mode_change(
        run_id=run_id,
        intake_id=0,
        actor_id=user.id,
        old_config=old_config_dict,
        new_config=new_config_dict,
    )

    logger.info(
        "Mode switched for run %d by user %d: %s",
        run_id,
        user.id,
        body.reason,
    )
    return {"run_id": run_id, "mode_switched": True, "reason": body.reason}
