"""InsightsService for secondary/practical legal knowledge.

Stores and retrieves advocacy knowledge (best practices, tips, pitfalls)
indexed by FOLIO IRI. Insights are KB documents with source_type="insight"
and always rank below primary research authorities per D-08.

This is modeled internally -- folio-insights does NOT exist as an external repo.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from app.services.knowledge_base.retriever import KBSearchResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.knowledge_base.retriever import KBRetriever

logger = logging.getLogger(__name__)

# Demotion factor for insights vs primary authorities per D-08
INSIGHT_DEMOTION_FACTOR: float = 0.5


class InsightsService:
    """Service for managing secondary/practical legal knowledge.

    Insights are KB documents with source_type="insight" containing
    advocacy tips, best practices, and pitfalls mapped to FOLIO IRIs.
    They always rank below primary research authorities per D-08.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        kb_retriever: KBRetriever | None = None,
    ) -> None:
        self._db_session = db_session
        self._kb_retriever = kb_retriever

    async def get_insights(
        self, folio_iri: str, top_k: int = 5
    ) -> list[KBSearchResult]:
        """Retrieve insights matching a FOLIO IRI.

        Queries KB for documents with source_type="insight" whose
        folio_iris_json contains the given IRI.

        Args:
            folio_iri: FOLIO concept IRI to search for.
            top_k: Maximum results to return.

        Returns:
            List of KBSearchResult with is_insight=True.
        """
        from sqlalchemy import select

        from app.models.knowledge_base import KBChunk, KBDocument

        # Query chunks from insight documents matching the FOLIO IRI
        stmt = (
            select(KBChunk)
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .where(KBDocument.source_type == "insight")
            .where(KBDocument.status == "active")
            .where(KBChunk.folio_iris_json.contains(folio_iri))
            .limit(top_k)
        )

        result = await self._db_session.execute(stmt)
        chunks = result.scalars().all()

        return [
            KBSearchResult(
                chunk_content=chunk.content,
                document_title=getattr(chunk, "title", "Insight"),
                document_id=chunk.document_id,
                score=0.5,  # Base score for insights
                folio_iris=self._parse_iris(chunk.folio_iris_json),
                is_insight=True,
            )
            for chunk in chunks
        ]

    async def add_insight(
        self,
        folio_iri: str,
        content: str,
        source: str = "llm",
    ) -> int:
        """Create a new insight document with chunks.

        Creates a KBDocument with source_type="insight" and a single
        KBChunk containing the insight content.

        Args:
            folio_iri: FOLIO concept IRI this insight relates to.
            content: The insight content text.
            source: Source of the insight (e.g., "llm", "manual").

        Returns:
            The created document ID.
        """
        from app.models.knowledge_base import KBChunk, KBDocument

        # Create document
        doc = KBDocument(
            org_id=0,  # System-level insight
            title=f"Insight: {folio_iri.split('/')[-1]}",
            source_type="insight",
            format="text/plain",
            folio_iris_json=json.dumps([folio_iri]),
            status="active",
        )
        self._db_session.add(doc)
        await self._db_session.flush()

        # Create chunk
        chunk = KBChunk(
            document_id=doc.id,
            chunk_index=0,
            content=content,
            heading=None,
            folio_iris_json=json.dumps([folio_iri]),
            token_count=len(content.split()),
        )
        self._db_session.add(chunk)
        await self._db_session.flush()

        return doc.id

    def rank_results(self, results: list[KBSearchResult]) -> list[KBSearchResult]:
        """Rank results with insights below primary authorities per D-08.

        Primary results (is_insight=False) always rank above insights
        (is_insight=True), regardless of their base scores.

        Args:
            results: Mixed list of primary and insight results.

        Returns:
            Sorted list with primary results first, then insights.
        """
        primary = [r for r in results if not r.is_insight]
        insights = [r for r in results if r.is_insight]

        # Sort each group by score descending
        primary.sort(key=lambda r: r.score, reverse=True)
        insights.sort(key=lambda r: r.score, reverse=True)

        # Demote insight scores
        for insight in insights:
            insight.score *= INSIGHT_DEMOTION_FACTOR

        return primary + insights

    @staticmethod
    def _parse_iris(iris_json: str | None) -> list[str]:
        """Parse FOLIO IRIs from JSON string."""
        if not iris_json:
            return []
        try:
            return json.loads(iris_json)
        except (json.JSONDecodeError, TypeError):
            return []
