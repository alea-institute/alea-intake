"""Autonomy admin API endpoints: config CRUD, stages, presets.

REST endpoints for reading/updating per-org autonomy configuration,
listing valid analysis stages, and fetching preset configs.
All endpoints require ADMIN role.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.organization import OrganizationConfig
from app.models.user import Role, User
from app.services.analysis.autonomy.audit_logger import AutonomyAuditLogger
from app.services.analysis.autonomy.config import (
    ANALYSIS_STAGES,
    AutonomyConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/autonomy/admin",
    tags=["autonomy-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("/config")
async def get_autonomy_config(
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Return current org autonomy config (defaults if null)."""
    stmt = select(OrganizationConfig).where(
        OrganizationConfig.org_id == user.org_id
    )
    result = await db.execute(stmt)
    org_config = result.scalar_one_or_none()

    if org_config is None or org_config.autonomy_config_json is None:
        # Return defaults
        return AutonomyConfig().model_dump()

    return AutonomyConfig.model_validate(
        org_config.autonomy_config_json
    ).model_dump()


@router.put("/config")
async def update_autonomy_config(
    body: AutonomyConfig,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Update org autonomy config (AUTONOMY-04, AUTONOMY-05)."""
    stmt = select(OrganizationConfig).where(
        OrganizationConfig.org_id == user.org_id
    )
    result = await db.execute(stmt)
    org_config = result.scalar_one_or_none()

    if org_config is None:
        # Create if not exists
        org_config = OrganizationConfig(
            org_id=user.org_id,
            autonomy_config_json=body.model_dump(),
        )
        db.add(org_config)
    else:
        old_config = org_config.autonomy_config_json or {}
        org_config.autonomy_config_json = body.model_dump()

        # Audit trail
        audit = AutonomyAuditLogger(db)
        await audit.log_event(
            run_id=0,
            intake_id=0,
            event_type="mode_set",
            actor_id=user.id,
            details={"old_config": old_config, "new_config": body.model_dump()},
        )

    await db.flush()

    logger.info("Updated autonomy config for org %d by user %d", user.org_id, user.id)
    return {"updated": True}


@router.get("/stages")
async def get_stages() -> dict[str, Any]:
    """Return list of valid analysis stage names (Pitfall 4 prevention).

    UI should render from this list, not hardcode stage names.
    """
    return {"stages": ANALYSIS_STAGES}


@router.get("/presets")
async def get_presets() -> dict[str, Any]:
    """Return dict of preset names to AutonomyConfig dicts."""
    return {
        "chatbot": AutonomyConfig.chatbot_preset().model_dump(),
        "professional": AutonomyConfig.professional_preset().model_dump(),
        "agent": AutonomyConfig.agent_preset().model_dump(),
    }
