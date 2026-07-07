"""PostgreSQL pgvector backend for embedding storage and search.

Uses cosine distance operator <=> for similarity search. Stores embeddings
in the shared schema (FOLIO is global, not per-tenant).
"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.services.embedding.backends import SearchResult


class PgVectorBackend:
    """PostgreSQL pgvector backend. Uses cosine distance operator <=>."""

    def __init__(
        self,
        engine: AsyncEngine,
        table_name: str = "folio_embeddings",
        dimension: int = 384,
    ) -> None:
        self._engine = engine
        self._table_name = table_name
        self._dimension = dimension

    async def ensure_table(self) -> None:
        """Create the embedding table in shared schema (FOLIO is global, not per-tenant)."""
        async with self._engine.begin() as conn:
            # Fresh databases (e.g. create_all deployments with migrations
            # skipped) may not have the shared schema yet (BUG-9).
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS shared.{self._table_name} (
                        id SERIAL PRIMARY KEY,
                        iri VARCHAR(512) UNIQUE NOT NULL,
                        label VARCHAR(512),
                        embedding vector({self._dimension}),
                        metadata JSONB
                    )
                """)
            )

    async def upsert(self, iri: str, vector: list[float], metadata: dict) -> None:
        vec_str = "[" + ",".join(str(v) for v in vector) + "]"
        meta_str = json.dumps(metadata)
        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"""
                    INSERT INTO shared.{self._table_name} (iri, label, embedding, metadata)
                    VALUES (:iri, :label, :embedding, :metadata)
                    ON CONFLICT (iri) DO UPDATE SET
                        label = EXCLUDED.label,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """),
                {
                    "iri": iri,
                    "label": metadata.get("label", ""),
                    "embedding": vec_str,
                    "metadata": meta_str,
                },
            )

    async def upsert_many(self, rows: list[dict]) -> None:
        """Batch upsert: one transaction + executemany for a whole batch.

        Each row: {"iri", "vector", "metadata"}. Row-at-a-time upserts open
        one transaction per vector — ~18K transactions per index build.
        """
        if not rows:
            return
        params = [
            {
                "iri": r["iri"],
                "label": r["metadata"].get("label", ""),
                "embedding": "[" + ",".join(str(v) for v in r["vector"]) + "]",
                "metadata": json.dumps(r["metadata"]),
            }
            for r in rows
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"""
                    INSERT INTO shared.{self._table_name} (iri, label, embedding, metadata)
                    VALUES (:iri, :label, :embedding, :metadata)
                    ON CONFLICT (iri) DO UPDATE SET
                        label = EXCLUDED.label,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """),
                params,
            )

    async def search(self, query_vector: list[float], top_k: int = 10) -> list[SearchResult]:
        vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT iri, label, 1 - (embedding <=> :query) as score, metadata
                    FROM shared.{self._table_name}
                    ORDER BY embedding <=> :query
                    LIMIT :top_k
                """),
                {"query": vec_str, "top_k": top_k},
            )
            rows = result.fetchall()
        return [
            SearchResult(
                iri=r.iri,
                label=r.label,
                score=float(r.score),
                metadata=r.metadata,
            )
            for r in rows
        ]

    async def delete_all(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE shared.{self._table_name}"))

    async def count(self) -> int:
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM shared.{self._table_name}")
            )
            return result.scalar() or 0
