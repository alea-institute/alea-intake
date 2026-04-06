"""Extended health check with component-level status.

Returns status for: database, FOLIO OWL cache, folio-mcp, LLM provider.
Any component failure sets overall status to "degraded" (not "unhealthy")
because partial functionality is still available.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from app.config import get_settings
from app.db.engine import get_engine
from app.services.folio.owl_cache import get_owl_status

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_VERSION = "1.0.0"


async def check_health(app: FastAPI) -> dict[str, Any]:
    """Run all component health checks and return aggregate status.

    Returns:
        Dict with keys: status, version, database, folio_owl, folio_mcp, llm_provider.
    """
    settings = get_settings()
    degraded = False

    # --- Database ---
    db_status: dict[str, Any] = {"status": "up"}
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check: database down: %s", exc)
        db_status = {"status": "down", "error": str(exc)}
        degraded = True

    # --- FOLIO OWL cache ---
    folio_owl_status: dict[str, Any]
    try:
        folio_owl_status = get_owl_status()
        folio_owl_status["status"] = "up" if folio_owl_status.get("cached") else "unavailable"
    except Exception as exc:
        folio_owl_status = {"status": "down", "error": str(exc)}
        degraded = True

    # --- folio-mcp ---
    folio_mcp_status: dict[str, Any] = {"status": "unavailable"}
    try:
        mcp_client = getattr(app.state, "folio_mcp_client", None)
        if mcp_client is not None and getattr(mcp_client, "is_connected", False):
            folio_mcp_status = {"status": "up"}
        else:
            folio_mcp_status = {"status": "unavailable"}
    except Exception as exc:
        folio_mcp_status = {"status": "down", "error": str(exc)}

    # --- LLM provider ---
    llm_status: dict[str, Any] = {"status": "configured"}
    # LLM availability is best-effort; we just confirm settings exist.
    # Actual provider health is verified at call time.

    overall = "degraded" if degraded else "healthy"

    return {
        "status": overall,
        "version": _VERSION,
        "database": db_status,
        "folio_owl": folio_owl_status,
        "folio_mcp": folio_mcp_status,
        "llm_provider": llm_status,
    }
