---
phase: 14-railway-dev-server-consolidation
plan: 01
subsystem: backend / database + analysis orchestrator
tags: [asyncpg, sqlalchemy, connection-pool, concurrency, postgres, health-check]
requires:
  - "Real local PostgreSQL (pgvector/pgvector:pg17) for verification"
provides:
  - "Postgres engine with pool_pre_ping=True + pool_recycle=1800"
  - "Serialized per-jurisdiction analysis execution (no concurrent shared-connection use)"
  - "backend/scripts/smoke_postgres_concurrent.py regression guard"
affects:
  - "backend/app/db/engine.py"
  - "backend/app/services/analysis/orchestrator.py"
tech-stack:
  added: []
  patterns:
    - "pool_pre_ping + pool_recycle to validate/rotate pooled asyncpg connections"
    - "Sequential await over jurisdictions instead of asyncio.gather on a shared session"
key-files:
  created:
    - "backend/scripts/smoke_postgres_concurrent.py"
  modified:
    - "backend/app/db/engine.py"
    - "backend/app/services/analysis/orchestrator.py"
decisions:
  - "Serialize per-jurisdiction branches (one-line scheduling change) rather than plumb per-branch connections; true parallelism deferred"
  - "Verify on host port 55432 because host port 5432 was already taken by an unrelated container"
metrics:
  tasks_completed: 3
  files_created: 1
  files_modified: 2
  completed_date: 2026-05-22
---

# Phase 14 Plan 01: Fix asyncpg "another operation in progress" Summary

Hardened the Postgres engine with `pool_pre_ping`/`pool_recycle` and root-cause-fixed the asyncpg "another operation is in progress" bug by serializing the per-jurisdiction analysis branches that previously shared one asyncpg connection — verified clean against a real local PostgreSQL.

## What Was Done

### Task 1 — Harden the Postgres engine (commit `6c0401d`)
Added `pool_pre_ping=True` and `pool_recycle=1800` to the PostgreSQL branch of `create_engine()`. The SQLite branch is untouched.

```diff
         return create_async_engine(
             url,
             pool_size=20,
             max_overflow=10,
+            # pre_ping validates a pooled connection with a lightweight check
+            # before handing it out, dropping dead/poisoned asyncpg connections;
+            # recycle (1800s) caps connection lifetime so long-lived poisoned
+            # connections rotate out of the pool.
+            pool_pre_ping=True,
+            pool_recycle=1800,
             echo=settings.debug,
         )
```

- `pool_pre_ping` validates each pooled connection with a lightweight check before reuse, so a dead/poisoned asyncpg connection is dropped instead of re-handed-out (this is what kept breaking unrelated requests, including `/health`).
- `pool_recycle=1800` caps connection lifetime so any long-lived poisoned connection rotates out.

### Task 2 — Serialize per-jurisdiction branches (commit `360952d`)
Root-cause fix. `_run_parallel_jurisdictions` previously fanned branches out with `asyncio.gather`, and every branch drove the SHARED `self._session` (one asyncpg connection) — both through the stage instances (`_get_stage_instance` passes `db_session=self._session`) and through the orchestrator's own checkpoint writes (`self._session.add(stage_record)` / `await self._session.flush()` in `_execute_stage_inner`). asyncpg connections are not concurrency-safe, so this path never worked on Postgres — it only survived on the demo's SQLite (aiosqlite serializes internally).

The serialization change:

```diff
-        await asyncio.gather(
-            *[_jurisdiction_branch(j) for j in jurisdictions]
-        )
+        for j in jurisdictions:
+            await _jurisdiction_branch(j)
```

- The inner `_jurisdiction_branch` helper is unchanged (still `fact_map` → `gap_analyze` per jurisdiction). Per-jurisdiction order and per-branch stage order are preserved; output is identical — only the scheduling (sequential vs concurrent) changed.
- Added an explanatory docstring block on `_run_parallel_jurisdictions` recording WHY it is serialized and noting that true per-jurisdiction parallelism (per-branch connections + cross-session merge of the run/iteration ORM objects) is a deliberate follow-up.
- Removed the now-unused `import asyncio`; updated the stale module/class docstrings that still claimed "in parallel ... via asyncio.gather".
- No public signatures changed (`run`, `resume`, `override_convergence`, `_run_parallel_jurisdictions`, `__init__`); all six `STAGES` names unchanged.

Targeted tests green:
- `pytest -k "orchestrator or jurisdiction or parallel or analysis"` → **114 passed, 934 deselected**.
- `pytest -k "parallel_jurisdiction or run_parallel or jurisdiction"` → **9 passed**.

### Task 3 — Verify against a real local PostgreSQL (commit `2b497d1`)
Stood up a real `pgvector/pgvector:pg17` Postgres and proved the bug is gone.

**Postgres used** (container `alea14verify-db`, id `95a8dc82bc3d`, image `pgvector/pgvector:pg17`):
```
$ docker exec alea14verify-db pg_isready -U alea -d alea_intake
/var/run/postgresql:5432 - accepting connections
```

**Exact commands**

Bring up Postgres (see Deviations re: port 55432):
```
docker run -d --name alea14verify-db \
  -e POSTGRES_DB=alea_intake -e POSTGRES_USER=alea -e POSTGRES_PASSWORD=changeme \
  -p 55432:5432 pgvector/pgvector:pg17
docker exec alea14verify-db pg_isready -U alea -d alea_intake
```

