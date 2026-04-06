"""Auto-migration runner for startup.

Reads deployment mode and runs pending Alembic migrations:
- Single-tenant: single `alembic upgrade head`
- Multi-tenant: shared schema first, then iterate tenant schemas (Pitfall 1)
  with per-schema failure isolation.
"""

import asyncio
import logging
import os
import subprocess

from app.config import get_settings
from app.deployment.mode import is_multi_tenant

logger = logging.getLogger(__name__)


async def _get_active_orgs() -> list:
    """Query all active organizations from the shared schema.

    Returns list of org objects with .slug attribute.
    """
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.engine import get_engine
    from app.models.shared import Organization

    engine = get_engine()
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": "shared"}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            result = await session.execute(
                select(Organization).where(Organization.is_active.is_(True))
            )
            return list(result.scalars().all())


def _run_alembic(args: list[str]) -> subprocess.CompletedProcess:
    """Run an alembic command synchronously.

    Args:
        args: Command arguments after 'alembic', e.g. ['upgrade', 'head'].

    Returns:
        CompletedProcess result.
    """
    cmd = ["alembic"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
    )


async def run_startup_migrations() -> dict[str, str]:
    """Run pending Alembic migrations on startup.

    Returns:
        Dict mapping schema names to migration status ('ok' or error message).
    """
    # Skip if env var is set (useful for testing)
    if os.environ.get("ALEA_SKIP_MIGRATIONS", "").lower() == "true":
        logger.info("ALEA_SKIP_MIGRATIONS=true; skipping auto-migration")
        return {}

    loop = asyncio.get_event_loop()
    results: dict[str, str] = {}

    if not is_multi_tenant():
        # Single-tenant: one migration run
        logger.info("Running single-tenant migration: alembic upgrade head")
        proc = await loop.run_in_executor(None, _run_alembic, ["upgrade", "head"])
        if proc.returncode == 0:
            results["public"] = "ok"
            logger.info("Single-tenant migration complete")
        else:
            results["public"] = proc.stderr or "unknown error"
            logger.error("Single-tenant migration failed: %s", proc.stderr)
    else:
        # Multi-tenant: shared schema first (Pitfall 1)
        logger.info("Running multi-tenant migrations: shared schema first")
        proc = await loop.run_in_executor(None, _run_alembic, ["upgrade", "head"])
        if proc.returncode == 0:
            results["shared"] = "ok"
            logger.info("Shared schema migration complete")
        else:
            results["shared"] = proc.stderr or "unknown error"
            logger.error("Shared schema migration failed: %s", proc.stderr)

        # Then each tenant schema
        orgs = await _get_active_orgs()
        for org in orgs:
            schema = f"tenant_{org.slug}"
            logger.info("Running migration for tenant schema: %s", schema)
            try:
                proc = await loop.run_in_executor(
                    None,
                    _run_alembic,
                    ["-x", f"tenant={schema}", "upgrade", "head"],
                )
                if proc.returncode == 0:
                    results[schema] = "ok"
                    logger.info("Migration complete for %s", schema)
                else:
                    results[schema] = proc.stderr or "unknown error"
                    logger.error(
                        "Migration failed for %s: %s", schema, proc.stderr
                    )
            except Exception as exc:
                results[schema] = str(exc)
                logger.error(
                    "Migration exception for %s: %s", schema, exc, exc_info=True
                )

    return results
