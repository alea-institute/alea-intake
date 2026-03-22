"""Consent models -- records of consent granted/revoked and configurable templates.

Lives in per-tenant schema. ConsentRecord tracks individual consent grants,
ConsentTemplate defines what consent options an org presents to consumers.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class ConsentRecord(TenantBase):
    """Record of consent granted or revoked by a user or kiosk session."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    consent_items: Mapped[dict] = mapped_column(JSON, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


class ConsentTemplate(TenantBase):
    """Org-configurable consent template defining available consent options."""

    __tablename__ = "consent_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    items: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
