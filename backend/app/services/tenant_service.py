"""Tenant lifecycle service -- create, retrieve, and list tenants."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_engine
from app.db.tenant import ensure_tenant_schema_exists
from app.models.shared import Organization
from app.schemas.organization import OrganizationCreate


class TenantService:
    """Manages tenant (organization) lifecycle."""

    async def create_tenant(
        self,
        session: AsyncSession,
        org_create: OrganizationCreate,
    ) -> Organization:
        """Create an Organization in the shared schema and provision its tenant schema.

        1. Insert Organization record in shared schema
        2. Create tenant_{slug} schema with all TenantBase tables
        """
        org = Organization(
            name=org_create.name,
            slug=org_create.slug,
        )
        session.add(org)
        await session.flush()  # Get the ID before committing

        # Provision the tenant schema
        engine = get_engine()
        await ensure_tenant_schema_exists(engine, org_create.slug)

        return org

    async def get_tenant_by_slug(
        self,
        session: AsyncSession,
        slug: str,
    ) -> Organization | None:
        """Look up an organization by its slug."""
        result = await session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_tenants(
        self,
        session: AsyncSession,
    ) -> list[Organization]:
        """List all organizations."""
        result = await session.execute(
            select(Organization).order_by(Organization.name)
        )
        return list(result.scalars().all())
