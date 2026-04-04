"""Citation verification service -- ground-truth checking of LLM-suggested authorities.

Every LLM-suggested citation must be verified against a known database before
being presented to the user. This service dispatches verification requests to
registered research adapters and records the results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.research.registry import ResearchToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a citation verification attempt.

    Attributes:
        citation: The citation that was verified.
        verified: Whether the citation was found and verified.
        status: Verification status (verified, unverified, not_found, error).
        verification_source: Which tool verified it (if any).
        confidence: Confidence in the verification (0.0-1.0).
        matched_title: Title of the matched authority.
        source_url: URL to the verified authority.
        error: Error message if verification failed.
    """

    citation: str
    verified: bool
    status: str  # "verified", "unverified", "not_found", "error"
    verification_source: str | None = None
    confidence: float | None = None
    matched_title: str | None = None
    source_url: str | None = None
    error: str | None = None


class CitationVerifier:
    """Verifies LLM-suggested citations against known research databases.

    Uses the ResearchToolRegistry to check citations against all configured
    and registered tools. Records verification results for audit trail.
    """

    def __init__(self, registry: ResearchToolRegistry) -> None:
        self._registry = registry

    async def verify(
        self,
        citation: str,
        tool_names: list[str] | None = None,
    ) -> VerificationResult:
        """Verify a single citation against configured tools.

        Tries each tool in order until one verifies the citation.

        Args:
            citation: Citation string to verify.
            tool_names: Specific tools to check. If None, checks all registered.

        Returns:
            VerificationResult with status and details.
        """
        if not citation or not citation.strip():
            return VerificationResult(
                citation=citation,
                verified=False,
                status="error",
                error="Empty citation",
            )

        try:
            result = await self._registry.verify_citation(citation, tool_names)

            if result.get("verified"):
                return VerificationResult(
                    citation=citation,
                    verified=True,
                    status="verified",
                    verification_source=result.get("verification_source"),
                    confidence=1.0,
                    matched_title=result.get("matched_title"),
                    source_url=result.get("source_url"),
                )
            else:
                return VerificationResult(
                    citation=citation,
                    verified=False,
                    status="not_found",
                    confidence=0.0,
                )

        except Exception as e:
            logger.error("Citation verification error for '%s': %s", citation, e)
            return VerificationResult(
                citation=citation,
                verified=False,
                status="error",
                error=str(e),
            )

    async def verify_batch(
        self,
        citations: list[str],
        tool_names: list[str] | None = None,
    ) -> list[VerificationResult]:
        """Verify multiple citations.

        Args:
            citations: List of citation strings to verify.
            tool_names: Specific tools to check.

        Returns:
            List of VerificationResult objects.
        """
        results = []
        for citation in citations:
            result = await self.verify(citation, tool_names)
            results.append(result)
        return results

    async def verify_and_persist(
        self,
        session: "AsyncSession",
        authority_id: int,
        citation: str,
        tool_names: list[str] | None = None,
    ) -> VerificationResult:
        """Verify a citation and persist the result to the database.

        Args:
            session: Async database session.
            authority_id: ID of the Authority record to update.
            citation: Citation string to verify.
            tool_names: Specific tools to check.

        Returns:
            VerificationResult with status and details.
        """
        from app.models.research import CitationVerification as CVModel

        result = await self.verify(citation, tool_names)

        # Persist the verification record
        verification_record = CVModel(
            authority_id=authority_id,
            verification_source=result.verification_source or "none",
            status=result.status,
            confidence=result.confidence,
            response_data={
                "matched_title": result.matched_title,
                "source_url": result.source_url,
            },
            error_message=result.error,
        )
        session.add(verification_record)
        await session.flush()

        return result
