"""Research tool registry -- singleton manager for research adapters.

Manages adapter registration, per-org tool discovery, and query dispatch
across all configured adapters. Merges results from multiple tools and
deduplicates by citation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Singleton instance
_registry: ResearchToolRegistry | None = None


class ResearchToolRegistry:
    """Singleton registry for research tool adapters.

    Manages adapter lifecycle and dispatches queries to configured tools.
    Adapters are registered by name and can be looked up individually or
    queried in batch across all enabled adapters.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, ResearchAdapter] = {}

    @classmethod
    def get_instance(cls) -> ResearchToolRegistry:
        """Get or create the singleton registry instance."""
        global _registry
        if _registry is None:
            _registry = cls()
        return _registry

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        global _registry
        _registry = None

    def register(self, adapter: ResearchAdapter) -> None:
        """Register an adapter by its adapter_name.

        Args:
            adapter: The research adapter instance to register.

        Raises:
            ValueError: If an adapter with the same name is already registered.
        """
        name = adapter.adapter_name
        if name in self._adapters:
            logger.warning("Replacing existing adapter: %s", name)
        self._adapters[name] = adapter
        logger.info("Registered research adapter: %s", name)

    def unregister(self, name: str) -> None:
        """Remove an adapter from the registry.

        Args:
            name: The adapter_name to remove.
        """
        self._adapters.pop(name, None)

    def get_adapter(self, name: str) -> ResearchAdapter | None:
        """Look up an adapter by name.

        Args:
            name: The adapter_name to look up.

        Returns:
            The adapter instance, or None if not found.
        """
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        """List all registered adapter names."""
        return list(self._adapters.keys())

    async def query_tool(self, tool_name: str, query: ResearchQuery) -> list[ResearchResult]:
        """Query a specific research tool.

        Args:
            tool_name: Name of the adapter to query.
            query: The research query.

        Returns:
            List of results from the specified tool.

        Raises:
            ValueError: If the tool is not registered.
        """
        adapter = self._adapters.get(tool_name)
        if adapter is None:
            raise ValueError(f"Research tool not registered: {tool_name}")

        try:
            results = await adapter.discover(query)
            # Tag results with source tool name
            for r in results:
                r.source_tool = tool_name
            return results
        except Exception as e:
            logger.error("Research query failed for %s: %s", tool_name, e)
            return []

    async def query_all(
        self,
        query: ResearchQuery,
        tool_names: list[str] | None = None,
    ) -> list[ResearchResult]:
        """Query multiple research tools and merge results.

        Dispatches the query to all specified tools (or all registered tools),
        collects results, deduplicates by citation, and sorts by relevance.

        Args:
            query: The research query.
            tool_names: Specific tools to query. If None, queries all registered.

        Returns:
            Merged and deduplicated list of results sorted by relevance.
        """
        names = tool_names or self.list_adapters()
        all_results: list[ResearchResult] = []

        for name in names:
            if name not in self._adapters:
                logger.warning("Skipping unregistered tool: %s", name)
                continue
            results = await self.query_tool(name, query)
            all_results.extend(results)

        # Deduplicate by citation (keep highest relevance score)
        deduped = _deduplicate_results(all_results)

        # Sort by relevance score descending
        deduped.sort(key=lambda r: r.relevance_score or 0.0, reverse=True)

        return deduped[:query.max_results]

    async def verify_citation(self, citation: str, tool_names: list[str] | None = None) -> dict:
        """Verify a citation against configured tools.

        Tries each tool until one verifies the citation.

        Args:
            citation: Citation string to verify.
            tool_names: Specific tools to check. If None, checks all registered.

        Returns:
            Dict with verified status, source tool, and details.
        """
        names = tool_names or self.list_adapters()

        for name in names:
            adapter = self._adapters.get(name)
            if adapter is None:
                continue
            try:
                is_verified = await adapter.verify_citation(citation)
                if is_verified:
                    # Fetch full details for the verified citation
                    authority = await adapter.fetch_authority(citation)
                    return {
                        "verified": True,
                        "status": "verified",
                        "verification_source": name,
                        "citation": citation,
                        "matched_title": authority.title if authority else None,
                        "source_url": authority.source_url if authority else None,
                    }
            except Exception as e:
                logger.warning("Verification failed for %s via %s: %s", citation, name, e)
                continue

        return {
            "verified": False,
            "status": "not_found",
            "verification_source": None,
            "citation": citation,
        }


def _deduplicate_results(results: list[ResearchResult]) -> list[ResearchResult]:
    """Deduplicate results by citation, keeping the highest relevance score."""
    seen: dict[str, ResearchResult] = {}
    for r in results:
        key = r.citation.strip().lower()
        if key not in seen:
            seen[key] = r
        else:
            existing = seen[key]
            if (r.relevance_score or 0.0) > (existing.relevance_score or 0.0):
                seen[key] = r
    return list(seen.values())


def get_research_registry() -> ResearchToolRegistry:
    """Factory function for dependency injection."""
    return ResearchToolRegistry.get_instance()
