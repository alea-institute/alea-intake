"""FOLIO concept tagger for knowledge base chunks.

Uses ConceptResolver to tag chunk headings with FOLIO IRIs,
creating strong retrieval signals for dual-signal search per D-13.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from app.services.knowledge_base.chunker import ChunkResult


@dataclass
class TagResult:
    """A FOLIO concept tag assigned to a chunk."""

    iri: str
    label: str
    confidence: float


class FolioTagger:
    """Tags knowledge base chunks with FOLIO concept IRIs.

    Uses ConceptResolver (or any async callable returning concept matches)
    to resolve chunk headings to FOLIO IRIs per D-13.
    """

    def __init__(self, concept_resolver: Any | None = None) -> None:
        """Initialize with optional ConceptResolver.

        Args:
            concept_resolver: Async callable that resolves text to FOLIO concepts.
                Expected signature: async (text) -> list[ConceptMatch]
                where ConceptMatch has .iri, .label, .confidence attributes.
                If None, all tagging returns empty lists.
        """
        self._resolver = concept_resolver

    async def tag_chunk(self, chunk: ChunkResult) -> list[TagResult]:
        """Tag a single chunk by resolving its heading to FOLIO IRIs.

        Args:
            chunk: A ChunkResult with optional heading.

        Returns:
            List of TagResult with IRI, label, and confidence.
            Empty list if chunk has no heading or no resolver configured.
        """
        if self._resolver is None:
            return []

        if chunk.heading is None:
            return []

        # Call resolver on heading text
        concepts = await self._resolver(chunk.heading)

        return [
            TagResult(
                iri=getattr(c, "iri", ""),
                label=getattr(c, "label", ""),
                confidence=getattr(c, "confidence", 0.0),
            )
            for c in concepts
        ]

    async def tag_chunks(self, chunks: list[ChunkResult]) -> list[list[TagResult]]:
        """Batch-tag all chunks.

        Args:
            chunks: List of ChunkResult to tag.

        Returns:
            List of tag lists, one per chunk.
        """
        return [await self.tag_chunk(chunk) for chunk in chunks]
