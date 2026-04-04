"""Audio recording and transcript models for voice intake modality.

All models live in per-tenant schemas via TenantBase. Sensitive fields
use LargeBinary for application-layer encryption.
"""

from datetime import datetime

from sqlalchemy import Float, Integer, JSON, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class AudioRecording(TenantBase):
    """An audio recording attached to a message in an intake session."""

    __tablename__ = "audio_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    original_format: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_policy: Mapped[str] = mapped_column(String(20), default="store_both", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Transcript(TenantBase):
    """ASR transcript of an audio recording, subject to consumer review."""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, nullable=False)
    text_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_review", nullable=False)
    asr_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    segments_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
