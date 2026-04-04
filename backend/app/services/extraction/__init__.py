"""Fact extraction services: LLM-driven extraction with structured output."""

from app.services.extraction.fact_extraction import FactExtractionService
from app.services.extraction.schemas import ExtractionResultSchema

__all__ = ["FactExtractionService", "ExtractionResultSchema"]
