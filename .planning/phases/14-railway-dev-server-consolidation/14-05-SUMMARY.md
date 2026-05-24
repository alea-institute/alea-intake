# 14-05 SUMMARY — Dev runbook + retire demo service

**Completed:** 2026-05-24
**Status:** Complete

## What happened

- **Runbook:** Wrote `docs/DEV-DEPLOY-RUNBOOK.md` — how `alea-intake-dev` tracks
  `master`, env vars, smoke tests, the Postgres gotchas + fixes (NullPool,
  single-tenant public-schema routing, tz-aware timestamps), the `railway ssh` DB
  reset procedure, deploy-status GraphQL, and remote (browserless) CLI auth.
- **Retired demo (user-approved deletion):** Deleted both `alea-intake-demo`
  (`86f796a8…`) and `alea-intake-demo-db` (`f7bbda94…`) via the Railway
  `serviceDelete` API (both returned `true`). Its latest deploy had been CRASHED
  since the 2026-05-06 talk. Verified the `alea-tools` project now contains only
  `alea-intake-dev` + `alea-intake-dev-db` (no `*demo*` services).

## Result

The `alea-tools` project is consolidated to a single canonical dev/test server.
Spend from the redundant demo service + DB is eliminated.
