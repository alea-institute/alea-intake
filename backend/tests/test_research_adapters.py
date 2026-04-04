"""Tests for research tool adapters: HTTP, MCP, CourtListener, Google Scholar, stubs.

All HTTP tests use httpx.MockTransport -- no real API calls.
All MCP tests use AsyncMock for FolioMCPClient.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.research.adapters.http_adapter import HTTPAdapter
from app.services.research.adapters.courtlistener import CourtListenerAdapter
from app.services.research.adapters.google_scholar import GoogleScholarAdapter
from app.services.research.adapters.mcp_adapter import MCPAdapter
from app.services.research.adapters.westlaw import WestlawAdapter
from app.services.research.adapters.clio_library import ClioLibraryAdapter
from app.services.research.adapters.midpage import MidpageAdapter
from app.services.research.adapters.descrybe import DescrybeAdapter
from app.services.research.base import ResearchQuery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_transport(handler):
    """Build an httpx.MockTransport from an async handler function."""
    return httpx.MockTransport(handler)


def _courtlistener_search_response() -> dict:
    """Sample CourtListener search response."""
    return {
        "count": 1,
        "results": [
            {
                "caseName": "Smith v. Jones",
                "citation": ["123 F.3d 456"],
                "court_id": "ca9",
                "dateFiled": "2020-01-15",
                "docketNumber": "20-12345",
                "absolute_url": "/opinion/12345/smith-v-jones/",
                "snippet": "The court held that...",
                "score": 45.0,
            }
        ],
    }


def _serpapi_response() -> dict:
    """Sample SerpAPI Google Scholar response."""
    return {
        "organic_results": [
            {
                "title": "Legal Analysis of Negligence Standards",
                "link": "https://scholar.google.com/scholar?q=negligence",
                "snippet": "This article examines negligence...",
                "publication_info": {"summary": "Journal of Legal Studies, 2023"},
            }
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: HTTPAdapter base class
# ---------------------------------------------------------------------------

class TestHTTPAdapterBase:
    """Test 1: HTTPAdapter base class provides _client, _base_url, _headers, _get/_post helpers."""

    def test_http_adapter_has_client_and_base_url(self):
        """HTTPAdapter stores base_url and can create a client."""
        # HTTPAdapter is abstract, test via a concrete subclass
        adapter = CourtListenerAdapter()
        assert adapter._base_url == "https://www.courtlistener.com/api/rest/v4"
        assert adapter._timeout == 30

    def test_http_adapter_accepts_injected_client(self):
        """HTTPAdapter accepts optional httpx.AsyncClient for DI (Pitfall 7)."""
        custom_client = httpx.AsyncClient()
        adapter = CourtListenerAdapter(client=custom_client)
        assert adapter._client is custom_client


# ---------------------------------------------------------------------------
# Test 2: CourtListenerAdapter.query()
# ---------------------------------------------------------------------------

class TestCourtListenerQuery:
    """Test 2: CourtListenerAdapter.query() constructs correct URL params and maps response."""

    @pytest.mark.asyncio
    async def test_query_constructs_correct_params(self):
        """query() builds q=, type=o, court= params and maps to ResearchResult list."""
        request_log = []

        def handler(request: httpx.Request) -> httpx.Response:
            request_log.append(request)
            return httpx.Response(200, json=_courtlistener_search_response())

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        adapter = CourtListenerAdapter(client=client)

        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")
        results = await adapter.discover(query)

        assert len(results) == 1
        assert results[0].citation == "123 F.3d 456"
        assert results[0].title == "Smith v. Jones"
        assert results[0].authority_type == "case_law"
        assert results[0].source_tool == "courtlistener"

        # Verify URL params
        req = request_log[0]
        assert "q=negligence" in str(req.url)
        assert "type=o" in str(req.url)
        assert "court=ca9" in str(req.url)


# ---------------------------------------------------------------------------
# Test 3: CourtListenerAdapter.verify_citation()
# ---------------------------------------------------------------------------

class TestCourtListenerVerifyCitation:
    """Test 3: verify_citation() searches by exact citation and returns dict."""

    @pytest.mark.asyncio
    async def test_verify_citation_found(self):
        """verify_citation() returns {verified: True} when citation found."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_courtlistener_search_response())

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        adapter = CourtListenerAdapter(client=client)

        result = await adapter.verify_citation("123 F.3d 456")
        assert result["verified"] is True
        assert result["source"] == "courtlistener"

    @pytest.mark.asyncio
    async def test_verify_citation_not_found(self):
        """verify_citation() returns {verified: False} when no results."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"count": 0, "results": []})

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        adapter = CourtListenerAdapter(client=client)

        result = await adapter.verify_citation("999 F.3d 999")
        assert result["verified"] is False


# ---------------------------------------------------------------------------
# Test 4: CourtListenerAdapter handles 429 rate limits
# ---------------------------------------------------------------------------

class TestCourtListenerRateLimit:
    """Test 4: CourtListenerAdapter handles 429 rate limit responses gracefully."""

    @pytest.mark.asyncio
    async def test_429_returns_empty_results(self):
        """429 response returns empty list with logged warning."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"detail": "Rate limit exceeded"})

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        adapter = CourtListenerAdapter(client=client)

        query = ResearchQuery(query_text="test query")
        results = await adapter.discover(query)
        assert results == []


# ---------------------------------------------------------------------------
# Test 5: GoogleScholarAdapter.query()
# ---------------------------------------------------------------------------