(a) Health check (`app.observability.health.check_health`) against live Postgres:
```
cd backend && ALEA_DATABASE_BACKEND=postgresql ALEA_DB_HOST=localhost ALEA_DB_PORT=55432 \
  ALEA_DB_NAME=alea_intake ALEA_DB_USER=alea ALEA_DB_PASSWORD=changeme \
  ALEA_SECRET_KEY=smoke ALEA_SKIP_MIGRATIONS=true \
  uv run python <runner calling check_health()>
```
Observed `/health` JSON:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": { "status": "up" },
  "folio_owl": { "cached": true, "status": "up", "...": "..." },
  "folio_mcp": { "status": "unavailable" },
  "llm_provider": { "status": "configured" }
}
```
`database.status: up` — `SELECT 1` succeeds with no asyncpg error.

(b) Concurrency smoke (`backend/scripts/smoke_postgres_concurrent.py` — opens 12 independent `engine.connect()` + `SELECT 1` coroutines concurrently via `asyncio.gather`, then disposes the engine):
```
cd backend && ALEA_DATABASE_BACKEND=postgresql ALEA_DB_HOST=localhost ALEA_DB_PORT=55432 \
  ALEA_DB_NAME=alea_intake ALEA_DB_USER=alea ALEA_DB_PASSWORD=changeme \
  ALEA_SECRET_KEY=smoke ALEA_SKIP_MIGRATIONS=true \
  uv run python scripts/smoke_postgres_concurrent.py
```
Observed output (exit 0):
```
OK no asyncpg concurrency error (12 concurrent SELECT 1)
```

**Teardown** (Postgres removed after verification):
```
docker rm -f alea14verify-db   # -> REMOVED
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Verification Postgres on host port 55432 instead of 5432**
- **Found during:** Task 3
- **Issue:** `docker-compose.multi.yml` hard-maps `5432:5432`, but host port 5432 was already allocated by an unrelated running container (`ontokit-postgres`, also pgvector/pgvector:pg17). Compose `up db` failed with "Bind for 127.0.0.1:5432 failed: port is already allocated", and a compose port-override merged (rather than replaced) the port list.
- **Fix:** Ran the same `pgvector/pgvector:pg17` image directly via `docker run -p 55432:5432` with the compose file's documented env (db `alea_intake`, user `alea`, password `changeme`) and pointed the backend at `ALEA_DB_PORT=55432`. This is the same image/service the plan specifies — only the host port differs.
- **Files modified:** none (verification-only).
- **Commit:** n/a (no source change).

**2. [Rule 3 — Blocking issue] `app` package not importable from `scripts/`**
- **Found during:** Task 3
- **Issue:** Running `python scripts/smoke_postgres_concurrent.py` put `scripts/` (not `backend/`) on `sys.path[0]`, so `import app...` raised `ModuleNotFoundError: No module named 'app'`. (Tests work because pytest's rootdir is `backend/`; uvicorn works because it runs from `backend/`.)
- **Fix:** Added a small `sys.path.insert(0, backend_root)` shim at the top of the smoke script (derived from `Path(__file__).resolve().parent.parent`) so it runs standalone from any cwd. Imports kept below the shim with `# noqa: E402`.
- **Files modified:** `backend/scripts/smoke_postgres_concurrent.py` (committed `2b497d1`).

### Out-of-scope (deferred, NOT fixed)

Pre-existing ruff `F841` lint errors in `orchestrator.py` (`session_id` unused in `resume`, `current_avg` unused in `_evaluate_convergence`) — confirmed present on the pre-edit `HEAD~2` version and in methods this plan did not touch. Logged to `.planning/phases/14-railway-dev-server-consolidation/deferred-items.md` per the scope boundary; left untouched. New/modified files (`smoke_postgres_concurrent.py`, `engine.py`) pass ruff cleanly.

## Verification Summary

- `backend/app/db/engine.py` Postgres branch contains both `pool_pre_ping=True` and `pool_recycle=1800`; SQLite branch contains neither; file parses (ast).
- `_run_parallel_jurisdictions` contains no `asyncio.gather` (grep count 0) and uses a sequential `for j in jurisdictions: await _jurisdiction_branch(j)` loop; file parses; public API unchanged.
- Against a real local PostgreSQL (pgvector/pgvector:pg17): `/health` reports `database.status: up`, and 12 concurrent pooled sessions raised no asyncpg "another operation is in progress" (`OK no asyncpg concurrency error`, exit 0).
- Targeted test subset green (114 passed; 9 jurisdiction-focused passed).

Root cause is fixed in code and proven against a real PostgreSQL locally — the blocker keeping `alea-intake-dev` unhealthy on Postgres is cleared, without touching Railway (deferred to plan 14-02+).

## Self-Check: PASSED

- Files: `backend/scripts/smoke_postgres_concurrent.py`, `backend/app/db/engine.py`, `backend/app/services/analysis/orchestrator.py`, `14-01-SUMMARY.md` — all FOUND.
- Commits `6c0401d`, `360952d`, `2b497d1` — all FOUND in git history.
