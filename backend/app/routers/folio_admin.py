"""FOLIO admin API endpoints: OWL lifecycle management and unmapped concept review.

Provides admin-only endpoints for:
- Checking OWL cache status (ETag, freshness)
- Triggering manual OWL update checks
- Rolling back to previous OWL version
- Reviewing unmapped concepts with pagination and org filtering
- Viewing current FOLIO configuration
"""

import asyncio

from fastapi import APIRouter, Depends, Query
from folio import FOLIO
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role
from app.services.folio.folio_service import reload_folio
from app.services.folio.owl_cache import get_owl_status, rollback_owl
from app.services.folio.owl_updater import OWLUpdateManager

router = APIRouter(
    prefix="/api/v1/admin/folio",
    tags=["folio-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("/owl/status")
async def get_owl_status_endpoint():
    """Get current OWL cache status: cached, etag, last_checked, content_hash."""
    status = get_owl_status()
    return status


@router.post("/owl/update")
async def trigger_owl_update():
    """Trigger a manual OWL freshness check and update if stale."""
    manager = OWLUpdateManager.get_instance()
    updated = await manager.check_and_update()
    return {"updated": updated}


@router.post("/owl/rollback")
async def trigger_owl_rollback():
    """Rollback to previous OWL version and reload the FOLIO singleton."""
    rolled_back = rollback_owl()
    if rolled_back:
        # Reload FOLIO from the restored OWL file
        settings = get_settings()
        loop = asyncio.get_event_loop()
        new_folio = await loop.run_in_executor(
            None, lambda: FOLIO(github_repo_branch=settings.folio_owl_branch)
        )
        reload_folio(new_folio)
    return {"rolled_back": rolled_back}


@router.get("/unmapped")
async def list_unmapped_concepts(
    session: AsyncSession = Depends(get_tenant_session),
    org_id: int | None = Query(None, description="Filter by organization ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List unmapped concepts, optionally filtered by org. Paginated."""
    from app.models.folio_concepts import UnmappedConceptRecord

    query = select(UnmappedConceptRecord)
    count_query = select(func.count()).select_from(UnmappedConceptRecord)

    if org_id is not None:
        query = query.where(UnmappedConceptRecord.org_id == org_id)
        count_query = count_query.where(UnmappedConceptRecord.org_id == org_id)

    query = query.order_by(UnmappedConceptRecord.created_at.desc())
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    records = result.scalars().all()

    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    return {
        "items": [
            {
                "id": r.id,
                "local_iri": r.local_iri,
                "original_text": r.original_text,
                "suggested_branch": r.suggested_branch,
                "unmapped_confidence": r.unmapped_confidence,
                "nearest_iris": r.nearest_iris,
                "org_id": r.org_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/config")
async def get_folio_config():
    """Get current FOLIO configuration values."""
    settings = get_settings()
    return {
        "owl_branch": settings.folio_owl_branch,
        "update_interval_hours": settings.folio_update_interval_hours,
        "confidence_threshold": settings.folio_confidence_threshold,
        "traversal_depth": settings.folio_traversal_depth,
        "cache_dir": settings.folio_cache_dir,
    }
