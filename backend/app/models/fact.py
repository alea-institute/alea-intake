"""Fact extraction models: ExtractedFact, FactSourceSpan.

Stores atomic factual assertions extracted from intake messages,
with source provenance tracking for narrative-anchored views.
"""

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class ExtractedFact(TenantBase):
    """An atomic factual assertion extracted from a message."""

    __tablename__ = "extracted_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    party_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assertion_text: Mapped[str] = mapped_column(Text, nullable=False)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="internal")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FactSourceSpan(TenantBase):
    """Source location within a message for an extracted fact."""

    __tablename__ = "fact_source_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp_end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
