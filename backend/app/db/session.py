"""Async session factories with per-tenant schema routing.

get_tenant_session: Creates sessions with schema_translate_map for tenant isolation.
get_shared_session: Creates sessions against the shared schema for cross-tenant ops.
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import get_engine


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the current engine."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_tenant_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession routed to the tenant's schema via schema_translate_map.

    Reads the tenant schema from request.state.tenant_schema, set by TenantMiddleware.
    Maps the logical 'tenant' schema name to the actual tenant_{org_slug} schema.
    """
    tenant_schema = getattr(request.state, "tenant_schema", None)
    session_factory = _make_session_factory()

    async with session_factory(
        execution_options={"schema_translate_map": {"tenant": tenant_schema}}
    ) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_shared_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession against the shared schema (no translation needed).

    Used for Organization CRUD and other cross-tenant operations.
    """
    session_factory = _make_session_factory()

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
