"""Cloud embedding provider stub for future cloud embedding support.

Placeholder for OpenAI text-embedding-3-small or similar cloud providers.
Implemented when an organization configures cloud embeddings.
"""

from __future__ import annotations


class CloudEmbeddingProvider:
    """Cloud embedding provider stub. Implemented when org configures cloud embeddings."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: str = "",
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._dimension = 1536  # OpenAI text-embedding-3-small default

    def encode(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Cloud embedding provider not yet implemented. Use local provider."
        )

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Cloud embedding provider not yet implemented. Use local provider."
        )

    @property
    def dimension(self) -> int:
        return self._dimension
