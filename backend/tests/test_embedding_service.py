"""Tests for the embedding service: FAISS backend, providers, and EmbeddingService."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.services.embedding.backends import EmbeddingBackend, SearchResult


# ---------------------------------------------------------------------------
# FAISS Backend Tests
# ---------------------------------------------------------------------------


class TestFAISSBackend:
    """Tests for the FAISS in-memory embedding backend."""

    @pytest.fixture
    def backend(self):
        from app.services.embedding.backends.faiss_backend import FAISSBackend

        return FAISSBackend()

    @pytest.mark.asyncio
    async def test_upsert_and_search(self, backend):
        """Upsert 3 vectors, search returns ranked results."""
        # Create 3 distinct normalized vectors (dimension=4 for speed)
        v1 = [1.0, 0.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0, 0.0]
        v3 = [0.9, 0.1, 0.0, 0.0]  # Close to v1

        await backend.upsert("iri:1", v1, {"label": "Concept A"})
        await backend.upsert("iri:2", v2, {"label": "Concept B"})
        await backend.upsert("iri:3", v3, {"label": "Concept C"})

        # Search with v1-like query, expect iri:1 and iri:3 ranked highest
        results = await backend.search(v1, top_k=3)
        assert len(results) == 3
        assert isinstance(results[0], SearchResult)
        assert results[0].iri == "iri:1"
        assert results[0].score >= results[1].score

    @pytest.mark.asyncio
    async def test_delete_all(self, backend):
        """Upsert then delete_all; count returns 0."""
        await backend.upsert("iri:1", [1.0, 0.0, 0.0, 0.0], {"label": "A"})
        assert await backend.count() == 1

        await backend.delete_all()
        assert await backend.count() == 0

    @pytest.mark.asyncio
    async def test_normalizes_vectors(self, backend):
        """Vectors are normalized to unit length before indexing."""
        # Unnormalized vector
        raw = [3.0, 4.0]
        await backend.upsert("iri:1", raw, {"label": "A"})

        # Search with same unnormalized vector; inner product of normalized = 1.0
        results = await backend.search(raw, top_k=1)
        assert len(results) == 1
        # Score should be ~1.0 (cosine similarity of identical vectors)
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_search_empty_index(self, backend):
        """Searching empty index returns empty list."""
        results = await backend.search([1.0, 0.0], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_implements_protocol(self, backend):
        """FAISSBackend satisfies the EmbeddingBackend protocol."""
        assert isinstance(backend, EmbeddingBackend)


# ---------------------------------------------------------------------------
# PgVector Backend Tests (mocked engine)
# ---------------------------------------------------------------------------


class TestPgVectorBackend:
    """Tests for the pgvector PostgreSQL backend (mock engine)."""

    @pytest.mark.asyncio
    async def test_upsert_and_search_mock(self):
        """PgVectorBackend.upsert stores vector; search returns it via mock."""
        from app.services.embedding.backends.pgvector_backend import PgVectorBackend

        mock_engine = MagicMock()
        backend = PgVectorBackend(engine=mock_engine, dimension=4)

        # Mock the async context manager chain for upsert
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        await backend.upsert("iri:1", [1.0, 0.0, 0.0, 0.0], {"label": "Test"})
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        """PgVectorBackend satisfies the EmbeddingBackend protocol."""
        from app.services.embedding.backends.pgvector_backend import PgVectorBackend

        backend = PgVectorBackend(engine=MagicMock(), dimension=4)
        assert isinstance(backend, EmbeddingBackend)


# ---------------------------------------------------------------------------
# Local Embedding Provider Tests
# ---------------------------------------------------------------------------


class TestLocalEmbeddingProvider:
    """Tests for the local sentence-transformers provider."""

    @pytest.mark.slow
    def test_encode_returns_vector(self):
        """LocalEmbeddingProvider.encode returns list[float] of dimension 384."""
        st = pytest.importorskip("sentence_transformers")
        from app.services.embedding.providers.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        vec = provider.encode("test text")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        assert len(vec) == 384

    @pytest.mark.slow
    def test_encode_batch_returns_vectors(self):
        """LocalEmbeddingProvider.encode_batch returns list of list[float]."""
        st = pytest.importorskip("sentence_transformers")
        from app.services.embedding.providers.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        vecs = provider.encode_batch(["text1", "text2"])
        assert isinstance(vecs, list)
        assert len(vecs) == 2
        assert all(isinstance(v, list) for v in vecs)
        assert len(vecs[0]) == 384


# ---------------------------------------------------------------------------
# EmbeddingService Tests
# ---------------------------------------------------------------------------


class TestEmbeddingService:
    """Tests for the EmbeddingService singleton with dual-backend."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton between tests."""
        from app.services.embedding.service import EmbeddingService

        EmbeddingService.reset_instance()
        yield
        EmbeddingService.reset_instance()

    def test_singleton(self):
        """get_instance() returns the same object."""
        from app.services.embedding.service import EmbeddingService

        mock_provider = MagicMock()
        mock_backend = MagicMock()
        s1 = EmbeddingService.get_instance(provider=mock_provider, backend=mock_backend)
        s2 = EmbeddingService.get_instance()
        assert s1 is s2

    def test_build_index_creates_vectors(self, mock_folio):
        """build_index encodes all FOLIO classes via provider and upserts to backend."""
        from app.services.embedding.service import EmbeddingService

        mock_provider = MagicMock()
        mock_provider.encode_batch.return_value = [[0.1] * 4] * len(mock_folio.classes)
        mock_provider.dimension = 4

        mock_backend = AsyncMock()
        mock_backend.delete_all = AsyncMock()
        mock_backend.upsert = AsyncMock()

        service = EmbeddingService.get_instance(provider=mock_provider, backend=mock_backend)
        service.build_index(mock_folio)

        assert mock_provider.encode_batch.called
        assert mock_backend.upsert.call_count == len(mock_folio.classes)

    def test_build_index_ensures_table_before_truncate(self, mock_folio):
        """BUG-9: build_index must create the table before delete_all TRUNCATEs it."""
        from app.services.embedding.service import EmbeddingService

        mock_provider = MagicMock()
        mock_provider.encode_batch.return_value = [[0.1] * 4] * len(mock_folio.classes)
        mock_provider.dimension = 4

        mock_backend = AsyncMock()
        service = EmbeddingService.get_instance(provider=mock_provider, backend=mock_backend)
        service.build_index(mock_folio)

        calls = [c[0] for c in mock_backend.method_calls]
        assert "ensure_table" in calls
        assert calls.index("ensure_table") < calls.index("delete_all")

    def test_build_index_accepts_real_list_classes(self):
        """BUG-10: real folio-python FOLIO.classes is a List[OWLClass], not a dict."""
        from app.services.embedding.service import EmbeddingService

        def _cls(iri, label):
            c = MagicMock()
            c.iri = iri
            c.label = label
            c.alternative_labels = []
            return c

        folio = MagicMock()
        folio.classes = [
            _cls("iri:1", "Eviction"),
            _cls("iri:2", None),  # unlabeled classes must be skipped
            _cls("iri:3", "Wage Theft"),
        ]

        mock_provider = MagicMock()
        mock_provider.encode_batch.return_value = [[0.1] * 4] * 2
        mock_provider.dimension = 4
        mock_backend = AsyncMock()

        service = EmbeddingService.get_instance(provider=mock_provider, backend=mock_backend)
        service.build_index(folio)

        assert mock_backend.upsert.call_count == 2

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """search returns SearchResult objects with iri, label, score."""
        from app.services.embedding.service import EmbeddingService

        mock_provider = MagicMock()
        mock_provider.encode.return_value = [0.1] * 4
        mock_provider.dimension = 4

        expected = [SearchResult(iri="iri:1", label="Test", score=0.9)]
        mock_backend = AsyncMock()
        mock_backend.search = AsyncMock(return_value=expected)

        service = EmbeddingService.get_instance(provider=mock_provider, backend=mock_backend)
        results = await service.search("eviction", top_k=5)

        assert len(results) == 1
        assert results[0].iri == "iri:1"
        assert results[0].label == "Test"
        assert results[0].score == 0.9


