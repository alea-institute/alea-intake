"""GoogleScholarAdapter -- SerpAPI-powered Google Scholar research adapter.

Queries academic legal sources via SerpAPI with engine=google_scholar.
Per D-03, requires an org-provided SerpAPI key. Raises NotConfiguredError
if no key is provided.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.research.adapters.http_adapter import HTTPAdapter, NotConfiguredError
from app.services.research.base import ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://serpapi.com"


class GoogleScholarAdapter(HTTPAdapter):
    """Google Scholar research adapter via SerpAPI.

    Uses the SerpAPI Google Scholar engine to search for academic legal
    sources. Requires a valid SerpAPI API key.

    Args:
        api_key: SerpAPI API key (required for operation).
        base_url: SerpAPI base URL override.
        timeout: Request timeout in seconds.
        client: Optional pre-configured httpx.AsyncClient for DI/testing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url or DEFAULT_BASE_URL,
            headers={"Accept": "application/json"},
            timeout=timeout,
            client=client,
        )
        self._api_key = api_key

    @property
    def adapter_name(self) -> str:
        return "google_scholar"

    @property
    def display_name(self) -> str:
        return "Google Scholar"

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search Google Scholar via SerpAPI.

        Raises NotConfiguredError if no SerpAPI key is configured.
        Maps organic_results to ResearchResult objects.
        """
        if not self._api_key:
            raise NotConfiguredError(
                "Google Scholar adapter requires a SerpAPI API key. "
                "Configure via organization settings."
            )

        params: dict[str, Any] = {
            "engine": "google_scholar",
            "q": query.query_text,
            "api_key": self._api_key,
        }

        try:
            response = await self._get("/search", params=params)
            response.raise_for_status()
            data = response.json()

            results: list[ResearchResult] = []
            for item in data.get("organic_results", []):
                result = self._parse_result(item)
                if result:
                    results.append(result)

            return results[:query.max_results]

        except NotConfiguredError:
            raise
        except httpx.HTTPStatusError as e:
            logger.error("SerpAPI error: %s", e.response.status_code)
            return []
        except Exception as e:
            logger.error("Google Scholar search failed: %s", e)
            return []

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch authority by citation. Limited for Scholar -- searches by citation text."""
        if not self._api_key:
            return None

        query = ResearchQuery(query_text=citation, max_results=1)
        results = await self.discover(query)
        return results[0] if results else None

    async def verify_citation(self, citation: str) -> dict[str, Any]:
        """Verify a citation via Google Scholar search.

        Returns {verified: bool, source: str, metadata: dict}.
        """
        if not self._api_key:
            raise NotConfiguredError(
                "Google Scholar adapter requires a SerpAPI API key."
            )

        result = await self.fetch_authority(citation)
        if result is not None:
            return {
                "verified": True,
                "source": "google_scholar",
                "metadata": {"title": result.title, "source_url": result.source_url},
            }
        return {"verified": False, "source": "google_scholar", "metadata": {}}

    async def health_check(self) -> bool:
        """Check if SerpAPI is reachable and key is valid."""
        if not self._api_key:
            return False
        try:
            response = await self._get("/search", params={"engine": "google_scholar", "q": "test", "api_key": self._api_key})
            return response.status_code == 200
        except Exception:
            return False

    def _parse_result(self, item: dict) -> ResearchResult | None:
        """Parse a SerpAPI organic result into a ResearchResult."""
        title = item.get("title", "")
        if not title:
            return None

        link = item.get("link", "")
        snippet = item.get("snippet", "")
        pub_info = item.get("publication_info", {})
        summary = pub_info.get("summary", "") if isinstance(pub_info, dict) else ""

        return ResearchResult(
            citation=title,  # Scholar results use title as citation identifier
            title=title,
            authority_type="secondary",
            jurisdiction=None,
            source_tool="google_scholar",
            source_url=link or None,
            excerpt=snippet or None,
            relevance_score=None,
            metadata={"publication_info": summary},
        )
