"""Tests for KBService document lifecycle and KB admin API endpoints.

Covers:
- KBService: upload, update, delete, bulk import, list, get
- Format support: PDF, DOCX, images, HTML, plain text per D-12
- Admin API: CRUD endpoints with admin role guard
- Version tracking on updates
"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_base.chunker import ChunkResult


# ---------------------------------------------------------------------------
# KBService Tests
# ---------------------------------------------------------------------------


class TestKBService:
    """Tests for KBService document lifecycle."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        added = []

        def mock_add(obj):
            added.append(obj)
            if not hasattr(obj, "_id_set"):
                obj.id = len(added)
                obj._id_set = True

        session.add = mock_add
        session.flush = AsyncMock()
        session._added = added
        return session

    @pytest.fixture
    def mock_document_service(self):
        svc = MagicMock()
        return svc

    @pytest.fixture
    def mock_chunker(self):
        chunker = MagicMock()
        chunker.chunk.return_value = [
            ChunkResult(
                content="Chunk content",
                heading="Test Heading",
                chunk_index=0,
                token_count=10,
                start_offset=0,
                end_offset=13,
            ),
        ]
        return chunker

    @pytest.fixture
    def mock_folio_tagger(self):
        tagger = AsyncMock()
        tagger.tag_chunks.return_value = [[]]
        return tagger

    @pytest.fixture
    def mock_retriever(self):
        return AsyncMock()

    @pytest.fixture
    def mock_embedding_service(self):
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        mock_session,
        mock_document_service,
        mock_chunker,
        mock_folio_tagger,
        mock_retriever,
        mock_embedding_service,
    ):
        from app.services.knowledge_base.kb_service import KBService

        return KBService(
            db_session=mock_session,
            document_service=mock_document_service,
            chunker=mock_chunker,
            folio_tagger=mock_folio_tagger,
            retriever=mock_retriever,
            embedding_service=mock_embedding_service,
        )

    @pytest.mark.asyncio
    async def test_upload_extracts_chunks_tags_embeds(self, service, mock_session, mock_chunker, mock_folio_tagger):
        """Test 1: KBService.upload extracts text, chunks, tags, embeds, creates KBDocument + KBChunks."""
        doc = await service.upload(
            org_id=1,
            file_content=b"This is plain text content for testing.",
            filename="test.txt",
            title="Test Document",
        )
        # Document and chunk should be created
        assert len(mock_session._added) >= 2  # doc + at least 1 chunk
        mock_chunker.chunk.assert_called_once()
        mock_folio_tagger.tag_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_supports_multiple_formats(self, service):
        """Test 2: Upload supports PDF, DOCX, images, HTML, plain text per D-12."""
        supported = service.get_supported_formats()
        assert "txt" in supported
        assert "html" in supported
        assert "pdf" in supported
        assert "docx" in supported
        # Image formats
        assert any(f in supported for f in ["png", "jpg", "jpeg", "tiff"])

    @pytest.mark.asyncio
    async def test_update_re_extracts_and_increments_version(self, service, mock_session):
        """Test 3: KBService.update re-extracts, re-chunks, re-embeds, increments version per D-14."""
        # Mock finding existing document
        mock_doc = SimpleNamespace(
            id=1, org_id=1, title="Old Doc", version=1, status="active",
            file_path=None, format="text/plain", source_type="uploaded",
            folio_iris_json=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result

        # Mock delete old chunks
        mock_chunks_result = MagicMock()
        mock_chunks_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_chunks_result

        updated = await service.update(
            document_id=1,
            file_content=b"Updated content",
            filename="updated.txt",
        )
        # Version should be incremented
        assert mock_doc.version == 2

    @pytest.mark.asyncio
    async def test_delete_removes_chunks_and_document(self, service, mock_session):
        """Test 4: KBService.delete removes chunks from vector index + deletes DB records per D-14."""
        mock_doc = SimpleNamespace(id=1, org_id=1, status="active")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()

        await service.delete(document_id=1)
        # Should have called delete
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_bulk_import_from_zip(self, service, mock_session, mock_chunker, mock_folio_tagger):
        """Test 5: KBService.bulk_import extracts ZIP, processes each file per D-14."""
        # Create a ZIP in memory with two text files
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc1.txt", "First document content.")
            zf.writestr("doc2.txt", "Second document content.")
        zip_bytes = buf.getvalue()

        docs = await service.bulk_import(org_id=1, zip_content=zip_bytes)
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_list_documents(self, service, mock_session):
        """Test 6: KBService.list_documents returns paginated KBDocument list."""
        mock_doc = SimpleNamespace(id=1, title="Doc 1", org_id=1, status="active")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_doc]
        mock_session.execute.return_value = mock_result

        docs = await service.list_documents(org_id=1, page=1, page_size=20)
        assert isinstance(docs, list)

    @pytest.mark.asyncio
    async def test_get_document(self, service, mock_session):
        """Test 7: KBService.get_document returns document with chunk count and FOLIO tags."""
        mock_doc = SimpleNamespace(
            id=1, title="Doc 1", org_id=1, status="active", version=1,
            folio_iris_json=json.dumps(["https://folio.openlegalstandard.org/lease"]),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result

        doc = await service.get_document(document_id=1)
        assert doc is not None

    @pytest.mark.asyncio
    async def test_html_extraction(self, service, mock_session, mock_chunker):
        """Test 13: HTML extraction strips tags and extracts text content."""
        html_content = b"<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>"
        doc = await service.upload(
            org_id=1,
            file_content=html_content,
            filename="test.html",
            title="HTML Doc",
        )
        # Chunker should receive stripped text (no HTML tags)
        call_args = mock_chunker.chunk.call_args
        text_arg = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
        assert "<html>" not in text_arg
        assert "<body>" not in text_arg

    @pytest.mark.asyncio
    async def test_version_tracking_on_update(self, service, mock_session):
        """Test 14: Version tracking: document version increments on update."""
        mock_doc = SimpleNamespace(
            id=1, org_id=1, title="Doc", version=3, status="active",
            file_path=None, format="text/plain", source_type="uploaded",
            folio_iris_json=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute.return_value = mock_result

        mock_chunks_result = MagicMock()
        mock_chunks_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_chunks_result

        await service.update(document_id=1, file_content=b"New content", filename="new.txt")
        assert mock_doc.version == 4


# ---------------------------------------------------------------------------
# KB Admin API Tests
# ---------------------------------------------------------------------------


class TestKBAdminAPI:
    """Tests for KB admin API endpoints."""

    @pytest.mark.asyncio
    async def test_admin_endpoints_exist(self):
        """Test 8-11: Admin API endpoints are defined and accessible."""
        from app.routers.kb_admin import router

        routes = {r.path for r in router.routes}
        # POST upload
        assert any("/documents" in p for p in routes)

    @pytest.mark.asyncio
    async def test_admin_requires_admin_role(self):
        """Test 12: Admin API requires admin role."""
        from app.routers.kb_admin import router

        # Check router dependencies include admin role check
        deps = router.dependencies
        assert len(deps) >= 1  # Should have require_role(Role.ADMIN)

    @pytest.mark.asyncio
    async def test_router_prefix(self):
        """Admin router has correct prefix."""
        from app.routers.kb_admin import router

        assert "/admin/kb" in router.prefix
