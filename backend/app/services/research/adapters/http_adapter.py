"""HTTPAdapter -- base class for HTTP-based research tool adapters.

Provides shared httpx.AsyncClient management, base URL, headers,
and _get/_post helpers with configurable timeout. Concrete adapters
like CourtListenerAdapter and GoogleScholarAdapter extend this class.

Per D-01, both HTTP and MCP adapters return the same ResearchResult schema.
Per Pitfall 7, constructor accepts optional httpx.AsyncClient for DI/testing.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)


class NotConfiguredError(Exception):
    """Raised when an adapter requires credentials that are not configured."""

    pass


class HTTPAdapter(ResearchAdapter):
    """Base class for HTTP-based research tool adapters.

    Provides shared httpx.AsyncClient management with configurable base URL,
    headers, and timeout. Concrete subclasses implement discover(), fetch_authority(),
    and verify_citation() using the _get/_post helpers.

    Args:
        base_url: Base URL for the API.
        headers: Default headers for all requests.
        timeout: Request timeout in seconds (default 30).
        client: Optional pre-configured httpx.AsyncClient for DI/testing.
    """

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._headers = headers or {}
        self._timeout = timeout
        self._client = client

    @property
    def adapter_name(self) -> str:
        return "http"

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the injected client or create a new one."""
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self._timeout)

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute a GET request against the API.

        Args:
            path: URL path appended to base_url (or full URL if client is injected).
            params: Query parameters.
            headers: Additional headers (merged with defaults).

        Returns:
            httpx.Response object.
        """
        merged_headers = {**self._headers, **(headers or {})}
        url = f"{self._base_url}{path}" if not self._client else f"{self._base_url}{path}"

        client = await self._get_client()
        owns_client = self._client is None

        try:
            response = await client.get(url, params=params, headers=merged_headers)
            return response
        finally:
            if owns_client:
                await client.aclose()

    async def _post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute a POST request against the API.

        Args:
            path: URL path appended to base_url.
            json_data: JSON body.
            headers: Additional headers (merged with defaults).

        Returns:
            httpx.Response object.
        """
        merged_headers = {**self._headers, **(headers or {})}
        url = f"{self._base_url}{path}"

        client = await self._get_client()
        owns_client = self._client is None

        try:
            response = await client.post(url, json=json_data, headers=merged_headers)
            return response
        finally:
            if owns_client:
                await client.aclose()

    # -- Default implementations (subclasses override) --

    async def discover(self, query: ResearchQuery) -> list[ResearchResult]:
        raise NotImplementedError("Subclasses must implement discover()")

    async def fetch_authority(self, citation: str) -> ResearchResult | None:
        raise NotImplementedError("Subclasses must implement fetch_authority()")

    async def verify_citation(self, citation: str) -> bool:
        raise NotImplementedError("Subclasses must implement verify_citation()")
