"""EnrichClient -- HTTP client for folio-enrich document annotation API.

Per D-09, communicates with the folio-enrich service for document annotation
with FOLIO concept tagging. Supports submit, poll, and SSE streaming.

Default endpoint: http://localhost:8731 (configurable via FOLIO_ENRICH_URL env var).
Graceful degradation if service is unavailable per Pitfall 4.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ENRICH_URL = "http://localhost:8731"


class EnrichClient:
    """HTTP client for the folio-enrich document annotation service.

    Provides methods to submit documents for enrichment, poll for results,
    and get SSE stream URLs. Gracefully handles connection errors when
    the folio-enrich service is unavailable.

    Args:
        base_url: folio-enrich API base URL (default from FOLIO_ENRICH_URL env var).
        timeout: Request timeout in seconds (default 10).
        client: Optional pre-configured httpx.AsyncClient for DI/testing.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get("FOLIO_ENRICH_URL", DEFAULT_ENRICH_URL)
        self._timeout = timeout
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the injected client or create a new one."""
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self._timeout)

    async def submit(self, text: str) -> str | None:
        """Submit a document for enrichment.

        POSTs to /enrich with the document content. Returns the job_id
        for polling results.

        Args:
            text: Document text to annotate.

        Returns:
            Job ID string, or None if service is unavailable.
        """
        client = await self._get_client()
        owns_client = self._client is None

        try:
            response = await client.post(
                f"{self._base_url}/enrich",
                json={"content": text},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("job_id")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("folio-enrich unavailable: %s", e)
            return None
        except Exception as e:
            logger.error("folio-enrich submit failed: %s", e)
            return None
        finally:
            if owns_client:
                await client.aclose()

    async def get_results(self, job_id: str) -> dict[str, Any] | None:
        """Get enrichment results for a completed job.

        GETs /enrich/{job_id} and returns the annotation dict.

        Args:
            job_id: The job identifier from submit().

        Returns:
            Annotation result dict, or None if service is unavailable.
        """
        client = await self._get_client()
        owns_client = self._client is None

        try:
            response = await client.get(f"{self._base_url}/enrich/{job_id}")
            response.raise_for_status()
            return response.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("folio-enrich unavailable: %s", e)
            return None
        except Exception as e:
            logger.error("folio-enrich get_results failed: %s", e)
            return None
        finally:
            if owns_client:
                await client.aclose()

    def get_stream_url(self, job_id: str) -> str:
        """Get the SSE stream URL for a job's progress.

        Args:
            job_id: The job identifier from submit().

        Returns:
            Full URL for the SSE endpoint.
        """
        return f"{self._base_url}/enrich/{job_id}/stream"
