"""Intake data models: Intake, IntakeParty, IntakeSession, Message.

Core models for the intake system. All extend TenantBase for per-tenant
schema isolation.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class Intake(TenantBase):
    """An intake case -- the top-level entity for a consumer's legal situation."""

    __tablename__ = "intakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_mode: Mapped[str] = mapped_column(String(20), default="multi_session")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class IntakeParty(TenantBase):
    """A party participating in an intake (consumer, co-petitioner, etc.)."""

    __tablename__ = "intake_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_in_intake: Mapped[str] = mapped_column(String(50), default="primary")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class IntakeSession(TenantBase):
    """A session within an intake -- supports pause/resume for multi-session mode."""

    __tablename__ = "intake_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Message(TenantBase):
    """A single message in an intake session (text, voice, document, or system)."""

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
