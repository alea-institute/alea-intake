"""DEPRECATED: Replaced by research_stage.py in Phase 6. Kept for reference.

Research stub stage -- FOLIO-based element discovery placeholder.
Uses FOLIO adjacency traversal to discover related concepts and potential
elements for each claim. Phase 6 replaces this with ResearchStage which
integrates full legal research tool queries (CourtListener, Westlaw, etc.).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisClaim, AnalysisRun

logger = logging.getLogger(__name__)


class ResearchStubStage:
    """FOLIO-based research placeholder.

    For each claim with a folio_iri, uses FOLIO adjacency to discover
    related concepts and potential elements. Returns a summary of
    discovered elements for the pipeline to use.

    Phase 6 will replace this with full legal research tool integration.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        folio: FOLIO | None = None,
    ) -> None:
        self._session = db_session
        self._folio = folio

    async def execute(
        self,
        run: AnalysisRun,
        claims: list[AnalysisClaim],
    ) -> dict:
        """Execute research stub stage.

        Args:
            run: The current AnalysisRun.
            claims: List of AnalysisClaim records to research.

        Returns:
            Dict with elements_discovered count and research_notes.
        """
        if self._folio is None:
            return {
                "elements_discovered": 0,
                "research_notes": "FOLIO unavailable, research deferred to Phase 6",
            }

        total_elements = 0
        notes_parts: list[str] = []

        for claim in claims:
            if not claim.folio_iri:
                notes_parts.append(
                    f"Claim '{claim.claim_name}': no FOLIO IRI, skipping adjacency"
                )
                continue

            try:
                from app.services.folio.adjacency import discover_adjacent_concepts

                graph = discover_adjacent_concepts(self._folio, claim.folio_iri)
                adjacent_count = len(graph.get("nodes", [])) - 1  # Exclude source node
                edge_count = len(graph.get("edges", []))

                if adjacent_count > 0:
                    total_elements += adjacent_count
                    node_labels = [
                        n["label"]
                        for n in graph.get("nodes", [])
                        if n.get("iri") != claim.folio_iri
                    ]
                    notes_parts.append(
                        f"Claim '{claim.claim_name}': {adjacent_count} adjacent concepts found "
                        f"({edge_count} edges). Related: {', '.join(node_labels[:5])}"
                    )
                else:
                    notes_parts.append(
                        f"Claim '{claim.claim_name}': no adjacent concepts in FOLIO"
                    )
            except Exception:
                logger.debug(
                    "FOLIO adjacency failed for claim '%s' (IRI: %s)",
                    claim.claim_name,
                    claim.folio_iri,
                    exc_info=True,
                )
                notes_parts.append(
                    f"Claim '{claim.claim_name}': adjacency traversal failed"
                )

        research_notes = "; ".join(notes_parts) if notes_parts else "No claims with FOLIO IRIs to research"

        return {
            "elements_discovered": total_elements,
            "research_notes": research_notes,
        }
