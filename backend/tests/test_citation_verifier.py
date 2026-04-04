"""Tests for CitationVerifier and ResultRanker.

CitationVerifier: multi-source verification with cache-first strategy (D-05/D-06/D-08).
ResultRanker: 5-signal composite scoring with binding strength (D-15/D-17).

All tests use mocked adapters and DB sessions -- no real API calls.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.research.citation_verifier import CitationVerifier, VerificationResult
from app.services.research.result_ranker import ResultRanker
from app.services.research.base import ResearchQuery, ResearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    citation: str = "123 F.3d 456",
    title: str = "Smith v. Jones",
    authority_type: str = "case_law",
    jurisdiction: str | None = "ca9",
    source_tool: str = "courtlistener",
    relevance_score: float | None = 0.8,
    **kwargs,
) -> ResearchResult:
    """Build a ResearchResult for testing."""
    return ResearchResult(
        citation=citation,
        title=title,
        authority_type=authority_type,
        jurisdiction=jurisdiction,
        source_tool=source_tool,
        relevance_score=relevance_score,
        metadata=kwargs.get("metadata", {}),
    )


def _make_cached_authority(
    citation: str = "123 F.3d 456",
    verified: bool = True,
    verification_source: str = "courtlistener",
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a mock cached Authority record."""
    auth = MagicMock()
    auth.citation = citation
    auth.verified = verified
    auth.verification_status = "verified" if verified else "unverified"
    auth.verification_source = verification_source
    auth.created_at = created_at or datetime.now(timezone.utc)
    return auth


# ---------------------------------------------------------------------------
# Test 1: CitationVerifier.verify() normalizes and checks cache then live
# ---------------------------------------------------------------------------

class TestCitationVerifierBasic:
    """Test 1: verify() normalizes citation, checks cache, then queries CourtListener."""

    @pytest.mark.asyncio
    async def test_verify_normalizes_and_checks_sources(self):
        """verify() uses CitationNormalizer then queries verification sources."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="123 F.3d 456")

        mock_adapter = AsyncMock()
        mock_adapter.verify_citation.return_value = {
            "verified": True,
            "source": "courtlistener",
            "metadata": {"title": "Smith v. Jones"},
        }

        verifier = CitationVerifier(
            adapters=[mock_adapter],
            citation_normalizer=mock_normalizer,
        )

        result = await verifier.verify("123 F.3d 456")

        assert isinstance(result, VerificationResult)
        assert result.status in ("verified", "unverified", "pending", "stale")
        mock_normalizer.normalize.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: Cached + fresh citation returns immediately
# ---------------------------------------------------------------------------

class TestCacheHitFresh:
    """Test 2: Cached + fresh citation (within TTL) returns without live API call."""

    @pytest.mark.asyncio
    async def test_fresh_cache_skips_live_api(self):
        """Fresh cached result returns immediately without calling adapters."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="123 F.3d 456")

        mock_adapter = AsyncMock()

        verifier = CitationVerifier(
            adapters=[mock_adapter],
            citation_normalizer=mock_normalizer,
        )

        # Seed the cache with a fresh entry
        verifier._cache["123 F.3d 456"] = VerificationResult(
            status="verified",
            sources_checked=["courtlistener"],
            confidence=1.0,
            citation_normalized="123 F.3d 456",
            metadata={"title": "Smith v. Jones"},
            verified_at=datetime.now(timezone.utc),
        )

        result = await verifier.verify("123 F.3d 456")

        assert result.status == "verified"
        assert result.confidence == 1.0
        # Adapter should NOT have been called
        mock_adapter.verify_citation.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 3: Cached + stale triggers parallel live refresh
# ---------------------------------------------------------------------------

