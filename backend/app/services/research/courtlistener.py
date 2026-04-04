"""CourtListener REST API adapter for legal research.

Implements the ResearchAdapter interface against the CourtListener v4 REST API.
CourtListener provides free access to US case law, statutes, and oral arguments.

API docs: https://www.courtlistener.com/api/rest-info/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)

# Default base URL for CourtListener REST API v4
DEFAULT_BASE_URL = "https://www.courtlistener.com/api/rest/v4"

# Map CourtListener cluster types to our authority types
_CLUSTER_TYPE_MAP = {
    "010combined": "case_law",
    "020lead": "case_law",
    "025appendix": "case_law",
    "030concurrence": "case_law",
    "040dissent": "case_law",
    "050addendum": "case_law",
}


class CourtListenerAdapter(ResearchAdapter):
    """CourtListener REST API research adapter.

    Queries the CourtListener search API for opinions (case law) matching
    a research query, with optional jurisdiction filtering. Supports
    citation verification by looking up specific citations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url or DEFAULT_BASE_URL
        self._timeout = timeout

    @property
    def adapter_name(self) -> str:
        return "courtlistener"

    @property
    def display_name(self) -> str:
        return "CourtListener"

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with optional API token."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "alea-intake/0.1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Token {self._api_key}"
        return headers

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search CourtListener for opinions matching the query.

        Uses the /search/ endpoint with type=o (opinions) for case law.

        Args:
            query: Research query with search text and optional filters.

        Returns:
            List of ResearchResult objects from CourtListener.
        """
        params: dict[str, Any] = {
            "q": query.query_text,
            "type": "o",  # opinions
            "order_by": "score desc",
        }

        if query.jurisdiction:
            # CourtListener uses court codes for jurisdiction filtering
            params["court"] = query.jurisdiction

        # Limit results
        max_results = min(query.max_results, 50)  # CL API cap

        results: list[ResearchResult] = []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/search/",
                    params=params,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()

                # Parse results from the search response
                for item in data.get("results", [])[:max_results]:
                    result = self._parse_search_result(item)
                    if result:
                        results.append(result)

        except httpx.TimeoutException:
            logger.warning("CourtListener search timed out for query: %s", query.query_text[:100])
        except httpx.HTTPStatusError as e:
            logger.error("CourtListener API error: %s", e.response.status_code)
        except Exception as e:
            logger.error("CourtListener search failed: %s", e)

        return results

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch a specific authority by citation string.

        Uses the /search/ endpoint with the citation as the query text,
        filtering for exact citation matches.

        Args:
            citation: Standard citation string (e.g., "347 U.S. 483").

        Returns:
            ResearchResult with full details, or None if not found.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/search/",
                    params={
                        "q": f'citation:("{citation}")',
                        "type": "o",
                    },
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if results:
                    return self._parse_search_result(results[0])

        except httpx.TimeoutException:
            logger.warning("CourtListener fetch timed out for citation: %s", citation)
        except httpx.HTTPStatusError as e:
            logger.error("CourtListener fetch error: %s", e.response.status_code)
        except Exception as e:
            logger.error("CourtListener fetch failed: %s", e)

        return None

    async def verify_citation(self, citation: str) -> bool:
        """Verify whether a citation exists in CourtListener.

        Args:
            citation: Citation string to verify.

        Returns:
            True if the citation was found in CourtListener.
        """
        result = await self.fetch_authority(citation)
        return result is not None

    async def check_connection(self) -> dict[str, str]:
        """Test connection to CourtListener API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._base_url}/courts/",
                    params={"limit": 1},
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return {"status": "connected", "adapter": self.adapter_name}
        except Exception as e:
            return {"status": "error", "adapter": self.adapter_name, "detail": str(e)}

    def _parse_search_result(self, item: dict) -> ResearchResult | None:
        """Parse a CourtListener search result into a ResearchResult.

        Args:
            item: Raw search result dict from CourtListener API.

        Returns:
            Parsed ResearchResult, or None if essential data is missing.
        """
        # Extract case name and citation
        case_name = item.get("caseName") or item.get("case_name") or ""
        citation_str = item.get("citation") or ""

        # Build citation from citation list if single citation field is empty
        if not citation_str:
            citations = item.get("citation", [])
            if isinstance(citations, list) and citations:
                citation_str = citations[0]
            elif not citation_str:
                # Use docket number as fallback
                citation_str = item.get("docketNumber") or item.get("docket_number") or ""

        if not case_name and not citation_str:
            return None

        # Extract court/jurisdiction
        court = item.get("court") or item.get("court_id") or ""

        # Build source URL
        absolute_url = item.get("absolute_url") or ""
        source_url = f"https://www.courtlistener.com{absolute_url}" if absolute_url else None

        # Extract snippet/excerpt
        snippet = item.get("snippet") or item.get("text") or ""
        if isinstance(snippet, str) and len(snippet) > 1000:
            snippet = snippet[:1000] + "..."

        # Determine relevance score (normalize CL score to 0-1)
        score = item.get("score")
        relevance = None
        if score is not None:
            try:
                # CL scores vary widely; normalize with log scaling
                relevance = min(1.0, float(score) / 100.0)
            except (ValueError, TypeError):
                pass

        return ResearchResult(
            citation=citation_str or case_name,
            title=case_name,
            authority_type="case_law",
            jurisdiction=str(court) if court else None,
            source_tool="courtlistener",
            source_url=source_url,
            excerpt=snippet if snippet else None,
            relevance_score=relevance,
            metadata={
                "court_id": court,
                "date_filed": item.get("dateFiled") or item.get("date_filed"),
                "docket_number": item.get("docketNumber") or item.get("docket_number"),
                "cluster_id": item.get("cluster_id"),
            },
        )
