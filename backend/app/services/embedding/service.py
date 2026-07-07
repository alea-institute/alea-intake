"""Singleton embedding service with dual-backend abstraction.

Provides encode, search, and build_index operations backed by either
pgvector (PostgreSQL) or FAISS (SQLite). Automatically selects backend
based on database_backend configuration.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from app.services.embedding.backends import EmbeddingBackend, SearchResult

if TYPE_CHECKING:
    from folio import FOLIO

    from app.services.embedding.providers import EmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton embedding service with dual-backend abstraction."""

    _instance: EmbeddingService | None = None
    _lock = threading.Lock()

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self._provider = provider
        self._backend = backend
        self._built = False

    @classmethod
    def get_instance(
        cls,
        provider: EmbeddingProvider | None = None,
        backend: EmbeddingBackend | None = None,
    ) -> EmbeddingService:
        """Return the singleton instance, creating it on first call.

        Uses double-checked locking for thread safety.
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            cls._instance = cls(provider=provider, backend=backend)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    def _ensure_provider(self) -> None:
        if self._provider is None:
            from app.services.embedding.providers.local import LocalEmbeddingProvider

            self._provider = LocalEmbeddingProvider()

    def _ensure_backend(self) -> None:
        if self._backend is None:
            from app.config import DatabaseBackend, get_settings
            from app.services.embedding.backends.faiss_backend import FAISSBackend

            settings = get_settings()
            if settings.database_backend == DatabaseBackend.POSTGRESQL:
                from app.db.engine import get_engine
                from app.services.embedding.backends.pgvector_backend import PgVectorBackend

                self._ensure_provider()
                self._backend = PgVectorBackend(
                    get_engine(), dimension=self._provider.dimension  # type: ignore[union-attr]
                )
            else:
                self._backend = FAISSBackend()

    def build_index(self, folio: FOLIO) -> None:
        """Build embedding index from all FOLIO classes.

        Synchronous -- call via run_in_executor from async contexts.
        Encodes all class labels in batches and upserts to the backend.
        """
        self._ensure_provider()
        self._ensure_backend()

        loop = asyncio.new_event_loop()
        try:
            # BUG-9: the pgvector table (and shared schema) must exist before
            # delete_all() TRUNCATEs it — on a fresh database this previously
            # raised UndefinedTableError, which the lifespan swallowed, leaving
            # every embedding search broken.
            ensure_table = getattr(self._backend, "ensure_table", None)
            if ensure_table is not None:
                loop.run_until_complete(ensure_table())
            loop.run_until_complete(self._backend.delete_all())  # type: ignore[union-attr]

            # Batch encode all labels. folio-python's FOLIO.classes is a
            # List[OWLClass] (BUG-10); dict-shaped test doubles still work.
            raw_classes = folio.classes
            if hasattr(raw_classes, "values"):
                raw_classes = raw_classes.values()
            classes = [
                c for c in raw_classes if c is not None and getattr(c, "label", None)
            ]
            labels = [cls.label for cls in classes]
            batch_size = 256

            logger.info("Building embedding index for %d FOLIO classes...", len(classes))

            upsert_many = getattr(self._backend, "upsert_many", None)
            for i in range(0, len(labels), batch_size):
                batch_labels = labels[i : i + batch_size]
                batch_classes = classes[i : i + batch_size]
                vectors = self._provider.encode_batch(batch_labels)  # type: ignore[union-attr]
                batch_rows = [
                    {
                        "iri": cls.iri,
                        "vector": vec,
                        "metadata": {
                            "label": cls.label,
                            "branch": getattr(cls, "branch", ""),
                            "alt_labels": cls.alternative_labels,
                        },
                    }
                    for cls, vec in zip(batch_classes, vectors)
                ]
                if upsert_many is not None:
                    # One transaction per batch instead of per vector.
                    loop.run_until_complete(upsert_many(batch_rows))
                else:
                    for row in batch_rows:
                        loop.run_until_complete(
                            self._backend.upsert(  # type: ignore[union-attr]
                                iri=row["iri"],
                                vector=row["vector"],
                                metadata=row["metadata"],
                            )
                        )

            self._built = True
            logger.info("Embedding index built: %d vectors", len(classes))
        finally:
            loop.close()

    async def search(self, text: str, top_k: int = 20) -> list[SearchResult]:
        """Search for similar FOLIO concepts by text embedding."""
        self._ensure_provider()
        self._ensure_backend()

        loop = asyncio.get_event_loop()
        vector = await loop.run_in_executor(
            None, self._provider.encode, text  # type: ignore[union-attr]
        )
        return await self._backend.search(vector, top_k=top_k)  # type: ignore[union-attr]

    async def rebuild_index(self, folio: FOLIO) -> None:
        """Rebuild index after OWL update. Called by OWLUpdateManager."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.build_index, folio)
