"""MCPAdapter -- wraps FolioMCPClient into ResearchToolAdapter interface.

Per D-10, maps FolioMCPClient tool calls (search_concepts, get_concept,
get_taxonomy_branch) into the unified ResearchResult schema. Results from
folio-mcp are secondary sources (ontology concepts, not case law).
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)


class MCPAdapter(ResearchAdapter):
    """MCP-based research adapter wrapping FolioMCPClient.

    Queries the FOLIO ontology via folio-mcp for concept searches
    and maps results to ResearchResult with authority_type="secondary".

    Args:
        mcp_client: FolioMCPClient instance (injected for testability).
    """

    def __init__(self, mcp_client: Any = None) -> None:
        self._mcp_client = mcp_client

    @property
    def adapter_name(self) -> str:
        return "folio-mcp"

    @property
    def display_name(self) -> str:
        return "FOLIO MCP"

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search FOLIO concepts via FolioMCPClient.search_concepts().

        Maps each concept result to a ResearchResult with
        source_tool="folio-mcp" and authority_type="secondary".
        """
        if self._mcp_client is None:
            logger.warning("MCPAdapter: no MCP client configured")
            return []

        try:
            concepts = await self._mcp_client.search_concepts(
                query.query_text, limit=query.max_results
            )

            results: list[ResearchResult] = []
            for concept in concepts:
                result = self._parse_concept(concept)
                if result:
                    results.append(result)

            return results

        except Exception as e:
            logger.error("MCP search failed: %s", e)
            return []

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch a FOLIO concept by IRI."""
        if self._mcp_client is None:
            return None

        try:
            concept = await self._mcp_client.get_concept(citation)
            return self._parse_concept(concept) if concept else None
        except Exception as e:
            logger.error("MCP fetch failed for '%s': %s", citation, e)
            return None

    async def verify_citation(self, citation: str) -> dict[str, Any]:
        """Verify a FOLIO concept IRI exists via get_concept().

        Returns {verified: bool, source: str, metadata: dict}.
        """
        if self._mcp_client is None:
            return {"verified": False, "source": "folio-mcp", "metadata": {}}

        try:
            concept = await self._mcp_client.get_concept(citation)
            if concept:
                label = concept.get("label", "") if isinstance(concept, dict) else ""
                return {
                    "verified": True,
                    "source": "folio-mcp",
                    "metadata": {"label": label, "iri": citation},
                }
        except Exception as e:
            logger.warning("MCP verify failed for '%s': %s", citation, e)

        return {"verified": False, "source": "folio-mcp", "metadata": {}}

    async def health_check(self) -> bool:
        """Check if MCP client is connected."""
        return self._mcp_client is not None

    def _parse_concept(self, concept: Any) -> ResearchResult | None:
        """Parse a FOLIO concept into a ResearchResult."""
        if concept is None:
            return None

        if isinstance(concept, dict):
            iri = concept.get("iri", "")
            label = concept.get("label", "")
            definition = concept.get("definition", "")
        else:
            # Handle MCP content objects
            iri = getattr(concept, "iri", "")
            label = getattr(concept, "label", str(concept))
            definition = getattr(concept, "definition", "")

        if not label:
            return None

        return ResearchResult(
            citation=iri or label,
            title=label,
            authority_type="secondary",
            jurisdiction=None,
            source_tool="folio-mcp",
            source_url=None,
            excerpt=definition or None,
            relevance_score=None,
            metadata={"iri": iri},
        )
