"""Async session factories with per-tenant schema routing.

get_tenant_session: Creates sessions with schema_translate_map for tenant isolation.
get_shared_session: Creates sessions against the shared schema for cross-tenant ops.
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_engine


def _is_sqlite() -> bool:
    """Check if the current engine is SQLite (no schema support)."""
    return "sqlite" in str(get_engine().url)


async def get_tenant_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession routed to the tenant's schema via schema_translate_map.

    Reads the tenant schema from request.state.tenant_schema, set by TenantMiddleware.
    Maps the logical 'tenant' schema name to the actual tenant_{org_slug} schema.
    For SQLite, schemas are mapped to None (default schema).
    """
    tenant_schema = getattr(request.state, "tenant_schema", None)
    engine = get_engine()

    # SQLite doesn't support named schemas; map to None (default schema)
    if _is_sqlite():
        schema_map = {"tenant": None, "shared": None}
    else:
        schema_map = {"tenant": tenant_schema}

    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map=schema_map)
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


async def get_shared_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession against the shared schema (no translation needed).

    Used for Organization CRUD and other cross-tenant operations.
    For SQLite, schemas are mapped to None.
    """
    engine = get_engine()

    if _is_sqlite():
        schema_map = {"tenant": None, "shared": None}
    else:
        schema_map = {"shared": "shared"}

    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map=schema_map)
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
