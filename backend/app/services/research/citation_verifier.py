"""CitationVerifier -- multi-source citation verification pipeline.

Per D-05/D-07, every LLM-suggested citation must be verified against known
databases before presentation. This verifier uses a cache-first strategy
with parallel live refresh for stale entries:

1. Normalize citation via CitationNormalizer
2. Check local cache for fresh result (within TTL)
3. If stale or uncached, query all verification sources in parallel
4. Aggregate results: multiple sources increase confidence (D-05)
5. Update cache and return VerificationResult

Per D-08, each authority receives a verified/unverified/pending flag
with verification source information.

Per D-19, TTL defaults: 24 hours for case law, 7 days for statutes.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VerificationResult(BaseModel):
    """Result of a multi-source citation verification.

    Per D-08, tracks verification status, sources checked,
    confidence level, and metadata from verification sources.

    Attributes:
        status: "verified", "unverified", "pending", or "stale".
        sources_checked: List of source names that were queried.
        confidence: Aggregate confidence (0.0-1.0). Higher with more confirming sources.
        citation_normalized: Canonical citation form after normalization.
        metadata: Merged metadata from all verification sources.
        verified_at: Timestamp of this verification result.
    """

    status: str  # verified | unverified | pending | stale
    sources_checked: list[str] = []
    confidence: float = 0.0
    citation_normalized: str = ""
    metadata: dict[str, Any] = {}
    verified_at: datetime | None = None


class CitationVerifier:
    """Multi-source citation verification with cache-first strategy.

    Per D-05/D-06, checks local cache first, then queries all configured
    verification sources in parallel. Multiple confirming sources increase
    confidence. Results are cached with configurable TTL per authority type.

    Args:
        adapters: List of research adapters with verify_citation() method.
        citation_normalizer: CitationNormalizer for canonical form computation.
        case_law_ttl_hours: Cache TTL for case law citations (default 24h per D-19).
        statute_ttl_hours: Cache TTL for statute citations (default 168h / 7 days per D-19).
    """

    def __init__(
        self,
        adapters: list[Any] | None = None,
        citation_normalizer: Any | None = None,
        case_law_ttl_hours: int = 24,
        statute_ttl_hours: int = 168,
    ) -> None:
        self._adapters = adapters or []
        self._normalizer = citation_normalizer
        self._cache: dict[str, VerificationResult] = {}
        self._case_law_ttl = timedelta(hours=case_law_ttl_hours)
        self._statute_ttl = timedelta(hours=statute_ttl_hours)

    async def verify(self, citation_str: str) -> VerificationResult:
        """Verify a single citation against all configured sources.

        Pipeline:
        1. Normalize via CitationNormalizer
        2. Check cache for fresh result
        3. If stale/uncached, query all sources in parallel
        4. Aggregate and cache result

        Args:
            citation_str: Raw citation string to verify.

        Returns:
            VerificationResult with status, confidence, and source info.
        """
        # Step 1: Normalize
        normalized_key = citation_str
        if self._normalizer:
            norm = self._normalizer.normalize(citation_str)
            if norm:
                normalized_key = norm.normalized

        # Step 2: Check cache
        cached = self._cache.get(normalized_key)
        if cached and self._is_fresh(cached):
            return cached

        # Step 3: Query all sources in parallel
        source_results = await self._query_all_sources(citation_str)

        # Step 4: Aggregate results
        result = self._aggregate_results(normalized_key, source_results)

        # Step 5: Update cache
        self._cache[normalized_key] = result

        return result

    async def verify_batch(self, citations: list[str]) -> list[VerificationResult]:
        """Verify multiple citations in parallel.

        Uses asyncio.gather with return_exceptions=True for graceful
        handling of individual verification failures.

        Args:
            citations: List of citation strings to verify.

        Returns:
            List of VerificationResult objects (one per citation).
        """
        tasks = [self.verify(c) for c in citations]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[VerificationResult] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                logger.error("Verification failed for '%s': %s", citations[i], r)
                results.append(
                    VerificationResult(
                        status="unverified",
                        sources_checked=[],
                        confidence=0.0,
                        citation_normalized=citations[i],
                        metadata={"error": str(r)},
                        verified_at=datetime.now(timezone.utc),
                    )
                )
            else:
                results.append(r)

        return results

    def _is_fresh(self, result: VerificationResult) -> bool:
        """Check if a cached result is still within its TTL.

        Per D-19: case law = 24h, statutes = 7 days.
        Default to case law TTL if type unknown.
        """
        if result.verified_at is None:
            return False

        now = datetime.now(timezone.utc)
        verified_at = result.verified_at
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)

        age = now - verified_at

        # Use statute TTL if metadata indicates statute type
        authority_type = result.metadata.get("authority_type", "case_law")
        ttl = self._statute_ttl if authority_type == "statute" else self._case_law_ttl

        return age < ttl

    async def _query_all_sources(self, citation_str: str) -> list[dict[str, Any]]:
        """Query all adapters in parallel for citation verification.

        Uses asyncio.gather with return_exceptions=True per D-04/D-19.
        """
        if not self._adapters:
            return []

        async def _query_adapter(adapter: Any) -> dict[str, Any]:
            try:
                result = await adapter.verify_citation(citation_str)
                return result if isinstance(result, dict) else {"verified": False, "source": "unknown", "metadata": {}}
            except Exception as e:
                logger.warning("Adapter verification failed: %s", e)
                return {"verified": False, "source": "unknown", "metadata": {}, "error": str(e)}

        tasks = [_query_adapter(a) for a in self._adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        source_results: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                source_results.append({"verified": False, "source": "unknown", "metadata": {}})
            else:
                source_results.append(r)

        return source_results

    def _aggregate_results(
        self, normalized_key: str, source_results: list[dict[str, Any]]
    ) -> VerificationResult:
        """Aggregate results from multiple verification sources.

        Per D-05: Multiple sources increase confidence.
        Confidence formula:
        - 0 verified sources: 0.0
        - 1 verified source: 0.7
        - 2+ verified sources: 0.7 + 0.15 * (n-1), capped at 1.0
        """
        sources_checked: list[str] = []
        verified_count = 0
        merged_metadata: dict[str, Any] = {}

        for sr in source_results:
            source_name = sr.get("source", "unknown")
            sources_checked.append(source_name)

            if sr.get("verified"):
                verified_count += 1
                # Merge metadata from verified sources
                if sr.get("metadata"):
                    merged_metadata.update(sr["metadata"])

        if verified_count == 0:
            confidence = 0.0
            status = "unverified"
        elif verified_count == 1:
            confidence = 0.7
            status = "verified"
        else:
            confidence = min(1.0, 0.7 + 0.15 * (verified_count - 1))
            status = "verified"

        return VerificationResult(
            status=status,
            sources_checked=sources_checked,
            confidence=confidence,
            citation_normalized=normalized_key,
            metadata=merged_metadata,
            verified_at=datetime.now(timezone.utc),
        )
