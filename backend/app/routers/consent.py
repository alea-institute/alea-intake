"""Consent management API endpoints: grant, revoke, status, and template retrieval.

Supports both authenticated users and kiosk sessions (via X-Session-ID header).
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.user import User
from app.schemas.consent import ConsentGrantRequest, ConsentResponse, ConsentTemplateResponse
from app.services.consent_service import ConsentService

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


@router.post("/grant", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    body: ConsentGrantRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConsentResponse:
    """Grant consent with specified items.

    Creates a new consent record, revoking any existing active consent first.
    """
    svc = ConsentService(session)
    ip_address = request.client.host if request.client else None

    record = await svc.grant_consent(
        user_id=current_user.id,
        session_id=None,
        consent_version=body.consent_version,
        consent_items=body.consent_items,
        ip_address=ip_address,
    )
    return ConsentResponse.model_validate(record)


@router.post("/revoke", response_model=ConsentResponse)
async def revoke_consent(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConsentResponse:
    """Revoke active consent. Takes immediate effect.

    Returns the revoked consent record with revoked_at timestamp.
    """
    svc = ConsentService(session)
    revoked = await svc.revoke_consent(user_id=current_user.id)

    if revoked is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active consent found to revoke",
        )

    return ConsentResponse.model_validate(revoked)


@router.get("/status")
async def consent_status(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConsentResponse | None:
    """Get current consent status for the authenticated user.

    Returns the active consent record, or null if no active consent.
    """
    svc = ConsentService(session)
    record = await svc.get_consent_status(user_id=current_user.id)

    if record is None:
        return None

    return ConsentResponse.model_validate(record)


@router.get("/template", response_model=ConsentTemplateResponse | None)
async def get_consent_template(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConsentTemplateResponse | None:
    """Get the active consent template for the user's organization.

    Returns the template defining what consent options to present,
    or null if no template is configured.
    """
    svc = ConsentService(session)
    template = await svc.get_active_template(org_id=current_user.org_id)

    if template is None:
        return None

    return ConsentTemplateResponse.model_validate(template)
