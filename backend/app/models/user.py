"""User model with role enum -- lives in per-tenant schema.

The full_name field is stored as LargeBinary because it contains PII
that will be encrypted at the application layer (field-level encryption).
"""

from datetime import datetime
from enum import Enum

from typing import Optional

from sqlalchemy import Boolean, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class Role(str, Enum):
    """User roles with predefined permission sets."""

    ADMIN = "admin"
    PROFESSIONAL = "professional"
    CONSUMER = "consumer"


class User(TenantBase):
    """User account within a tenant schema."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "org_id", name="uq_users_email_org_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="consumer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sso_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sso_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
