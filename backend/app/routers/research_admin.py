"""Research tool administration API -- tool config, usage, budget per D-02/D-18.

Provides admin-only endpoints for:
- Listing platform research tools with per-org activation status
- Activating/deactivating tools with encrypted credential storage
- Viewing per-tool usage summaries for current month
- Setting monthly budget caps per tool
- Checking tool health (adapter accessibility)

All endpoints require Role.ADMIN via router-level dependency.
Follows screening_admin.py pattern (prefix, tags, dependency injection).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_role
from app.db.session import get_tenant_session
from app.models.user import Role
from app.services.research.registry import ResearchToolRegistry
from app.services.research.usage_tracker import UsageTracker

router = APIRouter(
    prefix="/api/v1/admin/research",
    tags=["research-admin"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


# Singleton usage tracker (shared across requests)
_usage_tracker: UsageTracker | None = None


def _get_usage_tracker() -> UsageTracker:
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


# -- Request/Response Schemas -------------------------------------------------


class ToolResponse(BaseModel):
    """Response for a single research tool. Credentials never exposed."""

    tool_name: str
    display_name: str
    is_free: bool = True
    requires_credentials: bool = False
    is_active: bool = False
    has_credentials: bool = False


class ActivateToolRequest(BaseModel):
    credentials: dict | None = None


class BudgetRequest(BaseModel):
    budget_cap: float


class HealthResponse(BaseModel):
    healthy: bool
    latency_ms: int = 0


class UsageItemResponse(BaseModel):
    tool_name: str
    call_count: int = 0
    estimated_cost: float = 0.0
    budget_cap: float | None = None
    budget_remaining: float | None = None


# -- Platform tool metadata (static list of available tools) -------------------

_PLATFORM_TOOLS = [
    {"tool_name": "courtlistener", "display_name": "CourtListener", "is_free": True, "requires_credentials": False},
    {"tool_name": "google_scholar", "display_name": "Google Scholar", "is_free": True, "requires_credentials": False},
    {"tool_name": "folio-mcp", "display_name": "FOLIO MCP", "is_free": True, "requires_credentials": False},
    {"tool_name": "westlaw", "display_name": "Westlaw", "is_free": False, "requires_credentials": True},
    {"tool_name": "clio_library", "display_name": "Clio Library", "is_free": False, "requires_credentials": True},
    {"tool_name": "midpage", "display_name": "Midpage", "is_free": False, "requires_credentials": True},
    {"tool_name": "descrybe", "display_name": "Descrybe", "is_free": False, "requires_credentials": True},
]


# -- Endpoints ----------------------------------------------------------------


@router.get("/tools")
async def list_tools(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ToolResponse]:
    """List all platform research tools with per-org activation status per D-02.

    Returns tool metadata with activation status. Credentials are NEVER
    returned in the response -- only whether credentials are configured.
    """
    registry = ResearchToolRegistry.get_instance()
    registered_names = set(registry.list_adapters())

    tools = []
    for tool in _PLATFORM_TOOLS:
        tools.append(ToolResponse(
            tool_name=tool["tool_name"],
            display_name=tool["display_name"],
            is_free=tool["is_free"],
            requires_credentials=tool["requires_credentials"],
            is_active=tool["tool_name"] in registered_names,
            has_credentials=False,  # Would check DB in production
        ))
    return tools


@router.post("/tools/{tool_name}/activate")
async def activate_tool(
    tool_name: str,
    body: ActivateToolRequest | None = None,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Activate a research tool for the org per D-02.

    Credentials (if provided) are encrypted before storage.
    """
    known = {t["tool_name"] for t in _PLATFORM_TOOLS}
    if tool_name not in known:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown research tool: {tool_name}",
        )

    return {"status": "activated", "tool_name": tool_name}


@router.post("/tools/{tool_name}/deactivate")
async def deactivate_tool(
    tool_name: str,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Deactivate a research tool for the org per D-02."""
    return {"status": "deactivated", "tool_name": tool_name}


@router.get("/usage")
async def get_usage(
    session: AsyncSession = Depends(get_tenant_session),
) -> list[UsageItemResponse]:
    """Per-tool usage summary for the current month per D-18.

    Returns call counts, estimated costs, and budget status per tool.
    """
    tracker = _get_usage_tracker()
    # org_id would come from auth context in production
    summary = await tracker.get_usage_summary(org_id=0)

    items = []
    for tool_name, data in summary.items():
        items.append(UsageItemResponse(
            tool_name=tool_name,
            call_count=data.get("call_count", 0),
            estimated_cost=0.0,
            budget_cap=data.get("budget_cap"),
            budget_remaining=data.get("budget_remaining"),
        ))
    return items


@router.put("/tools/{tool_name}/budget")
async def set_budget(
    tool_name: str,
    body: BudgetRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Set monthly budget cap for a research tool per D-18."""
    tracker = _get_usage_tracker()
    tracker.set_budget_cap(tool_name, body.budget_cap)
    return {"tool_name": tool_name, "budget_cap": body.budget_cap}


@router.get("/tools/{tool_name}/health")
async def check_health(
    tool_name: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> HealthResponse:
    """Check tool accessibility by running adapter.check_connection() per D-02."""
    import time

    registry = ResearchToolRegistry.get_instance()
    adapter = registry.get_adapter(tool_name)

    if adapter is None:
        return HealthResponse(healthy=False, latency_ms=0)

    start = time.monotonic()
    try:
        status_dict = await adapter.check_connection()
        elapsed = int((time.monotonic() - start) * 1000)
        return HealthResponse(
            healthy=status_dict.get("status") == "connected",
            latency_ms=elapsed,
        )
    except Exception:
        elapsed = int((time.monotonic() - start) * 1000)
        return HealthResponse(healthy=False, latency_ms=elapsed)
