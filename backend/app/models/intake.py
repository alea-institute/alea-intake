"""Intake data models -- core intake session, party, and message tracking.

All models live in per-tenant schemas via TenantBase. Sensitive fields
use LargeBinary for application-layer encryption (EncryptionContext integration).
"""

from datetime import datetime

from sqlalchemy import Integer, JSON, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class Intake(TenantBase):
    """Top-level intake record -- one per consumer engagement."""

    __tablename__ = "intakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_mode: Mapped[str] = mapped_column(String(20), default="multi_session", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class IntakeParty(TenantBase):
    """A participant in an intake (consumer, professional, family member, etc.)."""

    __tablename__ = "intake_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_in_intake: Mapped[str] = mapped_column(String(50), default="primary", nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class IntakeSession(TenantBase):
    """A single conversation session within an intake (supports pause/resume)."""

    __tablename__ = "intake_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Optional binding to a practice-area config (see services.intake.practice_areas).
    # Nullable preserves backwards compatibility with the generic intake path.
    practice_area_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )


class Message(TenantBase):
    """A single message in an intake session (text, voice transcript, document, note)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    party_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    content_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    normalized_text: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
