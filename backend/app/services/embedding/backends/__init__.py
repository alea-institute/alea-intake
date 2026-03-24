"""Embedding backend protocol and shared data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class SearchResult:
    """A single embedding search result with concept metadata."""

    iri: str
    label: str
    score: float
    metadata: dict | None = field(default=None)


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Protocol for embedding storage backends (FAISS, pgvector)."""

    async def upsert(self, iri: str, vector: list[float], metadata: dict) -> None: ...
    async def search(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]: ...
    async def delete_all(self) -> None: ...
    async def count(self) -> int: ...
