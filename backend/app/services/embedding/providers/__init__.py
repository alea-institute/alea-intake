"""Embedding provider protocol for encoding text to vectors."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding model providers (local, cloud)."""

    def encode(self, text: str) -> list[float]: ...
    def encode_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...
