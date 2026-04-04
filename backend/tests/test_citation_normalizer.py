"""Tests for CitationNormalizer with eyecite-based Bluebook citation parsing.

Tests cover normalization, extraction, deduplication, and cache key computation.
"""

from __future__ import annotations

import pytest

from app.services.research.citation_normalizer import CitationNormalizer, NormalizedCitation


@pytest.fixture
def normalizer() -> CitationNormalizer:
    return CitationNormalizer()


class TestNormalizeSingle:
    """Test 1: normalize() returns NormalizedCitation with volume, reporter, page."""

    def test_basic_federal_reporter(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("123 F.3d 456")
        assert result is not None
        assert result.volume == 123
        assert result.reporter == "F.3d"
        assert result.page == 456

    def test_us_reports(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("347 U.S. 483")
        assert result is not None
        assert result.volume == 347
        assert result.reporter == "U.S."
        assert result.page == 483

    def test_raw_preserved(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("123 F.3d 456")
        assert result is not None
        assert result.raw == "123 F.3d 456"


class TestNormalizeFromContext:
    """Test 2: normalize() extracts citation from context text."""

    def test_citation_with_case_name_and_parenthetical(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("Smith v. Jones, 123 F.3d 456 (9th Cir. 2020)")
        assert result is not None
        assert result.volume == 123
        assert result.reporter == "F.3d"
        assert result.page == 456
        assert result.court == "ca9"
        assert result.year == 2020

    def test_citation_with_pin_cite(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("Smith v. Jones, 123 F.3d 456, 789 (9th Cir. 2020)")
        assert result is not None
        assert result.pin_cite == "789"


class TestExtractAll:
    """Test 3: extract_all() returns list of NormalizedCitation objects."""

    def test_two_citations(self, normalizer: CitationNormalizer):
        results = normalizer.extract_all("See 123 F.3d 456 and 789 U.S. 101.")
        assert len(results) == 2
        assert results[0].volume == 123
        assert results[0].reporter == "F.3d"
        assert results[1].volume == 789
        assert results[1].reporter == "U.S."

    def test_empty_text(self, normalizer: CitationNormalizer):
        results = normalizer.extract_all("")
        assert results == []

    def test_no_citations(self, normalizer: CitationNormalizer):
        results = normalizer.extract_all("This text has no legal citations.")
        assert results == []


class TestAreSameAuthority:
    """Test 4 & 5: are_same_authority() compares normalized citations."""

    def test_same_with_whitespace_variation(self, normalizer: CitationNormalizer):
        # eyecite parses "F. 3d" as a different reporter string, but same volume/page
        # Our normalizer strips whitespace in reporters for comparison
        assert normalizer.are_same_authority("123 F.3d 456", "123 F. 3d 456") is True

    def test_different_authorities(self, normalizer: CitationNormalizer):
        assert normalizer.are_same_authority("123 F.3d 456", "789 U.S. 101") is False

    def test_unparseable_returns_false(self, normalizer: CitationNormalizer):
        assert normalizer.are_same_authority("not a citation", "also not") is False


class TestBluebookFormats:
    """Test 6: normalize handles common Bluebook formats."""

    def test_us_reports(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("500 U.S. 44")
        assert result is not None
        assert result.reporter == "U.S."
        assert result.court == "scotus"

    def test_federal_reporter_3d(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("456 F.3d 789")
        assert result is not None
        assert result.reporter == "F.3d"

    def test_federal_supplement(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("100 F. Supp. 2d 200")
        assert result is not None
        assert result.volume == 100
        assert result.page == 200


class TestGracefulDegradation:
    """Test 7: normalize returns None for unparseable strings."""

    def test_unparseable_returns_none(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("this is not a legal citation")
        assert result is None

    def test_empty_string_returns_none(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("")
        assert result is None

    def test_partial_citation_returns_none(self, normalizer: CitationNormalizer):
        result = normalizer.normalize("See Smith v. Jones")
        assert result is None


class TestComputeQueryHash:
    """Test 8: compute_query_hash returns deterministic SHA-256 hash."""

    def test_deterministic(self, normalizer: CitationNormalizer):
        h1 = normalizer.compute_query_hash("negligence", "courtlistener", "California")
        h2 = normalizer.compute_query_hash("negligence", "courtlistener", "California")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_different_inputs_different_hashes(self, normalizer: CitationNormalizer):
        h1 = normalizer.compute_query_hash("negligence", "courtlistener", "California")
        h2 = normalizer.compute_query_hash("negligence", "courtlistener", "New York")
        assert h1 != h2

    def test_case_insensitive(self, normalizer: CitationNormalizer):
        h1 = normalizer.compute_query_hash("Negligence", "CourtListener", "california")
        h2 = normalizer.compute_query_hash("negligence", "courtlistener", "california")
        assert h1 == h2

    def test_none_jurisdiction(self, normalizer: CitationNormalizer):
        h = normalizer.compute_query_hash("negligence", "courtlistener", None)
        assert len(h) == 64


class TestDeduplicateResults:
    """Test 9: deduplicate_results removes duplicates by normalized citation."""

    def test_deduplicates_same_citation(self, normalizer: CitationNormalizer):
        from app.services.research.base import ResearchResult

        results = [
            ResearchResult(
                citation="123 F.3d 456",
                title="Smith v. Jones",
                authority_type="case_law",
                relevance_score=0.9,
                source_tool="courtlistener",
            ),
            ResearchResult(
                citation="123 F.3d 456",
                title="Smith v. Jones (duplicate)",
                authority_type="case_law",
                relevance_score=0.7,
                source_tool="westlaw",
            ),
        ]
        deduped = normalizer.deduplicate_results(results)
        assert len(deduped) == 1
        # Should keep highest-scored
        assert deduped[0].relevance_score == 0.9

    def test_preserves_different_citations(self, normalizer: CitationNormalizer):
        from app.services.research.base import ResearchResult

        results = [
            ResearchResult(
                citation="123 F.3d 456",
                title="Smith v. Jones",
                authority_type="case_law",
                relevance_score=0.9,
                source_tool="courtlistener",
            ),
            ResearchResult(
                citation="789 U.S. 101",
                title="Doe v. Roe",
                authority_type="case_law",
                relevance_score=0.8,
                source_tool="courtlistener",
            ),
        ]
        deduped = normalizer.deduplicate_results(results)
        assert len(deduped) == 2

    def test_empty_list(self, normalizer: CitationNormalizer):
        deduped = normalizer.deduplicate_results([])
        assert deduped == []

    def test_unparseable_citations_kept(self, normalizer: CitationNormalizer):
        from app.services.research.base import ResearchResult

        results = [
            ResearchResult(
                citation="not a real citation",
                title="Something",
                authority_type="statute",
                relevance_score=0.5,
                source_tool="manual",
            ),
        ]
        deduped = normalizer.deduplicate_results(results)
        assert len(deduped) == 1


class TestNormalizedCitationModel:
    """Test NormalizedCitation Pydantic model fields."""

    def test_all_fields(self):
        nc = NormalizedCitation(
            raw="Smith v. Jones, 123 F.3d 456 (9th Cir. 2020)",
            normalized="123 F.3d 456",
            volume=123,
            reporter="F.3d",
            page=456,
            pin_cite="460",
            court="ca9",
            year=2020,
        )
        assert nc.raw.startswith("Smith")
        assert nc.normalized == "123 F.3d 456"
        assert nc.volume == 123
        assert nc.reporter == "F.3d"
        assert nc.page == 456
        assert nc.pin_cite == "460"
        assert nc.court == "ca9"
        assert nc.year == 2020

    def test_optional_fields_default_none(self):
        nc = NormalizedCitation(
            raw="123 F.3d 456",
            normalized="123 F.3d 456",
        )
        assert nc.volume is None
        assert nc.reporter is None
        assert nc.page is None
        assert nc.pin_cite is None
        assert nc.court is None
        assert nc.year is None
