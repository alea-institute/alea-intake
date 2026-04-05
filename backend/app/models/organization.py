"""Organization config model -- per-org settings that live in tenant schema.

Separates org-specific configuration (LLM keys, kiosk settings) from the
shared Organization registry. This model lives in each tenant's own schema.
"""

from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class OrganizationConfig(TenantBase):
    """Per-org configuration stored in tenant schema."""

    __tablename__ = "organization_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    llm_api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_data_policy: Mapped[str] = mapped_column(String(20), default="cloud_optout")
    kiosk_audit_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    kiosk_consent_required: Mapped[bool] = mapped_column(Boolean, default=True)
    kiosk_session_ttl_hours: Mapped[int] = mapped_column(Integer, default=24)
    analysis_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