class TestCacheHitStale:
    """Test 3: Cached + stale citation triggers parallel live refresh."""

    @pytest.mark.asyncio
    async def test_stale_cache_triggers_refresh(self):
        """Stale cached result triggers a live verification call."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="123 F.3d 456")

        mock_adapter = AsyncMock()
        mock_adapter.verify_citation.return_value = {
            "verified": True,
            "source": "courtlistener",
            "metadata": {},
        }

        verifier = CitationVerifier(
            adapters=[mock_adapter],
            citation_normalizer=mock_normalizer,
            case_law_ttl_hours=24,
        )

        # Seed cache with a stale entry (older than TTL)
        verifier._cache["123 F.3d 456"] = VerificationResult(
            status="verified",
            sources_checked=["courtlistener"],
            confidence=1.0,
            citation_normalized="123 F.3d 456",
            metadata={},
            verified_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )

        result = await verifier.verify("123 F.3d 456")

        # Should have called the adapter for refresh
        mock_adapter.verify_citation.assert_awaited()
        assert result.status == "verified"


# ---------------------------------------------------------------------------
# Test 4: Uncached citation queries all sources in parallel
# ---------------------------------------------------------------------------

class TestParallelVerification:
    """Test 4: Uncached citation queries all verification sources in parallel."""

    @pytest.mark.asyncio
    async def test_parallel_source_queries(self):
        """Uncached citation uses asyncio.gather across all adapters."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="456 U.S. 789")

        adapter1 = AsyncMock()
        adapter1.verify_citation.return_value = {
            "verified": True,
            "source": "courtlistener",
            "metadata": {},
        }

        adapter2 = AsyncMock()
        adapter2.verify_citation.return_value = {
            "verified": False,
            "source": "google_scholar",
            "metadata": {},
        }

        verifier = CitationVerifier(
            adapters=[adapter1, adapter2],
            citation_normalizer=mock_normalizer,
        )

        result = await verifier.verify("456 U.S. 789")

        # Both adapters should have been called
        adapter1.verify_citation.assert_awaited()
        adapter2.verify_citation.assert_awaited()


# ---------------------------------------------------------------------------
# Test 5: Multiple verification sources increase confidence
# ---------------------------------------------------------------------------

class TestMultiSourceConfidence:
    """Test 5: Multiple verification sources increase confidence (D-05)."""

    @pytest.mark.asyncio
    async def test_two_sources_higher_confidence(self):
        """Verified by 2 sources produces higher confidence than 1 source."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="456 U.S. 789")

        adapter1 = AsyncMock()
        adapter1.verify_citation.return_value = {
            "verified": True,
            "source": "courtlistener",
            "metadata": {},
        }

        adapter2 = AsyncMock()
        adapter2.verify_citation.return_value = {
            "verified": True,
            "source": "google_scholar",
            "metadata": {},
        }

        verifier = CitationVerifier(
            adapters=[adapter1, adapter2],
            citation_normalizer=mock_normalizer,
        )

        result = await verifier.verify("456 U.S. 789")

        assert result.status == "verified"
        assert result.confidence > 0.5
        assert len(result.sources_checked) >= 2


# ---------------------------------------------------------------------------
# Test 6: Unverifiable citation returns unverified status
# ---------------------------------------------------------------------------

class TestUnverifiable:
    """Test 6: Unverifiable citation returns unverified with message."""

    @pytest.mark.asyncio
    async def test_unverifiable_citation(self):
        """All sources return unverified produces VerificationResult(status='unverified')."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.return_value = MagicMock(normalized="999 F.3d 999")

        adapter = AsyncMock()
        adapter.verify_citation.return_value = {
            "verified": False,
            "source": "courtlistener",
            "metadata": {},
        }

        verifier = CitationVerifier(
            adapters=[adapter],
            citation_normalizer=mock_normalizer,
        )

        result = await verifier.verify("999 F.3d 999")

        assert result.status == "unverified"
        assert "courtlistener" in result.sources_checked


# ---------------------------------------------------------------------------
# Test 7: verify_batch processes multiple citations in parallel
# ---------------------------------------------------------------------------

class TestVerifyBatch:
    """Test 7: verify_batch(citations) verifies in parallel."""

    @pytest.mark.asyncio
    async def test_batch_verification(self):
        """verify_batch processes multiple citations and returns list."""
        mock_normalizer = MagicMock()
        mock_normalizer.normalize.side_effect = [
            MagicMock(normalized="123 F.3d 456"),
            MagicMock(normalized="456 U.S. 789"),
        ]

        adapter = AsyncMock()
        adapter.verify_citation.return_value = {
            "verified": True,
            "source": "courtlistener",
            "metadata": {},
        }

        verifier = CitationVerifier(
            adapters=[adapter],
            citation_normalizer=mock_normalizer,
        )

        results = await verifier.verify_batch(["123 F.3d 456", "456 U.S. 789"])

        assert len(results) == 2
        assert all(isinstance(r, VerificationResult) for r in results)


