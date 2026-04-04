"""Legal research services -- pluggable adapter framework for legal research tools."""

from app.services.research.base import ResearchAdapter, ResearchQuery, ResearchResult
from app.services.research.registry import ResearchToolRegistry, get_research_registry
from app.services.research.verification import CitationVerifier, VerificationResult

__all__ = [
    "CitationVerifier",
    "ResearchAdapter",
    "ResearchQuery",
    "ResearchResult",
    "ResearchToolRegistry",
    "VerificationResult",
    "get_research_registry",
]
