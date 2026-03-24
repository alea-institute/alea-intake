"""FAISS in-memory backend for SQLite mode.

Uses IndexFlatIP on L2-normalized vectors, which computes cosine similarity
via inner product. This avoids the need for a separate cosine index.
"""

from __future__ import annotations

import numpy as np

from app.services.embedding.backends import SearchResult


class FAISSBackend:
    """FAISS in-memory backend for SQLite mode.

    Uses IndexFlatIP on normalized vectors = cosine similarity.
    """

    def __init__(self) -> None:
        self._index = None  # faiss.IndexFlatIP, created lazily
        self._iri_map: dict[int, str] = {}  # internal_id -> IRI
        self._label_map: dict[int, str] = {}  # internal_id -> label
        self._metadata_map: dict[int, dict] = {}
        self._next_id: int = 0
        self._dimension: int | None = None

    def _ensure_index(self, dimension: int) -> None:
        if self._index is None:
            import faiss

            self._dimension = dimension
            self._index = faiss.IndexFlatIP(dimension)  # Inner product on normalized = cosine

    def _normalize(self, vector: list[float]) -> np.ndarray:
        v = np.array(vector, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return v

    async def upsert(self, iri: str, vector: list[float], metadata: dict) -> None:
        v = self._normalize(vector)
        self._ensure_index(v.shape[1])
        self._index.add(v)  # type: ignore[union-attr]
        idx = self._next_id
        self._iri_map[idx] = iri
        self._label_map[idx] = metadata.get("label", "")
        self._metadata_map[idx] = metadata
        self._next_id += 1

    async def search(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]:
        if self._index is None or self._index.ntotal == 0:
            return []
        q = self._normalize(query_vector)
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(q, k)
        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append(
                SearchResult(
                    iri=self._iri_map[int(idx)],
                    label=self._label_map[int(idx)],
                    score=float(score),
                    metadata=self._metadata_map.get(int(idx)),
                )
            )
        return results

    async def delete_all(self) -> None:
        self._index = None
        self._iri_map.clear()
        self._label_map.clear()
        self._metadata_map.clear()
        self._next_id = 0

    async def count(self) -> int:
        return self._index.ntotal if self._index else 0
