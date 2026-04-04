"""MidpageAdapter -- stub for Midpage commercial research tool.

Per D-03, implements the adapter interface but raises NotConfiguredError
until API credentials are configured by the organization.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.research.adapters.http_adapter import HTTPAdapter, NotConfiguredError
from app.services.research.base import ResearchQuery, ResearchResult


class MidpageAdapter(HTTPAdapter):
    """Midpage research adapter stub.

    Raises NotConfiguredError on all operations until API credentials
    are configured. Ready for future implementation.

    Args:
        api_key: Midpage API key (required for operation).
        base_url: Midpage API base URL.
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
            base_url=base_url or "",
            timeout=timeout,
            client=client,
        )
        self._api_key = api_key

    @property
    def adapter_name(self) -> str:
        return "midpage"

    @property
    def display_name(self) -> str:
        return "Midpage"

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        """Search Midpage -- requires API credentials."""
        raise NotConfiguredError("Midpage adapter requires API credentials. Configure via organization settings.")

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        """Fetch from Midpage -- requires API credentials."""
        raise NotConfiguredError("Midpage adapter requires API credentials.")

    async def verify_citation(self, citation: str) -> dict[str, Any]:
        """Verify via Midpage -- requires API credentials."""
        raise NotConfiguredError("Midpage adapter requires API credentials.")
