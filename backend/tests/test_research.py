"""Tests for legal research infrastructure.

Covers: models, adapter ABC, registry, CourtListener adapter (mocked HTTP),
citation verification, and API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.models.research import (
    Authority,
    AuthorityType,
    CitationVerification,
    ResearchResult as ResearchResultModel,
    ResearchToolConfig,
    VerificationStatus,
)
from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult
from app.services.research.courtlistener import CourtListenerAdapter
from app.services.research.registry import ResearchToolRegistry
from app.services.research.verification import CitationVerifier, VerificationResult


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestResearchModels:
    """Test research DB model creation and attributes."""

    async def test_authority_creation(self, async_session):
        """Authority model stores legal authority with all fields."""
        auth = Authority(
            intake_id=1,
            citation="347 U.S. 483",
            title="Brown v. Board of Education",
            authority_type=AuthorityType.CASE_LAW.value,
            jurisdiction="us",
            folio_iri="https://folio.openlegalstandard.org/auth001",
            claim_iri="https://folio.openlegalstandard.org/obj001",
            source_tool="courtlistener",
            source_url="https://www.courtlistener.com/opinion/1/brown-v-board/",
            excerpt="Separate educational facilities are inherently unequal.",
            relevance_score=0.95,
            verified=True,
            verification_status="verified",
            verification_source="courtlistener",
        )
        async_session.add(auth)
        await async_session.flush()

        assert auth.id is not None
        assert auth.citation == "347 U.S. 483"
        assert auth.verified is True
        assert auth.authority_type == "case_law"

    async def test_research_result_creation(self, async_session):
        """ResearchResult model records a query and its results."""
        result = ResearchResultModel(
            intake_id=1,
            claim_iri="https://folio.openlegalstandard.org/obj001",
            jurisdiction="us",
            query_text="equal protection education segregation",
            tool_name="courtlistener",
            authority_count=5,
        )
        async_session.add(result)
        await async_session.flush()

        assert result.id is not None
        assert result.authority_count == 5

    async def test_research_tool_config_creation(self, async_session):
        """ResearchToolConfig stores per-org tool settings."""
        config = ResearchToolConfig(
            org_id=1,
            tool_name="courtlistener",
            display_name="CourtListener",
            enabled=True,
            base_url="https://www.courtlistener.com/api/rest/v4",
        )
        async_session.add(config)
        await async_session.flush()

        assert config.id is not None
        assert config.tool_name == "courtlistener"
        assert config.enabled is True

    async def test_citation_verification_creation(self, async_session):
        """CitationVerification records a verification attempt."""
        # First create an authority to reference
        auth = Authority(
            intake_id=1,
            citation="347 U.S. 483",
            title="Brown v. Board of Education",
            authority_type="case_law",
            source_tool="courtlistener",
        )
        async_session.add(auth)
        await async_session.flush()

        verification = CitationVerification(
            authority_id=auth.id,
            verification_source="courtlistener",
            status=VerificationStatus.VERIFIED.value,
            confidence=1.0,
        )
        async_session.add(verification)
        await async_session.flush()

        assert verification.id is not None
        assert verification.status == "verified"


# ---------------------------------------------------------------------------
# Adapter ABC tests
# ---------------------------------------------------------------------------

class TestResearchAdapterABC:
    """Test the abstract base class contract."""

    def test_cannot_instantiate_abc(self):
        """ResearchAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ResearchAdapter()

    def test_concrete_adapter_must_implement_methods(self):
        """Concrete adapter must implement all abstract methods."""

        class IncompleteAdapter(ResearchAdapter):
            @property
            def adapter_name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_concrete_adapter_works(self):
        """Fully implemented concrete adapter can be instantiated."""

        class TestAdapter(ResearchAdapter):
            @property
            def adapter_name(self):
                return "test"

            async def discover(self, query):
                return []

            async def fetch_authority(self, citation):
                return None

            async def verify_citation(self, citation):
                return False

        adapter = TestAdapter()
        assert adapter.adapter_name == "test"
        assert adapter.display_name == "Test"


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestResearchToolRegistry:
    """Test the research tool registry."""

    def setup_method(self):
        """Reset singleton before each test."""
        ResearchToolRegistry.reset()

    def _make_adapter(self, name: str = "test") -> ResearchAdapter:
        """Create a mock adapter."""
        adapter = MagicMock(spec=ResearchAdapter)
        adapter.adapter_name = name
        return adapter

    def test_singleton(self):
        """Registry is a singleton."""
        r1 = ResearchToolRegistry.get_instance()
        r2 = ResearchToolRegistry.get_instance()
        assert r1 is r2

    def test_register_and_list(self):
        """Can register adapters and list them."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("test")
        registry.register(adapter)

        assert "test" in registry.list_adapters()
        assert registry.get_adapter("test") is adapter

    def test_unregister(self):
        """Can unregister adapters."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("test")
        registry.register(adapter)
        registry.unregister("test")

        assert "test" not in registry.list_adapters()
        assert registry.get_adapter("test") is None

    async def test_query_tool(self):
        """Can query a specific registered tool."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("test")
        adapter.discover = AsyncMock(return_value=[
            ResearchResult(
                citation="347 U.S. 483",
                title="Brown v. Board of Education",
                authority_type="case_law",
            )
        ])
        registry.register(adapter)

        query = ResearchQuery(query_text="equal protection")
        results = await registry.query_tool("test", query)

        assert len(results) == 1
        assert results[0].citation == "347 U.S. 483"
        assert results[0].source_tool == "test"

    async def test_query_unregistered_tool_raises(self):
        """Querying an unregistered tool raises ValueError."""
        registry = ResearchToolRegistry.get_instance()
        query = ResearchQuery(query_text="test")

        with pytest.raises(ValueError, match="not registered"):
            await registry.query_tool("nonexistent", query)

    async def test_query_all_merges_results(self):
        """query_all merges and deduplicates results from multiple tools."""
        registry = ResearchToolRegistry.get_instance()

        adapter1 = self._make_adapter("tool1")
        adapter1.discover = AsyncMock(return_value=[
            ResearchResult(citation="347 U.S. 483", title="Brown", authority_type="case_law", relevance_score=0.8),
        ])

        adapter2 = self._make_adapter("tool2")
        adapter2.discover = AsyncMock(return_value=[
            ResearchResult(citation="347 U.S. 483", title="Brown v. Board", authority_type="case_law", relevance_score=0.9),
            ResearchResult(citation="410 U.S. 113", title="Roe v. Wade", authority_type="case_law", relevance_score=0.7),
        ])

        registry.register(adapter1)
        registry.register(adapter2)

        query = ResearchQuery(query_text="test", max_results=10)
        results = await registry.query_all(query)

        # Should deduplicate "347 U.S. 483" (keep higher score) and include Roe
        assert len(results) == 2
        # Highest relevance first
        brown = next(r for r in results if "483" in r.citation)
        assert brown.relevance_score == 0.9

    async def test_query_tool_handles_error_gracefully(self):
        """query_tool returns empty list on adapter error."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("failing")
        adapter.discover = AsyncMock(side_effect=ConnectionError("API down"))
        registry.register(adapter)

        query = ResearchQuery(query_text="test")
        results = await registry.query_tool("failing", query)
        assert results == []

    async def test_verify_citation_finds_match(self):
        """verify_citation returns verified when a tool confirms the citation."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("test")
        adapter.verify_citation = AsyncMock(return_value=True)
        adapter.fetch_authority = AsyncMock(return_value=ResearchResult(
            citation="347 U.S. 483",
            title="Brown v. Board of Education",
            authority_type="case_law",
            source_url="https://example.com/brown",
        ))
        registry.register(adapter)

        result = await registry.verify_citation("347 U.S. 483")
        assert result["verified"] is True
        assert result["verification_source"] == "test"

    async def test_verify_citation_not_found(self):
        """verify_citation returns not_found when no tool confirms."""
        registry = ResearchToolRegistry.get_instance()
        adapter = self._make_adapter("test")
        adapter.verify_citation = AsyncMock(return_value=False)
        registry.register(adapter)

        result = await registry.verify_citation("999 U.S. 999")
        assert result["verified"] is False
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# CourtListener adapter tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCourtListenerAdapter:
    """Test CourtListener adapter with mocked HTTP responses."""

    def _make_adapter(self) -> CourtListenerAdapter:
        return CourtListenerAdapter(api_key="test-key", base_url="https://cl.test/api/rest/v4")

    def _mock_search_response(self, results: list[dict] | None = None) -> httpx.Response:
        """Create a mock search response."""
        if results is None:
            results = [
                {
                    "caseName": "Brown v. Board of Education",
                    "citation": "347 U.S. 483",
                    "court": "scotus",
                    "absolute_url": "/opinion/1/brown-v-board/",
                    "snippet": "Separate educational facilities are inherently unequal.",
                    "score": 85.0,
                    "dateFiled": "1954-05-17",
                    "docketNumber": "No. 1",
                }
            ]
        return httpx.Response(
            status_code=200,
            json={"results": results, "count": len(results)},
            request=httpx.Request("GET", "https://cl.test/api/rest/v4/search/"),
        )

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_discover_returns_results(self, mock_client_cls):
        """discover() returns parsed results from CourtListener search."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        query = ResearchQuery(query_text="equal protection education")
        results = await adapter.discover(query)

        assert len(results) == 1
        assert results[0].citation == "347 U.S. 483"
        assert results[0].title == "Brown v. Board of Education"
        assert results[0].authority_type == "case_law"
        assert results[0].source_url == "https://www.courtlistener.com/opinion/1/brown-v-board/"

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_discover_handles_empty_results(self, mock_client_cls):
        """discover() returns empty list when no results found."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        results = await adapter.discover(ResearchQuery(query_text="xyznonexistent"))
        assert results == []

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_discover_handles_timeout(self, mock_client_cls):
        """discover() returns empty list on timeout."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        results = await adapter.discover(ResearchQuery(query_text="test"))
        assert results == []

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_fetch_authority_found(self, mock_client_cls):
        """fetch_authority() returns details for a known citation."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        result = await adapter.fetch_authority("347 U.S. 483")

        assert result is not None
        assert result.title == "Brown v. Board of Education"

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_fetch_authority_not_found(self, mock_client_cls):
        """fetch_authority() returns None when citation not found."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        result = await adapter.fetch_authority("999 U.S. 999")
        assert result is None

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_verify_citation_true(self, mock_client_cls):
        """verify_citation() returns True for found citation."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        assert await adapter.verify_citation("347 U.S. 483") is True

    @patch("app.services.research.courtlistener.httpx.AsyncClient")
    async def test_verify_citation_false(self, mock_client_cls):
        """verify_citation() returns False for missing citation."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._mock_search_response([]))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        adapter = self._make_adapter()
        assert await adapter.verify_citation("999 U.S. 999") is False

    def test_adapter_properties(self):
        """Adapter has correct name and display name."""
        adapter = self._make_adapter()
        assert adapter.adapter_name == "courtlistener"
        assert adapter.display_name == "CourtListener"


