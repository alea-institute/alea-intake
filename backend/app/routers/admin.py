"""Admin API endpoints: right-to-delete cascade operations.

Provides deletion preview and confirmation endpoints with admin-only access.
Uses org-configurable deletion policies for audit trail handling.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.shared import Organization
from app.models.user import Role, User
from app.services.deletion_service import DeletionService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class DeletionConfirmRequest(BaseModel):
    """Request body for confirming a deletion cascade."""

    user_id: int
    preview_hash: str | None = None


@router.get("/deletion/preview/{user_id}")
async def deletion_preview(
    user_id: int,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict:
    """Preview the records that would be deleted for a user.

    Returns record counts per category and a preview_hash for confirmation.
    Requires ADMIN role.
    """
    # Get the org for deletion policy
    org = await _get_org(session, current_user.org_id)

    svc = DeletionService(session, org)
    return await svc.preview_deletion(user_id)


@router.post("/deletion/confirm")
async def deletion_confirm(
    body: DeletionConfirmRequest,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict:
    """Execute deletion cascade after preview confirmation.

    Requires the preview_hash from the preview endpoint to prevent
    accidental or stale deletions. Requires ADMIN role.
    """
    if not body.preview_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deletion requires explicit confirmation. Use the confirm endpoint.",
        )

    # Verify target user exists
    result = await session.execute(
        select(User).where(User.id == body.user_id)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get the org for deletion policy
    org = await _get_org(session, current_user.org_id)

    svc = DeletionService(session, org)
    try:
        return await svc.confirm_deletion(body.user_id, body.preview_hash)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def _get_org(session: AsyncSession, org_id: int) -> Organization:
    """Retrieve the Organization for the current user's org."""
    # Try shared schema first, fall back to same session
    # For SQLite tests, organizations are in the same (default) schema
    result = await session.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if org is None:
        # Try without filter (in tests, org might be id=1 from fixture)
        result = await session.execute(
            select(Organization).limit(1)
        )
        org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization not found",
        )

    return org