# ---------------------------------------------------------------------------
# Test 8: ResultRanker.score() computes composite from 5 signals
# ---------------------------------------------------------------------------

class TestResultRankerScore:
    """Test 8: score() computes composite from relevance, recency, jurisdiction, court, verification."""

    def test_score_returns_float(self):
        """score() returns a float between 0 and 1."""
        ranker = ResultRanker()
        result = _make_result()
        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")

        score = ranker.score(result, query)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Test 9: ResultRanker.rank() sorts by composite score descending
# ---------------------------------------------------------------------------

class TestResultRankerRank:
    """Test 9: rank() sorts by composite score descending."""

    def test_rank_sorts_descending(self):
        """Higher-scoring results appear first."""
        ranker = ResultRanker()

        r1 = _make_result(citation="111 F.3d 111", relevance_score=0.9, jurisdiction="ca9")
        r2 = _make_result(citation="222 F.3d 222", relevance_score=0.2, jurisdiction="ny")
        r3 = _make_result(citation="333 F.3d 333", relevance_score=0.5, jurisdiction="ca9")

        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")
        ranked = ranker.rank([r2, r3, r1], query)

        scores = [ranker.score(r, query) for r in ranked]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Test 10: Jurisdictional match scores higher
# ---------------------------------------------------------------------------

class TestJurisdictionScoring:
    """Test 10: Same jurisdiction scores higher than different state (D-15)."""

    def test_same_jurisdiction_higher(self):
        """ca9 result scores higher than ny result for ca9 query."""
        ranker = ResultRanker()
        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")

        r_same = _make_result(jurisdiction="ca9", relevance_score=0.5)
        r_diff = _make_result(jurisdiction="ny", relevance_score=0.5)

        score_same = ranker.score(r_same, query)
        score_diff = ranker.score(r_diff, query)

        assert score_same > score_diff


# ---------------------------------------------------------------------------
# Test 11: Court level scoring
# ---------------------------------------------------------------------------

class TestCourtLevelScoring:
    """Test 11: Court level scoring: Supreme > Appeals > Trial (D-15)."""

    def test_supreme_scores_highest(self):
        """Supreme court results score higher than trial court."""
        ranker = ResultRanker()
        query = ResearchQuery(query_text="negligence")

        r_supreme = _make_result(metadata={"court_level": "supreme"}, relevance_score=0.5)
        r_trial = _make_result(metadata={"court_level": "trial"}, relevance_score=0.5)

        score_supreme = ranker.score(r_supreme, query)
        score_trial = ranker.score(r_trial, query)

        assert score_supreme > score_trial


# ---------------------------------------------------------------------------
# Test 12: Binding strength determination
# ---------------------------------------------------------------------------

class TestBindingStrength:
    """Test 12: Binding authorities from correct jurisdiction highlighted (D-17)."""

    def test_same_jurisdiction_binding(self):
        """Same jurisdiction case law marked as binding."""
        ranker = ResultRanker()
        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")
        result = _make_result(authority_type="case_law", jurisdiction="ca9")

        strength = ranker.determine_binding_strength(result, query)
        assert strength == "binding"

    def test_different_jurisdiction_persuasive(self):
        """Different jurisdiction case law marked as persuasive."""
        ranker = ResultRanker()
        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")
        result = _make_result(authority_type="case_law", jurisdiction="ny")

        strength = ranker.determine_binding_strength(result, query)
        assert strength == "persuasive"

    def test_secondary_source_is_secondary(self):
        """Secondary sources get binding_strength='secondary'."""
        ranker = ResultRanker()
        query = ResearchQuery(query_text="negligence", jurisdiction="ca9")
        result = _make_result(authority_type="secondary")

        strength = ranker.determine_binding_strength(result, query)
        assert strength == "secondary"
