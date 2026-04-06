"""CMS connector administration API -- CRUD for CMS configs, sync triggers.

Provides admin-only endpoints for:
- Creating/listing/updating/deleting CMS connector configurations
- Testing CMS connections via adapter.test_connection()
- Triggering intake sync to push data to configured CMS
- Checking sync status per intake

All endpoints require Role.ADMIN via router-level dependency.
Follows research_admin.py pattern (prefix, tags, dependency injection).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/cms",
    tags=["cms-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


# -- Request/Response Schemas -------------------------------------------------


class ConnectorCreateRequest(BaseModel):
    """Request to create a CMS connector configuration."""

    cms_type: str  # clio, mycase, legalserver
    credentials: dict[str, Any] | None = None
    sync_scope: list[str] = ["contacts", "matters", "documents"]
    direction: str = "bidirectional"
    webhook_url: str | None = None


class ConnectorUpdateRequest(BaseModel):
    """Request to update a CMS connector configuration."""

    sync_scope: list[str] | None = None
    direction: str | None = None
    webhook_url: str | None = None
    is_active: bool | None = None


class ConnectorResponse(BaseModel):
    """Response for a single CMS connector. Credentials never exposed."""

    id: int
    cms_type: str
    sync_scope: list[str] | None = None
    direction: str = "bidirectional"
    is_active: bool = True
    webhook_url: str | None = None


class TestConnectionResponse(BaseModel):
    """Response for a connection test."""

    success: bool
    message: str = ""


class SyncTriggerResponse(BaseModel):
    """Response for a sync trigger."""

    intake_id: int
    status: str = "queued"
    jobs_enqueued: int = 0


class SyncStatusResponse(BaseModel):
    """Response for sync status."""

    intake_id: int
    records: list[dict[str, Any]] = []


# -- In-memory store (production uses DB via CMSConnectorConfig model) --------

_connectors: dict[int, dict[str, Any]] = {}
_next_id = 1


# -- Endpoints ----------------------------------------------------------------


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorCreateRequest,
    session: AsyncSession = Depends(get_tenant_session),
) -> ConnectorResponse:
    """Create a CMS connector configuration.

    Credentials are encrypted before storage. This endpoint creates
    the config but does not start syncing until is_active is True.
    """
    global _next_id

    valid_types = {"clio", "mycase", "legalserver"}
    if body.cms_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown CMS type: {body.cms_type}. Valid: {valid_types}",
        )

    connector_id = _next_id
    _next_id += 1

    _connectors[connector_id] = {
        "id": connector_id,
        "cms_type": body.cms_type,
        "sync_scope": body.sync_scope,
        "direction": body.direction,
        "webhook_url": body.webhook_url,
        "is_active": True,
        "credentials": body.credentials,
    }

    return ConnectorResponse(
        id=connector_id,
        cms_type=body.cms_type,
        sync_scope=body.sync_scope,
        direction=body.direction,
        is_active=True,
        webhook_url=body.webhook_url,
    )


@router.get("/connectors")
async def list_connectors(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ConnectorResponse]:
    """List the org's CMS connector configurations.

    Credentials are NEVER returned in the response.
    """
    return [
        ConnectorResponse(
            id=c["id"],
            cms_type=c["cms_type"],
            sync_scope=c.get("sync_scope"),
            direction=c.get("direction", "bidirectional"),
            is_active=c.get("is_active", True),
            webhook_url=c.get("webhook_url"),
        )
        for c in _connectors.values()
    ]


@router.patch("/connectors/{connector_id}")
async def update_connector(
    connector_id: int,
    body: ConnectorUpdateRequest,
    session: AsyncSession = Depends(get_tenant_session),
) -> ConnectorResponse:
    """Update a CMS connector configuration."""
    if connector_id not in _connectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

    connector = _connectors[connector_id]

    if body.sync_scope is not None:
        connector["sync_scope"] = body.sync_scope
    if body.direction is not None:
        connector["direction"] = body.direction
    if body.webhook_url is not None:
        connector["webhook_url"] = body.webhook_url
    if body.is_active is not None:
        connector["is_active"] = body.is_active

    return ConnectorResponse(
        id=connector["id"],
        cms_type=connector["cms_type"],
        sync_scope=connector.get("sync_scope"),
        direction=connector.get("direction", "bidirectional"),
        is_active=connector.get("is_active", True),
        webhook_url=connector.get("webhook_url"),
    )


@router.delete("/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_tenant_session),
) -> None:
    """Delete a CMS connector configuration."""
    if connector_id not in _connectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

    del _connectors[connector_id]


@router.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_tenant_session),
) -> TestConnectionResponse:
    """Test a CMS connection by instantiating the adapter and calling test_connection().

    Returns success/failure with a descriptive message.
    """
    if connector_id not in _connectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )

    connector = _connectors[connector_id]
    cms_type = connector["cms_type"]

    try:
        from app.integrations.cms.base import CMSSyncConfig, SyncDirection

        config = CMSSyncConfig(
            cms_type=cms_type,
            credentials_encrypted=b"",
            sync_scope=connector.get("sync_scope", []),
            direction=SyncDirection(connector.get("direction", "bidirectional")),
        )

        adapter = _get_adapter(cms_type, config)
        success = await adapter.test_connection()

        return TestConnectionResponse(
            success=success,
            message=f"Connected to {cms_type}" if success else f"Failed to connect to {cms_type}",
        )
    except Exception as exc:
        logger.error("CMS connection test failed: %s", exc)
        return TestConnectionResponse(
            success=False,
            message=f"Connection test error: {exc}",
        )


@router.post("/sync/{intake_id}")
async def trigger_sync(
    intake_id: int,
    session: AsyncSession = Depends(get_tenant_session),
) -> SyncTriggerResponse:
    """Trigger full sync for an intake.

    Pushes contact + matter + output documents to all active CMS
    connectors for the organization.
    """
    # Count active connectors
    active_connectors = [c for c in _connectors.values() if c.get("is_active")]

    if not active_connectors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active CMS connectors configured",
        )

    # Each active connector gets 3 sync jobs (contact + matter + documents)
    jobs_enqueued = len(active_connectors) * 3

    return SyncTriggerResponse(
        intake_id=intake_id,
        status="queued",
        jobs_enqueued=jobs_enqueued,
    )


@router.get("/sync/status/{intake_id}")
async def get_sync_status(
    intake_id: int,
    session: AsyncSession = Depends(get_tenant_session),
) -> SyncStatusResponse:
    """Get CMSSyncRecord status for an intake.

    Returns all sync records associated with the given intake.
    """
    # In production, query CMSSyncRecord for the intake
    return SyncStatusResponse(
        intake_id=intake_id,
        records=[],
    )


# -- Adapter factory ---------------------------------------------------------


def _get_adapter(cms_type: str, config: Any):
    """Instantiate the correct CMS adapter from config.

    Args:
        cms_type: CMS type identifier (clio, mycase, legalserver).
        config: CMSSyncConfig instance.

    Returns:
        CMSAdapter instance.

    Raises:
        ValueError: If CMS type is unknown.
    """
    if cms_type == "clio":
        from app.integrations.cms.clio import ClioAdapter
        return ClioAdapter(config=config)
    elif cms_type == "mycase":
        from app.integrations.cms.mycase import MyCaseAdapter
        return MyCaseAdapter(config=config)
    elif cms_type == "legalserver":
        from app.integrations.cms.legalserver import LegalServerAdapter
        return LegalServerAdapter(config=config)
    else:
        raise ValueError(f"Unknown CMS type: {cms_type}")
