"""CourtListenerAdapter -- CourtListener REST API v4.3 research adapter.

Queries CourtListener for case law opinions and returns unified ResearchResults.
Per D-03, uses the /search/ endpoint with type=o for opinions, supporting
jurisdiction filtering via court= parameter.

API: https://www.courtlistener.com/api/rest/v4/
Auth: Token header. Rate limit: 5,000/hour.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.research.adapters.http_adapter import HTTPAdapter
from app.services.research.base import ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.courtlistener.com/api/rest/v4"


class CourtListenerAdapter(HTTPAdapter):
    """CourtListener REST API v4.3 research adapter.

    Searches US case law opinions via the CourtListener search API.
    Supports citation verification by exact citation lookup.

    Args:
        api_key: CourtListener API token (optional, for higher rate limits).
        base_url: Base URL override (default: CourtListener v4 API).
        timeout: Request timeout in seconds (default 30).
        client: Optional pre-configured httpx.AsyncClient for DI/testing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json",
            "User-Agent": "alea-intake/0.1.0",
        }
        if api_key:
            headers["Authorization"] = f"Token {api_key}"

        super().__init__(
            base_url=base_url or DEFAULT_BASE_URL,
            headers=headers,
            timeout=timeout,
            client=client,
        )
        self._api_key = api_key

    @property
    def adapter_name(self) -> str:
        return "courtlistener"

    @property
    def display_name(self) -> str:
        return "CourtListener"

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search CourtListener for opinions matching the query.

        Uses /search/ with type=o (opinions). Maps response fields:
        caseName -> title, citation -> citation, court -> jurisdiction,
        dateFiled -> date_decided, snippet -> relevance_snippet.

        Handles 429 with logged warning + empty results.
        """
        params: dict[str, Any] = {
            "q": query.query_text,
            "type": "o",
            "order_by": "score desc",
        }

        if query.jurisdiction:
            params["court"] = query.jurisdiction

        max_results = min(query.max_results, 50)

        try:
            response = await self._get("/search/", params=params)

            if response.status_code == 429:
                logger.warning("CourtListener rate limit hit for query: %s", query.query_text[:100])
                return []

            response.raise_for_status()
            data = response.json()

            results: list[ResearchResult] = []
            for item in data.get("results", [])[:max_results]:
                result = self._parse_search_result(item)
                if result:
                    results.append(result)

            return results

        except httpx.HTTPStatusError as e:
            logger.error("CourtListener API error: %s", e.response.status_code)
            return []
        except Exception as e:
            logger.error("CourtListener search failed: %s", e)
            return []

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch a specific authority by exact citation string."""
        try:
            response = await self._get(
                "/search/",
                params={"q": f'citation:("{citation}")', "type": "o"},
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if results:
                return self._parse_search_result(results[0])
        except Exception as e:
            logger.error("CourtListener fetch failed for '%s': %s", citation, e)

        return None

    async def verify_citation(self, citation: str) -> dict[str, Any]:
        """Verify whether a citation exists in CourtListener.

        Returns a dict with {verified: bool, source: str, metadata: dict}.
        Per D-08, provides verification source information.
        """
        result = await self.fetch_authority(citation)
        if result is not None:
            return {
                "verified": True,
                "source": "courtlistener",
                "metadata": {
                    "title": result.title,
                    "citation": result.citation,
                    "jurisdiction": result.jurisdiction,
                    "source_url": result.source_url,
                },
            }
        return {
            "verified": False,
            "source": "courtlistener",
            "metadata": {},
        }

    async def health_check(self) -> bool:
        """Test connection to CourtListener API."""
        try:
            response = await self._get("/courts/", params={"limit": 1})
            return response.status_code == 200
        except Exception:
            return False

    def _parse_search_result(self, item: dict) -> ResearchResult | None:
        """Parse a CourtListener search result into a ResearchResult."""
        case_name = item.get("caseName") or item.get("case_name") or ""
        raw_citation = item.get("citation")

        # CourtListener returns citation as either a string or a list of strings
        if isinstance(raw_citation, list):
            citation_str = raw_citation[0] if raw_citation else ""
        elif isinstance(raw_citation, str):
            citation_str = raw_citation
        else:
            citation_str = ""

        if not citation_str:
            citation_str = item.get("docketNumber") or item.get("docket_number") or ""

        if not case_name and not citation_str:
            return None

        court = item.get("court") or item.get("court_id") or ""
        absolute_url = item.get("absolute_url") or ""
        source_url = f"https://www.courtlistener.com{absolute_url}" if absolute_url else None

        snippet = item.get("snippet") or item.get("text") or ""
        if isinstance(snippet, str) and len(snippet) > 1000:
            snippet = snippet[:1000] + "..."

        score = item.get("score")
        relevance = None
        if score is not None:
            try:
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
