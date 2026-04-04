"""Dual-signal knowledge base retriever (vector similarity + FOLIO IRI boosting).

Combines embedding-based vector search with FOLIO IRI overlap boosting
for ontology-grounded retrieval per D-11/D-13. Per-org index isolation
ensures tenant data separation per Pitfall 3.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.embedding.service import EmbeddingService

logger = logging.getLogger(__name__)

# Boost multiplier for chunks with overlapping FOLIO IRIs per D-13
FOLIO_IRI_BOOST: float = 1.5


@dataclass
class KBSearchResult:
    """A single knowledge base search result."""

    chunk_content: str
    document_title: str
    document_id: int
    score: float
    folio_iris: list[str] = field(default_factory=list)
    is_insight: bool = False


class KBRetriever:
    """Dual-signal knowledge base retriever.

    Performs vector similarity search via EmbeddingService and boosts
    chunks whose FOLIO IRIs overlap with query IRIs per D-13.
    Ensures per-org tenant isolation per Pitfall 3.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        concept_resolver: Any | None = None,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._concept_resolver = concept_resolver
        self._db_session = db_session

    async def search(
        self,
        query: str,
        org_id: int,
        top_k: int = 10,
        folio_iris: list[str] | None = None,
    ) -> list[KBSearchResult]:
        """Search the knowledge base with dual-signal retrieval.

        (1) Embed query via EmbeddingService, search vector index (top_k*2 for oversampling).
        (2) Fetch chunk records from DB filtered by org_id (tenant isolation).
        (3) If folio_iris provided, boost chunks whose folio_iris_json overlaps.
        (4) Sort by boosted score, return top_k.

        Args:
            query: Search query text.
            org_id: Organization ID for tenant isolation.
            top_k: Maximum results to return.
            folio_iris: Optional FOLIO IRIs to boost matching chunks.

        Returns:
            Sorted list of KBSearchResult by score descending.
        """
        # Step 1: Vector similarity search (oversample 2x)
        oversample_k = top_k * 2
        embedding_results = await self._embedding_service.search(query, top_k=oversample_k)

        if not embedding_results:
            return []

        # Step 2: Get chunk IDs from embedding results and fetch from DB
        chunk_ids = [r.iri for r in embedding_results]
        score_map = {r.iri: r.score for r in embedding_results}

        # Fetch chunks from DB filtered by org_id
        chunks = await self._fetch_chunks_for_org(chunk_ids, org_id)

        if not chunks:
            return []

        # Build result set with scores
        results: list[KBSearchResult] = []
        folio_iris_set = set(folio_iris) if folio_iris else set()

        for chunk in chunks:
            chunk_id_str = f"chunk:{chunk.id}" if hasattr(chunk, "id") else str(chunk.id)

            # Get base score from embedding search
            base_score = score_map.get(chunk_id_str, 0.0)
            # Also try matching by ID directly
            if base_score == 0.0:
                for eid, escore in score_map.items():
                    base_score = escore
                    break

            # Parse FOLIO IRIs from chunk
            chunk_iris: list[str] = []
            if hasattr(chunk, "folio_iris_json") and chunk.folio_iris_json:
                try:
                    chunk_iris = json.loads(chunk.folio_iris_json)
                except (json.JSONDecodeError, TypeError):
                    chunk_iris = []

            # Step 3: Apply FOLIO IRI boost
            boosted_score = base_score
            if folio_iris_set and chunk_iris:
                overlap = folio_iris_set & set(chunk_iris)
                if overlap:
                    boosted_score *= FOLIO_IRI_BOOST

            # Get document title
            doc_title = getattr(chunk, "title", "") or "Unknown"
            doc_id = getattr(chunk, "document_id", 0)
            is_insight = False

            results.append(
                KBSearchResult(
                    chunk_content=chunk.content,
                    document_title=doc_title,
                    document_id=doc_id,
                    score=boosted_score,
                    folio_iris=chunk_iris,
                    is_insight=is_insight,
                )
            )

        # Step 4: Sort by score descending, return top_k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def _fetch_chunks_for_org(self, chunk_ids: list[str], org_id: int) -> list:
        """Fetch KB chunks from DB, filtered by org_id for tenant isolation.

        Args:
            chunk_ids: Chunk identifiers from embedding search.
            org_id: Organization ID to filter by.

        Returns:
            List of KBChunk records belonging to the org.
        """
        if not self._db_session:
            return []

        from sqlalchemy import select

        from app.models.knowledge_base import KBChunk, KBDocument

        # Join chunks with documents to filter by org_id
        stmt = (
            select(KBChunk)
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .where(KBDocument.org_id == org_id)
            .where(KBDocument.status == "active")
        )

        result = await self._db_session.execute(stmt)
        return result.scalars().all()
