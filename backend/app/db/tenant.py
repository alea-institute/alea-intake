"""Tenant resolution and schema management.

Handles mapping org slugs to PostgreSQL schemas and creating
tenant schemas with all required tables on first use.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import SharedBase, TenantBase


async def resolve_tenant_schema(org_slug: str) -> str:
    """Return the PostgreSQL schema name for a given org slug."""
    return f"tenant_{org_slug}"


async def ensure_tenant_schema_exists(engine: AsyncEngine, org_slug: str) -> None:
    """Create the tenant schema and all TenantBase tables if they don't exist.

    For PostgreSQL: Creates a new schema tenant_{org_slug} and runs
    CREATE TABLE for all TenantBase models within it.

    For SQLite: No-op for schema creation (SQLite has no schemas),
    but tables are still created.
    """
    schema_name = await resolve_tenant_schema(org_slug)
    dialect = engine.dialect.name

    async with engine.begin() as conn:
        if dialect == "postgresql":
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        await conn.run_sync(
            TenantBase.metadata.create_all,
            tables=TenantBase.metadata.sorted_tables,
        )


async def ensure_shared_schema_exists(engine: AsyncEngine) -> None:
    """Create the shared schema and all SharedBase tables if they don't exist.

    For PostgreSQL: Creates the 'shared' schema.
    For SQLite: Just creates the tables (no schema concept).
    """
    dialect = engine.dialect.name

    async with engine.begin() as conn:
        if dialect == "postgresql":
            await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "shared"'))

        await conn.run_sync(
            SharedBase.metadata.create_all,
            tables=SharedBase.metadata.sorted_tables,
        )
