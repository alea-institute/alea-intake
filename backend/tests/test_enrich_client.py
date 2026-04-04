"""Tests for EnrichClient -- folio-enrich HTTP integration.

All tests use httpx.MockTransport -- no real API calls.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.folio_enrich.enrich_client import EnrichClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_transport(handler):
    """Build an httpx.MockTransport from an async handler function."""
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Test 11: EnrichClient.submit()
# ---------------------------------------------------------------------------

class TestEnrichSubmit:
    """Test 11: EnrichClient.submit(text) POSTs to /enrich and returns job_id."""

    @pytest.mark.asyncio
    async def test_submit_returns_job_id(self):
        """submit() POSTs text to /enrich and returns the job_id."""
        request_log = []

        def handler(request: httpx.Request) -> httpx.Response:
            request_log.append(request)
            return httpx.Response(200, json={"job_id": "job-abc-123"})

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        enrich = EnrichClient(base_url="http://localhost:8731", client=client)

        job_id = await enrich.submit("Some legal document text")
        assert job_id == "job-abc-123"

        # Verify POST to /enrich
        req = request_log[0]
        assert req.method == "POST"
        assert "/enrich" in str(req.url)


# ---------------------------------------------------------------------------
# Test 12: EnrichClient.get_results()
# ---------------------------------------------------------------------------

class TestEnrichGetResults:
    """Test 12: EnrichClient.get_results(job_id) GETs /enrich/{job_id} and returns dict."""

    @pytest.mark.asyncio
    async def test_get_results_returns_annotations(self):
        """get_results() fetches annotation results for a job."""
        annotations = {
            "job_id": "job-abc-123",
            "status": "complete",
            "annotations": [
                {"concept": "Negligence", "iri": "https://folio.openlegalstandard.org/concept001", "span": [0, 10]}
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=annotations)

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        enrich = EnrichClient(base_url="http://localhost:8731", client=client)

        result = await enrich.get_results("job-abc-123")
        assert result["status"] == "complete"
        assert len(result["annotations"]) == 1


# ---------------------------------------------------------------------------
# Test 13: EnrichClient handles connection errors gracefully
# ---------------------------------------------------------------------------

class TestEnrichConnectionErrors:
    """Test 13: EnrichClient gracefully handles connection errors (Pitfall 4)."""

    @pytest.mark.asyncio
    async def test_submit_connection_error_returns_none(self):
        """submit() returns None when folio-enrich is unavailable."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        enrich = EnrichClient(base_url="http://localhost:8731", client=client)

        result = await enrich.submit("text")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_results_connection_error_returns_none(self):
        """get_results() returns None when folio-enrich is unavailable."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        enrich = EnrichClient(base_url="http://localhost:8731", client=client)

        result = await enrich.get_results("job-abc-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stream_url(self):
        """get_stream_url() returns the SSE endpoint URL."""
        enrich = EnrichClient(base_url="http://localhost:8731")
        url = enrich.get_stream_url("job-abc-123")
        assert url == "http://localhost:8731/enrich/job-abc-123/stream"
