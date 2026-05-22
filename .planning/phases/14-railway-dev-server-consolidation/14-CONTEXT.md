# Phase 14 Context — Railway Dev Server Consolidation

**Captured:** 2026-05-22
**Source:** Direct decision session (questions answered before planning)

## Goal

Make `alea-intake-dev` the single canonical Railway dev/test server: healthy on
PostgreSQL, auto-deploying from `master`, with the Phase 13 practice-area feature
live and verified. Retire the redundant `alea-intake-demo` service.

## Decisions made (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Which service is "dev" | **Repair the dedicated `alea-intake-dev` service** | Keeps a true PostgreSQL/pgvector test environment, not SQLite. (Demo service ran SQLite to dodge the DB bug.) |
| Branch the dev server tracks | **`master`** (merge Phase 13 first) | Dev = stable integration target; feature work merges to master then deploys. |
| Database backend for dev | **PostgreSQL** (follows from "repair dev") | Exercises the pgvector path that SQLite cannot. |

## Current-state findings (verified 2026-05-22)

- **Two Railway services exist** in the `alea-tools` project:
  - `alea-intake-dev` (`alea-intake-dev-production.up.railway.app`) — runs a
    **pre-Phase-13 build**; `/health` returns `degraded` with `database.status: down`.
  - `alea-intake-demo` (`alea-intake-demo-production.up.railway.app`) — healthy,
    SQLite-on-volume, auto-deploys `demo/practice-customization`, has the
    practice-area feature live. Created for the 2026-05-06 talk (now past).
- **Merge is a clean fast-forward:** `master` tip (`ebd6de0`) is the merge-base;
  `demo/practice-customization` is 10 commits ahead, zero divergence.
- **The asyncpg bug** (`another operation is in progress`) takes the dev Postgres
  down — it fires even on the health check's isolated `SELECT 1`, indicating a
  pooled connection got poisoned by concurrent use of a single asyncpg connection
  (asyncpg connections are not concurrency-safe) and the pool keeps handing it back.
- **`backend/app/db/engine.py`** Postgres branch has `pool_size=20, max_overflow=10`
  but **no `pool_pre_ping` and no `pool_recycle`** — so dead connections are never
  validated/recycled before reuse.
- **DB backend** selected by `database_backend` setting (env `ALEA_DATABASE_BACKEND`,
  default `postgresql`); SQLite path via `sqlite_path`.

## Constraints / blockers

- **Railway CLI is `Unauthorized`** — user must run `! railway login` (interactive)
  before any CLI-based deploy/config step. Pause point at the deploy phase.
- **Pushes are pre-authorized** for this repo (standing preference), but merging to
  `master` and changing DB connection handling are substantive — already approved.

## Approach

1. **Land code on master** — fast-forward merge + push `master`.
2. **Fix asyncpg bug** — add `pool_pre_ping=True` + `pool_recycle` (cheap, high-value
   first fix for the symptom), then root-cause/fix any concurrent shared-`AsyncSession`
   use (prime suspect: analysis orchestrator + `asyncio.gather`). Verify locally on
   Postgres before touching Railway.
3. **Wire auto-deploy** — connect `alea-intake-dev` to GitHub branch `master`; confirm
   `ALEA_DATABASE_BACKEND=postgresql`, `ALEA_DB_*`, `ALEA_SKIP_MIGRATIONS=true`.
4. **Verify** — `/health` healthy + DB up; `/api/practice-areas` returns `personal_injury`
   on the dev URL; browser smoke test of chip-row + PI welcome swap.
5. **Document & consolidate** — dev deploy runbook; retire `alea-intake-demo`.

## Fallback

If the asyncpg root cause proves deep, temporarily run dev on SQLite-on-volume (like
demo did) to unblock, with the Postgres fix tracked as follow-up. Not the plan — a net.

## Out of scope

- New product features or practice areas (Phase 13 delivered those).
- Production (non-dev) deployment topology.
- Alembic migration wiring (`ALEA_SKIP_MIGRATIONS=true`; `create_all` on startup stays).
