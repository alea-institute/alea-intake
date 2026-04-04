"""Research adapter abstract base class and shared data types.

Defines the pluggable contract for legal research tool adapters.
Each adapter implements discover() to search for authorities and
fetch_authority() to retrieve details for a specific citation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResearchQuery:
    """Query parameters for a research tool search.

    Attributes:
        query_text: The search text (claim description, legal issue, etc.).
        claim_iri: Optional FOLIO claim IRI to scope the search.
        jurisdiction: Optional jurisdiction filter (e.g., "California", "federal").
        authority_types: Optional filter for authority types (case_law, statute, etc.).
        max_results: Maximum number of results to return.
        metadata: Additional tool-specific query parameters.
    """

    query_text: str
    claim_iri: str | None = None
    jurisdiction: str | None = None
    authority_types: list[str] | None = None
    max_results: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """A single result from a research tool query.

    Attributes:
        citation: Standard citation string (e.g., "347 U.S. 483").
        title: Full title of the authority.
        authority_type: Type of authority (case_law, statute, regulation, etc.).
        jurisdiction: Jurisdiction of the authority.
        source_tool: Name of the research tool that found this.
        source_url: URL to the full text or detail page.
        excerpt: Relevant text excerpt or snippet.
        relevance_score: How relevant this result is to the query (0.0-1.0).
        folio_iri: Optional FOLIO concept IRI if mapped.
        metadata: Additional tool-specific result data.
    """

    citation: str
    title: str
    authority_type: str
    jurisdiction: str | None = None
    source_tool: str = ""
    source_url: str | None = None
    excerpt: str | None = None
    relevance_score: float | None = None
    folio_iri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchAdapter(abc.ABC):
    """Abstract base class for pluggable legal research tool adapters.

    Each concrete adapter wraps a specific research tool (CourtListener,
    Westlaw, Clio Library, etc.) and implements a uniform interface for
    querying and verifying legal authorities.

    Adapters are registered with the ResearchToolRegistry and invoked
    based on per-org tool configuration.
    """

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Unique identifier for this adapter (e.g., 'courtlistener', 'westlaw')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for this adapter."""
        return self.adapter_name.replace("_", " ").title()

    @abc.abstractmethod
    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search for legal authorities matching the query.

        Args:
            query: The research query with search text, jurisdiction, filters.

        Returns:
            List of ResearchResult objects sorted by relevance.

        Raises:
            ConnectionError: If the research tool API is unreachable.
            ValueError: If the query is malformed.
        """
        ...

    @abc.abstractmethod
    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch details for a specific citation.

        Args:
            citation: Standard citation string to look up.

        Returns:
            ResearchResult with full details, or None if not found.
        """
        ...

    @abc.abstractmethod
    async def verify_citation(self, citation: str) -> bool:
        """Verify whether a citation exists in this tool's database.

        Used for ground-truth verification of LLM-suggested citations.

        Args:
            citation: Citation string to verify.

        Returns:
            True if the citation was found and verified, False otherwise.
        """
        ...

    async def check_connection(self) -> dict[str, str]:
        """Test the connection to the research tool API.

        Returns:
            Status dict: {"status": "connected"} or {"status": "error", "detail": ...}
        """
        return {"status": "connected", "adapter": self.adapter_name}

    def configure(self, api_key: str | None = None, base_url: str | None = None, **kwargs) -> None:
        """Configure the adapter with API credentials and settings.

        Args:
            api_key: API key for the research tool.
            base_url: Base URL override for the API.
            **kwargs: Additional tool-specific configuration.
        """
        if api_key is not None:
            self._api_key = api_key
        if base_url is not None:
            self._base_url = base_url

    def _get_api_key(self) -> str | None:
        """Get the configured API key."""
        return getattr(self, "_api_key", None)

    def _get_base_url(self) -> str | None:
        """Get the configured base URL."""
        return getattr(self, "_base_url", None)
