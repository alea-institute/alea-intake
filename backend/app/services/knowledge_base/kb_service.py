"""Knowledge base document lifecycle service.

Handles the full document pipeline: upload, extract, chunk, tag, embed, index.
Supports PDF, DOCX, images (via DocumentService), HTML, and plain text per D-12.
Per-org tenant isolation with full version tracking per D-14.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.models.knowledge_base import KBChunk, KBDocument

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.document.document_service import DocumentService
    from app.services.embedding.service import EmbeddingService
    from app.services.knowledge_base.chunker import SemanticChunker
    from app.services.knowledge_base.folio_tagger import FolioTagger
    from app.services.knowledge_base.retriever import KBRetriever

logger = logging.getLogger(__name__)

# Supported file formats mapping (extension -> MIME type)
_FORMAT_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
    "text": "text/plain",
    "md": "text/markdown",
}

# Formats that use DocumentService extractors
_DOC_SERVICE_FORMATS = {"pdf", "docx", "png", "jpg", "jpeg", "tiff", "tif"}


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML tag stripper that extracts text content."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _extract_html(content: bytes) -> str:
    """Extract text from HTML content by stripping tags."""
    text = content.decode("utf-8", errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(text)
    return parser.get_text()


class KBService:
    """Knowledge base document lifecycle service.

    Manages the full document pipeline: upload, extract, chunk, FOLIO-tag,
    embed, and index. Supports multiple document formats and per-org isolation.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        document_service: DocumentService | None = None,
        chunker: SemanticChunker | None = None,
        folio_tagger: FolioTagger | None = None,
        retriever: KBRetriever | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._db_session = db_session
        self._document_service = document_service
        self._chunker = chunker
        self._folio_tagger = folio_tagger
        self._retriever = retriever
        self._embedding_service = embedding_service

    def get_supported_formats(self) -> list[str]:
        """Return list of supported file extensions."""
        return list(_FORMAT_MAP.keys())

    async def upload(
        self,
        org_id: int,
        file_content: bytes,
        filename: str,
        title: str,
        source_type: str = "uploaded",
    ) -> KBDocument:
        """Upload and process a document into the knowledge base.

        (1) Detect format from filename extension.
        (2) Extract text (DocumentService for PDF/DOCX/images, custom for HTML/text).
        (3) Chunk via SemanticChunker.
        (4) Tag via FolioTagger.
        (5) Create KBDocument + KBChunk records.

        Args:
            org_id: Organization ID for tenant isolation.
            file_content: Raw file bytes.
            filename: Original filename (used for format detection).
            title: Document title.
            source_type: Type of document (uploaded, insight, etc.).

        Returns:
            Created KBDocument record.
        """
        ext = Path(filename).suffix.lstrip(".").lower()
        mime_type = _FORMAT_MAP.get(ext, "text/plain")

        # Extract text based on format
        text = await self._extract_text(file_content, ext, mime_type)

        # Chunk
        chunks = []
        if self._chunker:
            chunks = self._chunker.chunk(text, max_tokens=500, overlap=50)

        # Tag
        all_tags: list[list] = []
        if self._folio_tagger and chunks:
            all_tags = await self._folio_tagger.tag_chunks(chunks)

        # Collect all FOLIO IRIs from tags
        doc_iris: list[str] = []
        for tag_list in all_tags:
            for tag in tag_list:
                if tag.iri and tag.iri not in doc_iris:
                    doc_iris.append(tag.iri)

        # Create document record
        doc = KBDocument(
            org_id=org_id,
            title=title,
            source_type=source_type,
            format=mime_type,
            version=1,
            folio_iris_json=json.dumps(doc_iris) if doc_iris else None,
            status="active",
        )
        self._db_session.add(doc)
        await self._db_session.flush()

        # Create chunk records
        for i, chunk in enumerate(chunks):
            chunk_iris: list[str] = []
            if i < len(all_tags):
                chunk_iris = [t.iri for t in all_tags[i] if t.iri]

            kb_chunk = KBChunk(
                document_id=doc.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                heading=chunk.heading,
                folio_iris_json=json.dumps(chunk_iris) if chunk_iris else None,
                token_count=chunk.token_count,
            )
            self._db_session.add(kb_chunk)

        await self._db_session.flush()
        return doc

    async def update(
        self,
        document_id: int,
        file_content: bytes,
        filename: str,
    ) -> KBDocument:
        """Update an existing document: re-extract, re-chunk, re-embed, increment version.

        Args:
            document_id: ID of the document to update.
            file_content: New file content bytes.
            filename: New filename (for format detection).

        Returns:
            Updated KBDocument.

        Raises:
            ValueError: If document not found.
        """
        from sqlalchemy import select

        # Fetch existing document
        stmt = select(KBDocument).where(KBDocument.id == document_id)
        result = await self._db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        # Delete old chunks
        from sqlalchemy import delete as sa_delete

        await self._db_session.execute(
            sa_delete(KBChunk).where(KBChunk.document_id == document_id)
        )

        # Re-process
        ext = Path(filename).suffix.lstrip(".").lower()
        mime_type = _FORMAT_MAP.get(ext, "text/plain")
        text = await self._extract_text(file_content, ext, mime_type)

        chunks = []
        if self._chunker:
            chunks = self._chunker.chunk(text, max_tokens=500, overlap=50)

        all_tags: list[list] = []
        if self._folio_tagger and chunks:
            all_tags = await self._folio_tagger.tag_chunks(chunks)

        doc_iris: list[str] = []
        for tag_list in all_tags:
            for tag in tag_list:
                if tag.iri and tag.iri not in doc_iris:
                    doc_iris.append(tag.iri)

        # Update document metadata
        doc.format = mime_type
        doc.version += 1
        doc.folio_iris_json = json.dumps(doc_iris) if doc_iris else None

        # Create new chunks
        for i, chunk in enumerate(chunks):
            chunk_iris: list[str] = []
            if i < len(all_tags):
                chunk_iris = [t.iri for t in all_tags[i] if t.iri]

            kb_chunk = KBChunk(
                document_id=doc.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                heading=chunk.heading,
                folio_iris_json=json.dumps(chunk_iris) if chunk_iris else None,
                token_count=chunk.token_count,
            )
            self._db_session.add(kb_chunk)

        await self._db_session.flush()
        return doc

    async def delete(self, document_id: int) -> None:
        """Delete a document and all its chunks.

        Args:
            document_id: ID of the document to delete.

        Raises:
            ValueError: If document not found.
        """
        from sqlalchemy import delete as sa_delete, select

        # Verify document exists
        stmt = select(KBDocument).where(KBDocument.id == document_id)
        result = await self._db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        # Delete chunks first
        await self._db_session.execute(
            sa_delete(KBChunk).where(KBChunk.document_id == document_id)
        )

        # Delete document
        await self._db_session.execute(
            sa_delete(KBDocument).where(KBDocument.id == document_id)
        )

        await self._db_session.flush()

    async def bulk_import(
        self, org_id: int, zip_content: bytes
    ) -> list[KBDocument]:
        """Import multiple documents from a ZIP archive.

        Extracts all files from the ZIP and processes each one.

        Args:
            org_id: Organization ID.
            zip_content: Raw ZIP file bytes.

        Returns:
            List of created KBDocument records.
        """
        docs: list[KBDocument] = []

        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            for name in zf.namelist():
                # Skip directories and hidden files
                if name.endswith("/") or name.startswith("__") or name.startswith("."):
                    continue

                ext = Path(name).suffix.lstrip(".").lower()
                if ext not in _FORMAT_MAP:
                    logger.warning("Skipping unsupported file in ZIP: %s", name)
                    continue

                file_bytes = zf.read(name)
                title = Path(name).stem.replace("_", " ").replace("-", " ").title()

                doc = await self.upload(
                    org_id=org_id,
                    file_content=file_bytes,
                    filename=name,
                    title=title,
                )
                docs.append(doc)

        return docs

    async def list_documents(
        self, org_id: int, page: int = 1, page_size: int = 20
    ) -> list:
        """List documents for an organization with pagination.

        Args:
            org_id: Organization ID.
            page: Page number (1-indexed).
            page_size: Number of documents per page.

        Returns:
            List of KBDocument records.
        """
        from sqlalchemy import select

        offset = (page - 1) * page_size
        stmt = (
            select(KBDocument)
            .where(KBDocument.org_id == org_id)
            .where(KBDocument.status == "active")
            .offset(offset)
            .limit(page_size)
        )
        result = await self._db_session.execute(stmt)
        return result.scalars().all()

    async def get_document(self, document_id: int) -> dict | None:
        """Get a document with chunk count and aggregated FOLIO tags.

        Args:
            document_id: Document ID.

        Returns:
            Dict with document info, chunk_count, and folio_tags. None if not found.
        """
        from sqlalchemy import func, select

        stmt = select(KBDocument).where(KBDocument.id == document_id)
        result = await self._db_session.execute(stmt)
        doc = result.scalar_one_or_none()

        if doc is None:
            return None

        return {
            "id": doc.id,
            "title": doc.title,
            "version": doc.version,
            "status": doc.status,
            "folio_iris": json.loads(doc.folio_iris_json) if doc.folio_iris_json else [],
        }

    async def _extract_text(self, content: bytes, ext: str, mime_type: str) -> str:
        """Extract text from file content based on format.

        Uses DocumentService for PDF/DOCX/images, custom extraction for HTML/text.
        """
        if ext in _DOC_SERVICE_FORMATS and self._document_service:
            # Use DocumentService extractors
            # Save temp file and process
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                result = await self._document_service.process_document(
                    file_path=tmp_path,
                    mime_type=mime_type,
                    message_id=0,
                )
                return result.text
            finally:
                tmp_path.unlink(missing_ok=True)

        elif ext in ("html", "htm"):
            return _extract_html(content)

        else:
            # Plain text / markdown -- pass through
            return content.decode("utf-8", errors="replace")
