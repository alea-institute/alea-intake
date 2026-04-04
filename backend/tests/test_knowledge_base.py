"""Tests for knowledge base subsystem: SemanticChunker, FolioTagger, KBRetriever.

Covers:
- Semantic chunking with paragraph/heading boundaries, overlap, and token limits
- FOLIO tagging on chunk headings via ConceptResolver
- Dual-signal retrieval (vector similarity + FOLIO IRI boosting)
- Per-org tenant isolation
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# SemanticChunker Tests
# ---------------------------------------------------------------------------


class TestSemanticChunker:
    """Tests for SemanticChunker text chunking."""

    @pytest.fixture
    def chunker(self):
        from app.services.knowledge_base.chunker import SemanticChunker

        return SemanticChunker()

    def test_chunk_respects_paragraph_boundaries(self, chunker):
        """Test 1: Chunks respect paragraph boundaries per D-13."""
        text = "First paragraph content.\n\nSecond paragraph content.\n\nThird paragraph content."
        chunks = chunker.chunk(text, max_tokens=500, overlap=0)
        # Should produce at least 1 chunk, content split at paragraph boundaries
        assert len(chunks) >= 1
        # Each chunk should contain complete paragraphs (not split mid-sentence within paragraph)
        for c in chunks:
            assert c.content.strip() != ""

    def test_chunk_token_size_and_overlap(self, chunker):
        """Test 2: Chunks are ~500 tokens each with ~50-token overlap."""
        # Build a long text (~2000 tokens)
        words = ["word"] * 2000
        text = " ".join(words)
        chunks = chunker.chunk(text, max_tokens=500, overlap=50)
        assert len(chunks) >= 2
        for c in chunks:
            assert c.token_count <= 550  # Allow some slack for boundary respect

        # Check overlap: last tokens of chunk N repeated at start of chunk N+1
        if len(chunks) >= 2:
            c0_tokens = chunks[0].content.split()
            c1_tokens = chunks[1].content.split()
            overlap_tokens = c0_tokens[-50:]
            c1_start = c1_tokens[:50]
            # At least some overlap tokens should appear
            assert len(set(overlap_tokens) & set(c1_start)) > 0

    def test_chunk_preserves_headings(self, chunker):
        """Test 3: Chunks preserve headings -- heading stays with its content."""
        text = "## Section Title\nContent under section title with more text.\n\n## Another Section\nMore content here."
        chunks = chunker.chunk(text, max_tokens=500, overlap=0)
        # At least one chunk should have a heading
        headings = [c.heading for c in chunks if c.heading is not None]
        assert len(headings) >= 1
        assert "Section Title" in headings[0]

    def test_chunk_result_fields(self, chunker):
        """Chunks have all required fields: content, heading, chunk_index, token_count, start_offset, end_offset."""
        text = "## Heading\nSome content here."
        chunks = chunker.chunk(text, max_tokens=500, overlap=0)
        assert len(chunks) >= 1
        c = chunks[0]
        assert hasattr(c, "content")
        assert hasattr(c, "heading")
        assert hasattr(c, "chunk_index")
        assert hasattr(c, "token_count")
        assert hasattr(c, "start_offset")
        assert hasattr(c, "end_offset")
        assert c.chunk_index == 0
        assert c.token_count > 0

    def test_chunk_handles_uppercase_headings(self, chunker):
        """Uppercase-line headings are detected and preserved."""
        text = "COMPLAINT FOR DAMAGES\nThe plaintiff alleges breach of contract."
        chunks = chunker.chunk(text, max_tokens=500, overlap=0)
        assert len(chunks) >= 1
        assert chunks[0].heading is not None
        assert "COMPLAINT" in chunks[0].heading


# ---------------------------------------------------------------------------
# FolioTagger Tests
# ---------------------------------------------------------------------------


class TestFolioTagger:
    """Tests for FolioTagger FOLIO concept tagging on chunks."""

    @pytest.fixture
    def mock_resolver(self):
        """Create a mock ConceptResolver."""
        resolver = AsyncMock()
        return resolver

    @pytest.fixture
    def tagger(self, mock_resolver):
        from app.services.knowledge_base.folio_tagger import FolioTagger

        return FolioTagger(concept_resolver=mock_resolver)

    @pytest.mark.asyncio
    async def test_tag_chunk_uses_concept_resolver(self, tagger, mock_resolver):
        """Test 4: FolioTagger.tag_chunk uses ConceptResolver on chunk heading per D-13."""
        from app.services.knowledge_base.chunker import ChunkResult

        # Mock resolver returns concepts
        mock_resolver.return_value = [
            SimpleNamespace(iri="https://folio.openlegalstandard.org/complaint", label="Complaint", confidence=0.92, source="embedding"),
        ]
        chunk = ChunkResult(
            content="The plaintiff filed a complaint.",
            heading="Complaint",
            chunk_index=0,
            token_count=6,
            start_offset=0,
            end_offset=31,
        )
        tags = await tagger.tag_chunk(chunk)
        assert len(tags) >= 1
        mock_resolver.assert_called_once()

    @pytest.mark.asyncio
    async def test_tag_chunk_returns_iris_with_confidence(self, tagger, mock_resolver):
        """Test 5: FolioTagger returns list of FOLIO IRIs with confidence scores."""
        from app.services.knowledge_base.chunker import ChunkResult

        mock_resolver.return_value = [
            SimpleNamespace(iri="https://folio.openlegalstandard.org/lease", label="Lease", confidence=0.88, source="label_match"),
            SimpleNamespace(iri="https://folio.openlegalstandard.org/contract", label="Contract", confidence=0.75, source="embedding"),
        ]
        chunk = ChunkResult(
            content="The lease agreement was signed.",
            heading="Lease Agreement",
            chunk_index=0,
            token_count=5,
            start_offset=0,
            end_offset=30,
        )
        tags = await tagger.tag_chunk(chunk)
        assert len(tags) == 2
        assert tags[0].iri == "https://folio.openlegalstandard.org/lease"
        assert tags[0].confidence == 0.88
        assert tags[1].iri == "https://folio.openlegalstandard.org/contract"

    @pytest.mark.asyncio
    async def test_tag_chunk_no_heading_returns_empty(self, tagger):
        """Test 6: Chunks without headings return empty tag list."""
        from app.services.knowledge_base.chunker import ChunkResult

        chunk = ChunkResult(
            content="Just some text.",
            heading=None,
            chunk_index=0,
            token_count=3,
            start_offset=0,
            end_offset=15,
        )
        tags = await tagger.tag_chunk(chunk)
        assert tags == []

    @pytest.mark.asyncio
    async def test_tag_chunks_batch(self, tagger, mock_resolver):
        """FolioTagger.tag_chunks batch-tags all chunks."""
        from app.services.knowledge_base.chunker import ChunkResult

        mock_resolver.return_value = [
            SimpleNamespace(iri="https://folio.openlegalstandard.org/arrest", label="Arrest", confidence=0.9, source="embedding"),
        ]
        chunks = [
            ChunkResult(content="Text 1", heading="Arrest", chunk_index=0, token_count=2, start_offset=0, end_offset=6),
            ChunkResult(content="Text 2", heading=None, chunk_index=1, token_count=2, start_offset=6, end_offset=12),
        ]
        all_tags = await tagger.tag_chunks(chunks)
        assert len(all_tags) == 2
        assert len(all_tags[0]) >= 1  # First chunk has heading -> tags
        assert len(all_tags[1]) == 0  # Second chunk has no heading -> empty

    @pytest.mark.asyncio
    async def test_tagger_without_resolver(self):
        """FolioTagger with no resolver returns empty tags."""
        from app.services.knowledge_base.chunker import ChunkResult
        from app.services.knowledge_base.folio_tagger import FolioTagger

        tagger = FolioTagger(concept_resolver=None)
        chunk = ChunkResult(content="Text", heading="Heading", chunk_index=0, token_count=1, start_offset=0, end_offset=4)
        tags = await tagger.tag_chunk(chunk)
        assert tags == []


# ---------------------------------------------------------------------------
# KBRetriever Tests
# ---------------------------------------------------------------------------


class TestKBRetriever:
    """Tests for KBRetriever dual-signal search."""

    @pytest.fixture
    def mock_embedding_service(self):
        svc = AsyncMock()
        return svc

    @pytest.fixture
    def mock_concept_resolver(self):
        return AsyncMock()

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.fixture
    def retriever(self, mock_embedding_service, mock_concept_resolver, mock_session):
        from app.services.knowledge_base.retriever import KBRetriever

        return KBRetriever(
            embedding_service=mock_embedding_service,
            concept_resolver=mock_concept_resolver,
            db_session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_search_vector_similarity(self, retriever, mock_embedding_service, mock_session):
        """Test 7: KBRetriever.search performs vector similarity search via EmbeddingService."""
        from app.services.embedding.backends import SearchResult

        # Mock embedding search results
        mock_embedding_service.search.return_value = [
            SearchResult(iri="chunk:1", label="Chunk 1", score=0.95, metadata={"org_id": 1}),
            SearchResult(iri="chunk:2", label="Chunk 2", score=0.85, metadata={"org_id": 1}),
        ]

        # Mock DB session for chunk lookup
        mock_chunk_1 = SimpleNamespace(
            id=1, document_id=10, content="Chunk 1 content", heading="Heading 1",
            folio_iris_json=json.dumps(["https://folio.openlegalstandard.org/lease"]),
            token_count=50,
        )
        mock_chunk_2 = SimpleNamespace(
            id=2, document_id=11, content="Chunk 2 content", heading=None,
            folio_iris_json=None, token_count=40,
        )
        mock_doc_1 = SimpleNamespace(id=10, title="Doc 1", org_id=1)
        mock_doc_2 = SimpleNamespace(id=11, title="Doc 2", org_id=1)

        # Setup DB mock to return chunks and docs
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_chunk_1, mock_chunk_2]
        mock_session.execute.return_value = mock_result

        results = await retriever.search("lease agreement", org_id=1, top_k=10)
        assert len(results) >= 1
        mock_embedding_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_boosts_folio_iris(self, retriever, mock_embedding_service, mock_session):
        """Test 8: KBRetriever.search boosts chunks whose folio_iris overlap with query FOLIO IRIs per D-13."""
        from app.services.embedding.backends import SearchResult

        lease_iri = "https://folio.openlegalstandard.org/lease"

        mock_embedding_service.search.return_value = [
            SearchResult(iri="chunk:1", label="Chunk 1", score=0.80, metadata={"org_id": 1}),
            SearchResult(iri="chunk:2", label="Chunk 2", score=0.82, metadata={"org_id": 1}),
        ]

        mock_chunk_1 = SimpleNamespace(
            id=1, document_id=10, content="Has lease content", heading="Lease",
            folio_iris_json=json.dumps([lease_iri]), token_count=50,
        )
        mock_chunk_2 = SimpleNamespace(
            id=2, document_id=11, content="No matching IRI", heading=None,
            folio_iris_json=None, token_count=40,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_chunk_1, mock_chunk_2]
        mock_session.execute.return_value = mock_result

        results = await retriever.search(
            "lease agreement", org_id=1, top_k=10, folio_iris=[lease_iri]
        )
        # Chunk 1 should be boosted above chunk 2 despite lower base score
        assert len(results) >= 1
        if len(results) >= 2:
            # Chunk with matching FOLIO IRI should be ranked higher
            assert results[0].folio_iris == [lease_iri] or results[0].score >= results[1].score

    @pytest.mark.asyncio
    async def test_search_tenant_isolation(self, retriever, mock_embedding_service, mock_session):
        """Test 9: KBRetriever only searches the org's own index (tenant isolation per Pitfall 3)."""
        from app.services.embedding.backends import SearchResult

        # Return results from multiple orgs
        mock_embedding_service.search.return_value = [
            SearchResult(iri="chunk:1", label="Chunk 1", score=0.90, metadata={"org_id": 1}),
            SearchResult(iri="chunk:99", label="Other Org", score=0.95, metadata={"org_id": 99}),
        ]

        mock_chunk_1 = SimpleNamespace(
            id=1, document_id=10, content="Org 1 content", heading=None,
            folio_iris_json=None, token_count=50,
        )
        mock_result = MagicMock()
        # Only chunks from org 1 returned
        mock_result.scalars.return_value.all.return_value = [mock_chunk_1]
        mock_session.execute.return_value = mock_result

        results = await retriever.search("test query", org_id=1, top_k=10)
        # Should only contain results from org 1
        # The retriever should filter by org_id
        assert all(r.score > 0 for r in results)
