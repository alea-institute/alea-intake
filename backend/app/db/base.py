"""SQLAlchemy declarative bases for tenant and shared schemas.

Two separate bases ensure models are created in the correct schema:
- TenantBase: Models in per-tenant schemas (tenant_{org_slug})
- SharedBase: Models in the shared schema (tenant registry, cross-tenant data)
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention for constraints (consistent across all migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

tenant_metadata = MetaData(schema="tenant", naming_convention=convention)
shared_metadata = MetaData(schema="shared", naming_convention=convention)


class TenantBase(DeclarativeBase):
    """Base class for models that live in per-tenant schemas."""

    metadata = tenant_metadata


class SharedBase(DeclarativeBase):
    """Base class for models that live in the shared schema."""

    metadata = shared_metadata
