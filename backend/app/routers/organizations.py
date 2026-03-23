"""Organization CRUD endpoints -- admin-only management of tenants.

All endpoints require Role.ADMIN. Organization creation triggers
tenant schema provisioning via TenantService.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_shared_session
from app.models.shared import Organization
from app.models.user import Role, User
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])

_tenant_service = TenantService()


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    body: OrganizationCreate,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_shared_session),
):
    """Create a new organization and provision its tenant schema.

    Requires admin role.
    """
    # Check for duplicate slug
    existing = await session.execute(
        select(Organization).where(Organization.slug == body.slug)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{body.slug}' already exists",
        )

    org = await _tenant_service.create_tenant(session, body)
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        auth_mode=org.auth_mode,
        is_active=org.is_active,
    )


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_shared_session),
):
    """List all organizations. Requires admin role."""
    orgs = await _tenant_service.list_tenants(session)
    return [
        OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            auth_mode=org.auth_mode,
            is_active=org.is_active,
        )
        for org in orgs
    ]


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: int,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_shared_session),
):
    """Get a single organization by ID. Requires admin role."""
    result = await session.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        auth_mode=org.auth_mode,
        is_active=org.is_active,
    )


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: int,
    body: dict,
    current_user: User = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_shared_session),
):
    """Partially update an organization. Requires admin role.

    Accepts a JSON object with any subset of Organization fields to update.
    Slug updates are not allowed (would break tenant schema naming).
    """
    result = await session.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Prevent slug changes (would break tenant schema references)
    if "slug" in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change organization slug",
        )

    # Apply allowed field updates
    allowed_fields = {"name", "auth_mode", "llm_data_policy", "consent_mode", "deletion_policy", "is_active"}
    for field, value in body.items():
        if field in allowed_fields:
            setattr(org, field, value)

    await session.flush()
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        auth_mode=org.auth_mode,
        is_active=org.is_active,
    )