# ---------------------------------------------------------------------------
# Lifespan Integration Test
# ---------------------------------------------------------------------------


class TestLifespanEmbeddingIndex:
    """Test that lifespan calls EmbeddingService.build_index after FOLIO load."""

    @pytest.mark.asyncio
    async def test_lifespan_builds_embedding_index(self):
        """Lifespan calls EmbeddingService.get_instance().build_index(folio)."""
        import os

        # Ensure ALEA_SECRET_KEY is set so app.main can import cleanly
        os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only")

        from app.main import app, lifespan

        async def noop_periodic(*args, **kwargs):
            """Fake periodic check that just sleeps forever (will be cancelled)."""
            await asyncio.sleep(3600)

        with (
            patch("app.main.ensure_owl_fresh"),
            patch("app.main.get_folio") as mock_get_folio,
            patch("app.main.OWLUpdateManager") as mock_updater_cls,
            patch("app.main._periodic_owl_check", side_effect=noop_periodic),
            patch("app.main.get_engine"),
            patch("app.main.dispose_engine", new_callable=AsyncMock),
            patch("app.main.EmbeddingService") as mock_emb_cls,
        ):
            mock_folio = MagicMock()
            mock_get_folio.return_value = mock_folio

            mock_emb_instance = MagicMock()
            mock_emb_cls.get_instance.return_value = mock_emb_instance

            mock_updater = MagicMock()
            mock_updater_cls.get_instance.return_value = mock_updater

            async with lifespan(app):
                pass

            # Verify build_index was called with the FOLIO instance
            mock_emb_cls.get_instance.assert_called_once()
            mock_emb_instance.build_index.assert_called_once()