# ---------------------------------------------------------------------------
# Citation Verifier tests
# ---------------------------------------------------------------------------

class TestCitationVerifier:
    """Test the citation verification service."""

    def setup_method(self):
        ResearchToolRegistry.reset()

    async def test_verify_found(self):
        """Verifier returns verified result when tool confirms citation."""
        registry = ResearchToolRegistry.get_instance()
        adapter = MagicMock(spec=ResearchAdapter)
        adapter.adapter_name = "test"
        adapter.verify_citation = AsyncMock(return_value=True)
        adapter.fetch_authority = AsyncMock(return_value=ResearchResult(
            citation="347 U.S. 483",
            title="Brown v. Board",
            authority_type="case_law",
            source_url="https://example.com/brown",
        ))
        registry.register(adapter)

        verifier = CitationVerifier(registry)
        result = await verifier.verify("347 U.S. 483")

        assert result.verified is True
        assert result.status == "verified"
        assert result.verification_source == "test"
        assert result.confidence == 1.0

    async def test_verify_not_found(self):
        """Verifier returns not_found when no tool confirms."""
        registry = ResearchToolRegistry.get_instance()
        adapter = MagicMock(spec=ResearchAdapter)
        adapter.adapter_name = "test"
        adapter.verify_citation = AsyncMock(return_value=False)
        registry.register(adapter)

        verifier = CitationVerifier(registry)
        result = await verifier.verify("999 U.S. 999")

        assert result.verified is False
        assert result.status == "not_found"
        assert result.confidence == 0.0

    async def test_verify_empty_citation(self):
        """Verifier returns error for empty citation."""
        registry = ResearchToolRegistry.get_instance()
        verifier = CitationVerifier(registry)
        result = await verifier.verify("")

        assert result.verified is False
        assert result.status == "error"
        assert "Empty" in (result.error or "")

    async def test_verify_batch(self):
        """verify_batch processes multiple citations."""
        registry = ResearchToolRegistry.get_instance()
        adapter = MagicMock(spec=ResearchAdapter)
        adapter.adapter_name = "test"
        adapter.verify_citation = AsyncMock(side_effect=[True, False])
        adapter.fetch_authority = AsyncMock(return_value=ResearchResult(
            citation="347 U.S. 483", title="Brown", authority_type="case_law",
        ))
        registry.register(adapter)

        verifier = CitationVerifier(registry)
        results = await verifier.verify_batch(["347 U.S. 483", "999 U.S. 999"])

        assert len(results) == 2
        assert results[0].verified is True
        assert results[1].verified is False

    async def test_verify_and_persist(self, async_session):
        """verify_and_persist saves a CitationVerification record."""
        registry = ResearchToolRegistry.get_instance()
        adapter = MagicMock(spec=ResearchAdapter)
        adapter.adapter_name = "test"
        adapter.verify_citation = AsyncMock(return_value=True)
        adapter.fetch_authority = AsyncMock(return_value=ResearchResult(
            citation="347 U.S. 483", title="Brown", authority_type="case_law",
        ))
        registry.register(adapter)

        # Create a stub authority to reference
        auth = Authority(
            intake_id=1,
            citation="347 U.S. 483",
            title="Brown v. Board",
            authority_type="case_law",
            source_tool="test",
        )
        async_session.add(auth)
        await async_session.flush()

        verifier = CitationVerifier(registry)
        result = await verifier.verify_and_persist(
            async_session, auth.id, "347 U.S. 483"
        )

        assert result.verified is True

        # Verify the DB record was created
        db_result = await async_session.execute(
            select(CitationVerification).where(
                CitationVerification.authority_id == auth.id
            )
        )
        cv = db_result.scalar_one()
        assert cv.status == "verified"
        assert cv.verification_source == "test"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestResearchConfig:
    """Test research config settings."""

    def test_config_has_research_settings(self):
        """Config includes research tool settings."""
        from app.config import Settings

        # Create settings with required field
        s = Settings(secret_key="test-key")
        assert s.courtlistener_base_url == "https://www.courtlistener.com/api/rest/v4"
        assert s.research_timeout_seconds == 30
        assert s.research_max_results_per_query == 20


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestResearchSchemas:
    """Test Pydantic request/response schemas."""

    def test_research_query_request(self):
        """ResearchQueryRequest validates properly."""
        from app.schemas.research import ResearchQueryRequest

        req = ResearchQueryRequest(
            query_text="equal protection education",
            jurisdiction="us",
            max_results=10,
        )
        assert req.query_text == "equal protection education"
        assert req.max_results == 10

    def test_research_query_request_min_length(self):
        """ResearchQueryRequest rejects short query text."""
        from app.schemas.research import ResearchQueryRequest

        with pytest.raises(Exception):
            ResearchQueryRequest(query_text="ab")

    def test_verify_citation_request(self):
        """VerifyCitationRequest validates properly."""
        from app.schemas.research import VerifyCitationRequest

        req = VerifyCitationRequest(citation="347 U.S. 483")
        assert req.citation == "347 U.S. 483"

    def test_authority_response_from_attributes(self):
        """AuthorityResponse can be created from ORM attributes."""
        from app.schemas.research import AuthorityResponse

        resp = AuthorityResponse(
            citation="347 U.S. 483",
            title="Brown v. Board",
            authority_type="case_law",
            source_tool="courtlistener",
            verified=True,
        )
        assert resp.verified is True
