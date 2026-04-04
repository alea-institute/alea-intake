"""Screening protocol admin API endpoints: protocol CRUD and activation management.

Provides admin-only endpoints for:
- Creating and listing screening protocols
- Creating new protocol versions
- Activating/deactivating protocols per org with version pinning
- Listing org's active protocol activations

All endpoints require Role.ADMIN via router-level dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role
from app.services.screening.protocol_service import ProtocolService


router = APIRouter(
    prefix="/api/v1/admin/screening",
    tags=["screening-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


# -- Request/Response Schemas -------------------------------------------------


class ProtocolCreateRequest(BaseModel):
    name: str
    slug: str
    severity_tier: str
    description: str | None = None
    trigger_conditions: dict
    questions: list
    escalation_actions: dict
    safety_resources: dict | None = None
    is_shared: bool = False


class VersionCreateRequest(BaseModel):
    trigger_conditions: dict
    questions: list
    escalation_actions: dict
    safety_resources: dict | None = None
    version: str = "1.1.0"


class ActivateRequest(BaseModel):
    pinned_version_id: int
    activation_mode: str
    config: dict | None = None


# -- Endpoints ----------------------------------------------------------------


@router.post("/protocols", status_code=status.HTTP_201_CREATED)
async def create_protocol(
    body: ProtocolCreateRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new screening protocol with initial version.

    The protocol is owned by the admin's org. Set is_shared=True to make it
    visible in the community protocol pool.
    """
    svc = ProtocolService(session)
    try:
        protocol, version = await svc.create_protocol(
            name=body.name,
            slug=body.slug,
            severity_tier=body.severity_tier,
            description=body.description,
            owner_org_id=None,  # Will be set from request context in production
            is_shared=body.is_shared,
            trigger_conditions=body.trigger_conditions,
            questions=body.questions,
            escalation_actions=body.escalation_actions,
            safety_resources=body.safety_resources,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": protocol.id,
        "name": protocol.name,
        "slug": protocol.slug,
        "severity_tier": protocol.severity_tier,
        "is_shared": protocol.is_shared,
        "version_id": version.id,
        "version": version.version,
    }


@router.get("/protocols")
async def list_protocols(
    session: AsyncSession = Depends(get_tenant_session),
):
    """List protocols visible to the requesting org.

    Returns seed protocols + community shared + org's own private protocols.
    Excludes other organizations' private protocols.
    """
    svc = ProtocolService(session)
    # In production, org_id would come from request context
    protocols = await svc.list_protocols(org_id=None)
    return protocols


@router.get("/protocols/{protocol_id}")
async def get_protocol(
    protocol_id: int,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Get a single protocol with all its versions."""
    svc = ProtocolService(session)
    protocol = await svc.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return protocol


@router.post("/protocols/{protocol_id}/versions")
async def create_version(
    protocol_id: int,
    body: VersionCreateRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new version for an existing protocol."""
    svc = ProtocolService(session)
    version = await svc.create_version(
        protocol_id=protocol_id,
        trigger_conditions=body.trigger_conditions,
        questions=body.questions,
        escalation_actions=body.escalation_actions,
        safety_resources=body.safety_resources,
        version=body.version,
    )
    return {
        "id": version.id,
        "protocol_id": version.protocol_id,
        "version": version.version,
        "is_active": version.is_active,
    }


@router.post("/protocols/{protocol_id}/activate")
async def activate_protocol(
    protocol_id: int,
    body: ActivateRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Activate a protocol for the org with version pinning.

    activation_mode: "mandatory" (always runs), "optional" (professional toggle), "disabled".
    pinned_version_id: specific version to use (D-04 -- no "latest" auto-update).
    """
    svc = ProtocolService(session)
    try:
        activation = await svc.activate_protocol(
            protocol_id=protocol_id,
            pinned_version_id=body.pinned_version_id,
            activation_mode=body.activation_mode,
            config=body.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "protocol_id": activation.protocol_id,
        "pinned_version_id": activation.pinned_version_id,
        "activation_mode": activation.activation_mode,
    }


@router.post("/protocols/{protocol_id}/deactivate")
async def deactivate_protocol(
    protocol_id: int,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Deactivate a protocol (set activation_mode to 'disabled')."""
    svc = ProtocolService(session)
    await svc.deactivate(protocol_id=protocol_id)
    return {"status": "disabled", "protocol_id": protocol_id}


@router.get("/activations")
async def list_activations(
    session: AsyncSession = Depends(get_tenant_session),
):
    """List the org's active protocol activations with their pinned versions."""
    svc = ProtocolService(session)
    active = await svc.get_active_protocols()
    return [
        {
            "protocol_id": act.protocol_id,
            "pinned_version_id": act.pinned_version_id,
            "activation_mode": act.activation_mode,
            "version": ver.version if ver else None,
        }
        for act, ver in active
    ]
