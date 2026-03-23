"""Audit log query endpoints -- admin-only access to immutable audit trail.

Provides list and detail endpoints with filtering by action, actor, and
date range. Only users with the ADMIN role can access these endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role, User
from app.schemas.audit import AuditLogQuery, AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/", response_model=list[AuditLogResponse])
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by action"),
    actor_id: int | None = Query(None, description="Filter by actor ID"),
    start_date: datetime | None = Query(None, description="Filter from date"),
    end_date: datetime | None = Query(None, description="Filter to date"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Skip results"),
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[AuditLogResponse]:
    """List audit log entries with optional filters.

    Requires ADMIN role. Returns entries ordered by timestamp DESC.
    """
    svc = AuditService(session)
    entries = await svc.query_logs(
        action=action,
        actor_id=actor_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return [AuditLogResponse.model_validate(e) for e in entries]


@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: int,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
) -> AuditLogResponse:
    """Get a single audit log entry by ID.

    Requires ADMIN role.
    """
    from sqlalchemy import select
    from app.models.audit import AuditLog

    result = await session.execute(
        select(AuditLog).where(AuditLog.id == audit_id)
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    return AuditLogResponse.model_validate(entry)
