"""Audio recording and transcript models for voice intake.

All models extend TenantBase for per-tenant schema isolation.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class AudioRecording(TenantBase):
    """An audio recording attached to an intake message."""

    __tablename__ = "audio_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    original_format: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_policy: Mapped[str] = mapped_column(String(20), default="store_both")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Transcript(TenantBase):
    """A transcript of an audio recording, produced by ASR."""

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, nullable=False)
    text_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    asr_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    segments_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