class TestGoogleScholarQuery:
    """Test 5: GoogleScholarAdapter.query() calls SerpAPI and maps to ResearchResult."""

    @pytest.mark.asyncio
    async def test_query_calls_serpapi(self):
        """query() uses engine=google_scholar param and maps to ResearchResult."""

        request_log = []

        def handler(request: httpx.Request) -> httpx.Response:
            request_log.append(request)
            return httpx.Response(200, json=_serpapi_response())

        transport = _mock_transport(handler)
        client = httpx.AsyncClient(transport=transport)
        adapter = GoogleScholarAdapter(api_key="test-key", client=client)

        query = ResearchQuery(query_text="negligence standards")
        results = await adapter.discover(query)

        assert len(results) == 1
        assert results[0].title == "Legal Analysis of Negligence Standards"
        assert results[0].source_tool == "google_scholar"

        # Verify engine param
        req = request_log[0]
        assert "engine=google_scholar" in str(req.url)


# ---------------------------------------------------------------------------
# Test 6: GoogleScholarAdapter raises NotConfiguredError without key
# ---------------------------------------------------------------------------

class TestGoogleScholarNoKey:
    """Test 6: GoogleScholarAdapter raises NotConfiguredError if no SerpAPI key."""

    @pytest.mark.asyncio
    async def test_no_key_raises_error(self):
        """query() raises NotConfiguredError without api_key."""
        from app.services.research.adapters.http_adapter import NotConfiguredError

        adapter = GoogleScholarAdapter()
        query = ResearchQuery(query_text="test")

        with pytest.raises(NotConfiguredError, match="SerpAPI"):
            await adapter.discover(query)


# ---------------------------------------------------------------------------
# Test 7: MCPAdapter.query()
# ---------------------------------------------------------------------------

class TestMCPAdapterQuery:
    """Test 7: MCPAdapter.query() uses FolioMCPClient.search_concepts() and maps results."""

    @pytest.mark.asyncio
    async def test_query_uses_search_concepts(self):
        """query() calls search_concepts and maps to ResearchResult with authority_type=secondary."""
        mock_mcp = AsyncMock()
        mock_mcp.search_concepts.return_value = [
            {"iri": "https://folio.openlegalstandard.org/concept001", "label": "Negligence", "definition": "A tort..."}
        ]

        adapter = MCPAdapter(mcp_client=mock_mcp)
        query = ResearchQuery(query_text="negligence")
        results = await adapter.discover(query)

        assert len(results) == 1
        assert results[0].source_tool == "folio-mcp"
        assert results[0].authority_type == "secondary"
        mock_mcp.search_concepts.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 8: MCPAdapter.verify_citation()
# ---------------------------------------------------------------------------

class TestMCPAdapterVerify:
    """Test 8: MCPAdapter.verify_citation() delegates to FolioMCPClient.get_concept()."""

    @pytest.mark.asyncio
    async def test_verify_delegates_to_get_concept(self):
        """verify_citation() uses get_concept for IRI-based verification."""
        mock_mcp = AsyncMock()
        mock_mcp.get_concept.return_value = {
            "iri": "https://folio.openlegalstandard.org/concept001",
            "label": "Negligence",
        }

        adapter = MCPAdapter(mcp_client=mock_mcp)
        result = await adapter.verify_citation("https://folio.openlegalstandard.org/concept001")
        assert result["verified"] is True
        mock_mcp.get_concept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_nonexistent_concept(self):
        """verify_citation() returns unverified for missing concept."""
        mock_mcp = AsyncMock()
        mock_mcp.get_concept.side_effect = Exception("Not found")

        adapter = MCPAdapter(mcp_client=mock_mcp)
        result = await adapter.verify_citation("https://folio.openlegalstandard.org/nonexist")
        assert result["verified"] is False


# ---------------------------------------------------------------------------
# Test 9: Commercial stubs raise NotConfiguredError
# ---------------------------------------------------------------------------

class TestCommercialStubs:
    """Test 9: All commercial stubs raise NotConfiguredError on query()."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("adapter_cls", [WestlawAdapter, ClioLibraryAdapter, MidpageAdapter, DescrybeAdapter])
    async def test_stub_query_raises_not_configured(self, adapter_cls):
        """Stub adapters raise NotConfiguredError when no credentials configured."""
        from app.services.research.adapters.http_adapter import NotConfiguredError

        adapter = adapter_cls()
        query = ResearchQuery(query_text="test")

        with pytest.raises(NotConfiguredError, match="API credentials"):
            await adapter.discover(query)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("adapter_cls", [WestlawAdapter, ClioLibraryAdapter, MidpageAdapter, DescrybeAdapter])
    async def test_stub_verify_raises_not_configured(self, adapter_cls):
        """Stub adapters raise NotConfiguredError on verify_citation()."""
        from app.services.research.adapters.http_adapter import NotConfiguredError

        adapter = adapter_cls()
        with pytest.raises(NotConfiguredError, match="API credentials"):
            await adapter.verify_citation("123 F.3d 456")


# ---------------------------------------------------------------------------
# Test 10: All adapter constructors accept optional httpx.AsyncClient
# ---------------------------------------------------------------------------

class TestAdapterDI:
    """Test 10: All adapter constructors accept optional httpx.AsyncClient for DI."""

    def test_courtlistener_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = CourtListenerAdapter(client=client)
        assert adapter._client is client

    def test_google_scholar_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = GoogleScholarAdapter(api_key="key", client=client)
        assert adapter._client is client

    def test_westlaw_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = WestlawAdapter(client=client)
        assert adapter._client is client

    def test_clio_library_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = ClioLibraryAdapter(client=client)
        assert adapter._client is client

    def test_midpage_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = MidpageAdapter(client=client)
        assert adapter._client is client

    def test_descrybe_accepts_client(self):
        client = httpx.AsyncClient()
        adapter = DescrybeAdapter(client=client)
        assert adapter._client is client
