"""Output document model -- stores rendered output per profile.

Each OutputDocument captures a single rendered output (one per profile) with
Markdown as the canonical format and optional rendered bytes for PDF/DOCX.
"""

from datetime import datetime

from sqlalchemy import Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class OutputDocument(TenantBase):
    """A rendered output document for a specific profile and analysis run."""

    __tablename__ = "output_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_type: Mapped[str] = mapped_column(String(30), nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_pdf: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    rendered_docx: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    rendered_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
