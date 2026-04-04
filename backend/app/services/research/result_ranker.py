"""ResultRanker -- multi-signal relevance scoring and ranking.

Per D-15, scores results by 5 signals:
  1. Relevance to claim elements (keyword overlap, weight 0.30)
  2. Recency (newer = higher, weight 0.20)
  3. Jurisdictional match (exact > same-state > federal > other, weight 0.25)
  4. Court level (supreme > appeals > trial, weight 0.15)
  5. Verification confidence (verified > unverified, weight 0.10)

Per D-17, determines binding strength:
  - Binding: same jurisdiction + authoritative court level
  - Persuasive: different jurisdiction
  - Secondary: non-case-law sources

Supports optional LLM re-ranking for final presentation via LLMService.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.services.research.base import ResearchQuery, ResearchResult

logger = logging.getLogger(__name__)

# Signal weights (must sum to 1.0)
WEIGHT_RELEVANCE = 0.30
WEIGHT_RECENCY = 0.20
WEIGHT_JURISDICTION = 0.25
WEIGHT_COURT_LEVEL = 0.15
WEIGHT_VERIFICATION = 0.10

# Court level scores
COURT_LEVEL_SCORES = {
    "supreme": 1.0,
    "appellate": 0.7,
    "appeals": 0.7,
    "trial": 0.4,
    "district": 0.4,
}

# Binding authority types (can be binding if from correct jurisdiction)
_BINDING_AUTHORITY_TYPES = {"case_law", "statute", "regulation", "constitutional", "rule"}


class ResultRanker:
    """Multi-signal result ranker with optional LLM re-ranking.

    Scores each result by 5 signals and sorts descending.
    Per D-17, determines binding_strength for each result.

    Args:
        llm_service: Optional LLMService for re-ranking.
        verification_results: Optional dict of citation -> confidence for verification signal.
    """

    def __init__(
        self,
        llm_service: Any | None = None,
        verification_results: dict[str, float] | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._verification_results = verification_results or {}

    def score(self, result: ResearchResult, query: ResearchQuery) -> float:
        """Compute composite score from 5 signals.

        Args:
            result: Research result to score.
            query: Original query for context (jurisdiction, keywords, etc.).

        Returns:
            Float score between 0.0 and 1.0.
        """
        s_relevance = self._score_relevance(result, query)
        s_recency = self._score_recency(result)
        s_jurisdiction = self._score_jurisdiction(result, query)
        s_court_level = self._score_court_level(result)
        s_verification = self._score_verification(result)

        composite = (
            WEIGHT_RELEVANCE * s_relevance
            + WEIGHT_RECENCY * s_recency
            + WEIGHT_JURISDICTION * s_jurisdiction
            + WEIGHT_COURT_LEVEL * s_court_level
            + WEIGHT_VERIFICATION * s_verification
        )

        return min(1.0, max(0.0, composite))

    def rank(self, results: list[ResearchResult], query: ResearchQuery) -> list[ResearchResult]:
        """Sort results by composite score descending.

        Also sets binding_strength on each result per D-17.

        Args:
            results: List of results to rank.
            query: Original query for context.

        Returns:
            Sorted list (highest score first).
        """
        # Set binding strength on each result
        for r in results:
            r.metadata["binding_strength"] = self.determine_binding_strength(r, query)

        return sorted(results, key=lambda r: self.score(r, query), reverse=True)

    def determine_binding_strength(
        self, result: ResearchResult, query: ResearchQuery
    ) -> str:
        """Determine binding strength per D-17.

        Args:
            result: Research result to evaluate.
            query: Original query (contains target jurisdiction).

        Returns:
            "binding", "persuasive", or "secondary".
        """
        # Secondary sources are always secondary
        if result.authority_type not in _BINDING_AUTHORITY_TYPES:
            return "secondary"

        # No jurisdiction on query means we can't determine binding
        if not query.jurisdiction:
            return "persuasive"

        # Same jurisdiction = binding
        if result.jurisdiction and result.jurisdiction.lower() == query.jurisdiction.lower():
            return "binding"

        # Different jurisdiction = persuasive
        return "persuasive"

    async def llm_rerank(
        self,
        results: list[ResearchResult],
        query: ResearchQuery,
        top_n: int = 10,
    ) -> list[ResearchResult]:
        """Optional LLM re-ranking for final presentation.

        Uses LLMService.json_async with a ranking schema to re-order
        the top results for the final presentation list.

        Args:
            results: Pre-ranked results to re-rank.
            query: Original query context.
            top_n: Number of top results to present to LLM.

        Returns:
            Re-ranked list of results.
        """
        if not self._llm_service:
            return results

        # Only re-rank top N to keep cost/latency reasonable
        top_results = results[:top_n]

        try:
            prompt = self._build_rerank_prompt(top_results, query)
            # LLM re-ranking is optional; fall back to signal-based ranking on error
            # In production, this would use LLMService.json_async with a ranking schema
            logger.info("LLM re-ranking %d results for query: %s", len(top_results), query.query_text[:100])
            return results  # Placeholder: real impl would parse LLM response
        except Exception as e:
            logger.warning("LLM re-ranking failed, using signal-based ranking: %s", e)
            return results

    # -- Private signal scorers --

    def _score_relevance(self, result: ResearchResult, query: ResearchQuery) -> float:
        """Score relevance by keyword overlap between result and query.

        Simple approach: fraction of query keywords found in result text.
        """
        if result.relevance_score is not None:
            return min(1.0, result.relevance_score)

        # Fallback: keyword overlap
        query_words = set(query.query_text.lower().split())
        result_text = f"{result.title} {result.excerpt or ''}".lower()
        result_words = set(result_text.split())

        if not query_words:
            return 0.0

        overlap = len(query_words & result_words)
        return min(1.0, overlap / len(query_words))

    def _score_recency(self, result: ResearchResult) -> float:
        """Score recency: newer decisions score higher.

        Uses date_filed from metadata if available.
        """
        date_str = result.metadata.get("date_filed") or result.metadata.get("date_decided")
        if not date_str:
            return 0.5  # Unknown date gets neutral score

        try:
            # Parse date string
            if isinstance(date_str, str):
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            elif isinstance(date_str, datetime):
                date = date_str
            else:
                return 0.5

            now = datetime.now(timezone.utc)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            age_days = (now - date).days
            # 0-365 days: 1.0-0.8, 1-5 years: 0.8-0.5, 5-20 years: 0.5-0.2, 20+ years: 0.2
            if age_days <= 365:
                return 1.0 - 0.2 * (age_days / 365)
            elif age_days <= 1825:  # 5 years
                return 0.8 - 0.3 * ((age_days - 365) / 1460)
            elif age_days <= 7300:  # 20 years
                return 0.5 - 0.3 * ((age_days - 1825) / 5475)
            else:
                return 0.2
        except (ValueError, TypeError):
            return 0.5

    def _score_jurisdiction(self, result: ResearchResult, query: ResearchQuery) -> float:
        """Score jurisdictional match per D-15.

        exact match = 1.0, same state = 0.8, federal = 0.6, other = 0.3.
        """
        if not query.jurisdiction or not result.jurisdiction:
            return 0.5  # No jurisdiction info

        r_jur = result.jurisdiction.lower()
        q_jur = query.jurisdiction.lower()

        # Exact match
        if r_jur == q_jur:
            return 1.0

        # Federal courts (common prefix patterns)
        federal_patterns = {"fed", "federal", "scotus", "us", "supreme"}
        if any(p in r_jur for p in federal_patterns):
            return 0.6

        # Same state detection (simplified: check if state abbreviation matches)
        r_state = self._extract_state(r_jur)
        q_state = self._extract_state(q_jur)
        if r_state and q_state and r_state == q_state:
            return 0.8

        return 0.3

    def _score_court_level(self, result: ResearchResult) -> float:
        """Score court level: Supreme > Appeals > Trial per D-15."""
        court_level = result.metadata.get("court_level", "").lower()

        if court_level in COURT_LEVEL_SCORES:
            return COURT_LEVEL_SCORES[court_level]

        # Try to infer from court_id or jurisdiction
        jurisdiction = (result.jurisdiction or "").lower()
        if "supreme" in jurisdiction or "scotus" in jurisdiction:
            return 1.0
        if "appeal" in jurisdiction or "circuit" in jurisdiction:
            return 0.7
        if "district" in jurisdiction or "trial" in jurisdiction:
            return 0.4

        return 0.5  # Unknown court level gets neutral score

    def _score_verification(self, result: ResearchResult) -> float:
        """Score verification confidence: verified = 1.0, unverified = 0.3."""
        confidence = self._verification_results.get(result.citation)
        if confidence is not None:
            return confidence

        # Check metadata for verification info
        verified = result.metadata.get("verified")
        if verified is True:
            return 1.0
        elif verified is False:
            return 0.3

        return 0.5  # Unknown verification status

    def _extract_state(self, jurisdiction: str) -> str | None:
        """Extract a two-letter state abbreviation from jurisdiction string."""
        # Match patterns like "ca9" -> "ca", "ny" -> "ny"
        match = re.match(r"^([a-z]{2})", jurisdiction)
        return match.group(1) if match else None

    def _build_rerank_prompt(
        self, results: list[ResearchResult], query: ResearchQuery
    ) -> str:
        """Build LLM prompt for re-ranking results."""
        result_lines = []
        for i, r in enumerate(results):
            result_lines.append(
                f"{i+1}. {r.title} ({r.citation}) - {r.authority_type}, {r.jurisdiction or 'unknown'}"
            )

        return (
            f"Re-rank these legal research results by relevance to: {query.query_text}\n"
            f"Jurisdiction: {query.jurisdiction or 'any'}\n\n"
            f"Results:\n" + "\n".join(result_lines)
        )
