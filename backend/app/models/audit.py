"""Audit log model -- append-only, immutable by application code.

Lives in per-tenant schema. INSERT-only permissions enforced at DB level
for production deployments.
"""

from datetime import datetime

from sqlalchemy import JSON, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class AuditLog(TenantBase):
    """Immutable audit trail for all tenant actions."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_timestamp_action", "timestamp", "action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
