"""Concurrency smoke test for the asyncpg pooled engine (Phase 14, plan 14-01).

Proves the pooled-engine + per-connection pattern survives REAL asyncpg
concurrency without raising "another operation is in progress".

This is the regression guard for the bug fixed in 14-01:
  - engine.py now uses pool_pre_ping + pool_recycle
  - orchestrator._run_parallel_jurisdictions no longer fans branches out over
    a single shared asyncpg connection

The script opens the configured engine, runs several independent
``engine.connect()`` sessions CONCURRENTLY via ``asyncio.gather`` -- each doing
a ``SELECT 1`` -- then disposes the engine. Each connect() draws its own
connection from the pool, so concurrency is safe; if the engine ever handed the
same asyncpg connection to two coroutines at once, asyncpg would raise
"another operation is in progress".

Run against a real Postgres, e.g.::

    ALEA_DATABASE_BACKEND=postgresql \
    ALEA_DB_HOST=localhost ALEA_DB_PORT=55432 \
    ALEA_DB_NAME=alea_intake ALEA_DB_USER=alea ALEA_DB_PASSWORD=changeme \
    ALEA_SECRET_KEY=smoke ALEA_SKIP_MIGRATIONS=true \
    uv run python scripts/smoke_postgres_concurrent.py

Prints ``OK no asyncpg concurrency error`` and exits 0 on success.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the backend/ root (which contains the `app` package) is importable
# whether this script is run as `python scripts/smoke_postgres_concurrent.py`
# (sys.path[0] == scripts/) or from the backend/ cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from app.db.engine import dispose_engine, get_engine  # noqa: E402

CONCURRENCY = 12


async def _one_select(idx: int) -> int:
    """Open an independent connection from the pool and run SELECT 1."""
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        value = result.scalar()
        assert value == 1, f"branch {idx} got {value!r}, expected 1"
        return idx


async def main() -> int:
    # Touch the engine once so the singleton is created before fan-out.
    get_engine()
    try:
        # Run many connect()+SELECT 1 coroutines CONCURRENTLY. If the pool ever
        # re-used a single asyncpg connection across two live coroutines, this
        # is exactly where "another operation is in progress" would fire.
        results = await asyncio.gather(
            *[_one_select(i) for i in range(CONCURRENCY)]
        )
        assert sorted(results) == list(range(CONCURRENCY))
    finally:
        await dispose_engine()

    print(f"OK no asyncpg concurrency error ({CONCURRENCY} concurrent SELECT 1)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
