"""Shared-schema models (tenant registry, cross-tenant data).

These models live in the 'shared' PostgreSQL schema and are accessible
across all tenants. The primary model is Organization, which serves as
the tenant registry.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SharedBase


class Organization(SharedBase):
    """Tenant registry -- each organization gets its own tenant schema."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    auth_mode: Mapped[str] = mapped_column(String(20), default="email_password")
    llm_data_policy: Mapped[str] = mapped_column(String(20), default="cloud_optout")
    consent_mode: Mapped[str] = mapped_column(String(20), default="granular")
    deletion_policy: Mapped[str] = mapped_column(String(20), default="anonymize")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
