"""Document models: UploadedDocument, DocumentExtraction.

Stores encrypted uploaded documents and their text extractions.
"""

from datetime import datetime

from sqlalchemy import Integer, JSON, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class UploadedDocument(TenantBase):
    """An uploaded document attached to an intake."""

    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DocumentExtraction(TenantBase):
    """Extracted text and structure from an uploaded document."""

    __tablename__ = "document_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_text_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    elements_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
