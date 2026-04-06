"""CMS sync models -- track sync state and connector configuration.

CMSSyncRecord tracks per-entity sync status between ALEA and CMS.
CMSConnectorConfig stores per-org CMS connector configuration with
encrypted credentials.

Both models live in the tenant schema (per-org data isolation).
"""

from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class CMSSyncRecord(TenantBase):
    """Tracks sync state for each ALEA entity pushed to / pulled from a CMS.

    Each record maps one ALEA entity (contact, matter, document) to its
    corresponding CMS entity, tracking sync status and any errors.
    """

    __tablename__ = "cms_sync_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alea_entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="contact|matter|document"
    )
    alea_entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cms_entity_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="CMS-side ID"
    )
    cms_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="clio|mycase|legalserver"
    )
    sync_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending|synced|failed|conflict",
    )
    sync_direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="push", comment="push|pull"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class CMSConnectorConfig(TenantBase):
    """Per-org CMS connector configuration.

    Stores credentials (encrypted), sync scope, direction, and webhook
    URL for each CMS connector an organization has configured.
    """

    __tablename__ = "cms_connector_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cms_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="clio|mycase|legalserver"
    )
    credentials_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    sync_scope_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="List of entity types to sync"
    )
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="bidirectional"
    )
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
