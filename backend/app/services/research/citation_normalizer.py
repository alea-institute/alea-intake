"""CitationNormalizer -- eyecite-based Bluebook citation parser.

Parses legal citations into canonical forms for deduplication and verification.
Uses eyecite for full-case citation parsing and provides utilities for
comparing authorities, computing cache keys, and deduplicating research results.

Usage:
    normalizer = CitationNormalizer()
    cite = normalizer.normalize("Smith v. Jones, 123 F.3d 456 (9th Cir. 2020)")
    # cite.volume == 123, cite.reporter == "F.3d", cite.page == 456

    all_cites = normalizer.extract_all("See 123 F.3d 456 and 789 U.S. 101.")
    # [NormalizedCitation(...), NormalizedCitation(...)]

    same = normalizer.are_same_authority("123 F.3d 456", "123 F. 3d 456")
    # True
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel

from eyecite import get_citations
from eyecite.models import FullCaseCitation

if TYPE_CHECKING:
    from app.services.research.base import ResearchResult

logger = logging.getLogger(__name__)


class NormalizedCitation(BaseModel):
    """Canonical representation of a legal citation.

    Attributes:
        raw: Original citation string as provided.
        normalized: Canonical form (volume reporter page).
        volume: Volume number.
        reporter: Reporter abbreviation (e.g., "F.3d", "U.S.").
        page: Starting page number.
        pin_cite: Specific page within opinion, if present.
        court: Court abbreviation (e.g., "ca9", "scotus").
        year: Year of decision.
    """

    raw: str
    normalized: str
    volume: int | None = None
    reporter: str | None = None
    page: int | None = None
    pin_cite: str | None = None
    court: str | None = None
    year: int | None = None


def _normalize_reporter(reporter: str) -> str:
    """Normalize reporter string by collapsing internal whitespace.

    Handles variations like "F. 3d" vs "F.3d" by removing spaces
    that appear between periods and alphanumeric characters.
    """
    # Remove spaces after periods within the reporter abbreviation
    # e.g., "F. 3d" -> "F.3d", "F. Supp. 2d" -> "F.Supp.2d"
    return re.sub(r"\.\s+", ".", reporter).strip()


class CitationNormalizer:
    """Parses and normalizes legal citations using eyecite.

    Provides methods for citation normalization, comparison, deduplication,
    and deterministic cache key computation for research result caching.
    """

    def normalize(self, citation_str: str) -> NormalizedCitation | None:
        """Parse a citation string and return its canonical form.

        Uses eyecite.get_citations() to parse, extracts the first
        FullCaseCitation found, and builds a NormalizedCitation.

        Args:
            citation_str: A citation string to parse.

        Returns:
            NormalizedCitation if parseable, None otherwise.
        """
        if not citation_str or not citation_str.strip():
            return None

        citations = get_citations(citation_str)

        # Find the first FullCaseCitation
        full_cites = [c for c in citations if isinstance(c, FullCaseCitation)]
        if not full_cites:
            return None

        cite = full_cites[0]
        groups = cite.groups

        volume_str = groups.get("volume")
        reporter_str = groups.get("reporter")
        page_str = groups.get("page")

        volume = int(volume_str) if volume_str and volume_str.isdigit() else None
        page = int(page_str) if page_str and page_str.isdigit() else None

        # Normalize the reporter abbreviation
        reporter_norm = _normalize_reporter(reporter_str) if reporter_str else None

        # Build canonical normalized form: "{volume} {reporter} {page}"
        if volume is not None and reporter_norm and page is not None:
            normalized = f"{volume} {reporter_norm} {page}"
        else:
            normalized = cite.corrected_citation()

        # Extract metadata
        meta = cite.metadata
        court = meta.court if hasattr(meta, "court") else None
        year_str = meta.year if hasattr(meta, "year") else None
        year = int(year_str) if year_str and str(year_str).isdigit() else None
        pin_cite = meta.pin_cite if hasattr(meta, "pin_cite") else None

        return NormalizedCitation(
            raw=citation_str,
            normalized=normalized,
            volume=volume,
            reporter=reporter_str.strip() if reporter_str else None,
            page=page,
            pin_cite=str(pin_cite) if pin_cite else None,
            court=court,
            year=year,
        )

    def extract_all(self, text: str) -> list[NormalizedCitation]:
        """Extract all citations from a block of text.

        Args:
            text: Text potentially containing multiple legal citations.

        Returns:
            List of NormalizedCitation objects for each parseable citation.
        """
        if not text or not text.strip():
            return []

        citations = get_citations(text)
        results: list[NormalizedCitation] = []

        for cite in citations:
            if not isinstance(cite, FullCaseCitation):
                continue

            groups = cite.groups
            volume_str = groups.get("volume")
            reporter_str = groups.get("reporter")
            page_str = groups.get("page")

            volume = int(volume_str) if volume_str and volume_str.isdigit() else None
            page = int(page_str) if page_str and page_str.isdigit() else None
            reporter_norm = _normalize_reporter(reporter_str) if reporter_str else None

            if volume is not None and reporter_norm and page is not None:
                normalized = f"{volume} {reporter_norm} {page}"
            else:
                normalized = cite.corrected_citation()

            meta = cite.metadata
            court = meta.court if hasattr(meta, "court") else None
            year_str = meta.year if hasattr(meta, "year") else None
            year = int(year_str) if year_str and str(year_str).isdigit() else None
            pin_cite = meta.pin_cite if hasattr(meta, "pin_cite") else None

            results.append(
                NormalizedCitation(
                    raw=cite.corrected_citation(),
                    normalized=normalized,
                    volume=volume,
                    reporter=reporter_str.strip() if reporter_str else None,
                    page=page,
                    pin_cite=str(pin_cite) if pin_cite else None,
                    court=court,
                    year=year,
                )
            )

        return results

    def are_same_authority(self, cite_a: str, cite_b: str) -> bool:
        """Check if two citation strings refer to the same authority.

        Compares by normalized (volume, reporter, page) tuple after
        collapsing whitespace in reporter abbreviations.

        Args:
            cite_a: First citation string.
            cite_b: Second citation string.

        Returns:
            True if both parse to the same authority, False otherwise.
        """
        norm_a = self.normalize(cite_a)
        norm_b = self.normalize(cite_b)

        if norm_a is None or norm_b is None:
            return False

        # Compare by normalized tuple (volume, normalized_reporter, page)
        def _key(nc: NormalizedCitation) -> tuple:
            reporter = _normalize_reporter(nc.reporter) if nc.reporter else ""
            return (nc.volume, reporter, nc.page)

        return _key(norm_a) == _key(norm_b)

    def compute_query_hash(
        self, query: str, tool_name: str, jurisdiction: str | None
    ) -> str:
        """Compute a deterministic SHA-256 hash for a research query cache key.

        Normalizes inputs (lowercase, strip whitespace) before hashing
        to ensure queries that differ only in case or whitespace produce
        the same cache key.

        Args:
            query: The search query text.
            tool_name: The research tool adapter name.
            jurisdiction: Optional jurisdiction filter.

        Returns:
            64-character hex SHA-256 digest.
        """
        parts = [
            query.strip().lower(),
            tool_name.strip().lower(),
            (jurisdiction or "").strip().lower(),
        ]
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def deduplicate_results(
        self, results: list[ResearchResult]
    ) -> list[ResearchResult]:
        """Remove duplicate ResearchResults by normalized citation.

        Groups results by their normalized citation key (volume, reporter, page).
        For each group, keeps the result with the highest relevance_score.
        Results with unparseable citations are kept as-is (no dedup).

        Args:
            results: List of ResearchResult objects to deduplicate.

        Returns:
            Deduplicated list, preserving order of first occurrence.
        """
        if not results:
            return []

        seen: dict[str, ResearchResult] = {}
        unparseable: list[ResearchResult] = []

        for result in results:
            norm = self.normalize(result.citation)
            if norm is None:
                # Cannot normalize -- keep the result as-is
                unparseable.append(result)
                continue

            key = norm.normalized
            if key in seen:
                # Keep the one with higher relevance_score
                existing = seen[key]
                existing_score = existing.relevance_score or 0.0
                new_score = result.relevance_score or 0.0
                if new_score > existing_score:
                    seen[key] = result
            else:
                seen[key] = result

        # Preserve insertion order + append unparseable at end
        return list(seen.values()) + unparseable
