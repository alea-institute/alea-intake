"""Embedding service package -- dual-backend vector search for FOLIO concepts."""

from app.services.embedding.backends import EmbeddingBackend, SearchResult
from app.services.embedding.service import EmbeddingService

__all__ = ["EmbeddingBackend", "EmbeddingService", "SearchResult"]
