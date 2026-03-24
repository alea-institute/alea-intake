"""Local embedding provider using sentence-transformers.

Uses all-MiniLM-L6-v2 (384d) by default -- fast, small, good quality
for concept label matching. Normalizes embeddings for cosine similarity.
"""

from __future__ import annotations


class LocalEmbeddingProvider:
    """sentence-transformers based local embedding provider."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384d, fast, small

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = SentenceTransformer(self._model_name)
        self._dimension: int = self._model.get_sentence_embedding_dimension()

    def encode(self, text: str) -> list[float]:
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension
