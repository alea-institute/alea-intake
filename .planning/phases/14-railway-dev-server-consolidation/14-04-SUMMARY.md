# 14-04 SUMMARY — Verify dev is the canonical test server

**Completed:** 2026-05-24
**Status:** Complete — dev fully functional on PostgreSQL and verified end-to-end.

## Verification results (live dev URL)

All against `https://alea-intake-dev-production.up.railway.app`:

- **`/health`** → `{"status":"healthy","database":{"status":"up"}}` ✅
- **`/api/practice-areas`** → `["personal_injury"]` (JSON, not SPA fallback) ✅
- **`/api/v1/auth/register`** → `201` with tokens ✅
- **`/api/v1/auth/login`** → `200` with tokens ✅
- **Browser smoke (chrome-devtools MCP):** login → consent → New intake →
  practice-area chip-row visible (`Generic` + `Personal Injury`); clicking
  **Personal Injury** swaps the welcome copy to PI text ("I help people understand
  legal options after an accident or injury… medical bills or police reports"). ✅

## Major deviation: the app had never actually run on PostgreSQL

The plan assumed verification would "just work" once deployed. Instead, hitting the
live DB exposed that the app was SQLite-first and had **never functioned on Postgres**.
Fixed three layered asyncpg/Postgres incompatibilities (each surfaced the next),
reproduced and fixed against a real local pgvector Postgres before deploying:

1. **`pool_pre_ping` cross-loop crash** (commit `dbe8a57`) — startup `create_all`
   raised `RuntimeError: got Future attached to a different loop`. asyncpg
   connections are loop-bound and the engine can init outside the serving loop, so a
   pooled connection got reused across loops. → Switched the Postgres engine to
   **`NullPool`** (no cross-loop reuse). Removed `pool_pre_ping`/`pool_recycle`
   (the 14-01 serialization already prevents intra-request poisoning).
2. **Schema-mode mismatch** (commit `835b332`) — `session.py` hardcoded
   `shared`→`"shared"` / `tenant`→`tenant_{slug}` for any non-SQLite backend, but
   `create_all` puts tables in `public`. → Routed **single-tenant** (the default) to
   `public` via the canonical mode intent; multi-tenant still uses named schemas.
3. **Naive vs tz-aware timestamps** (commit `835b332`) — columns were naive
   `DateTime`, but code inserts `datetime.now(timezone.utc)`; asyncpg rejects that.
   → Central Base `type_annotation_map {datetime: DateTime(timezone=True)}` +
   fixed the few explicit naive columns (refresh_token, knowledge_base).

**Validation:** local pgvector Postgres — cross-loop repro passes, `create_all`
builds 40 tables, register + login succeed. Full suite: **1045 passed, 3 skipped**.

## Dev DB reset (one-time)

The existing dev tables were naive-typed from an earlier deploy; `create_all` won't
ALTER existing tables. The dev Postgres is private-only (no public proxy), so reset
was run **from inside Railway's network** via `railway ssh --service alea-intake-dev`:
dropped + recreated the `public` schema (+ `CREATE EXTENSION vector`) and re-ran
`create_all`. Result: 40 tables, `refresh_tokens.expires_at` now
`timestamp with time zone`. No real data was lost (fresh dev DB).

## Test user (dev)

`dev-smoke@example.com` / `DevSmoke123!` registered on dev for smoke testing.

## Net effect

`alea-intake-dev` is now a genuinely functional PostgreSQL test server (not just a
healthy connection) — the practice-area feature and the core auth/intake flow work
live. Postgres compatibility was hardened as a side effect, which also benefits the
eventual production multi-tenant deployment.
