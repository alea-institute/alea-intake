# 14-03 SUMMARY — Wire dev auto-deploy + redeploy

**Completed:** 2026-05-24
**Status:** Complete

## What happened

- **Auth:** User authenticated the Railway CLI via browserless pairing (run under a
  pseudo-TTY with `script` since the remote shell has no TTY). `railway whoami` →
  Damien Riehl.
- **Discovery:** `alea-intake-dev` had **no GitHub source and no repo trigger** — it
  had been deployed via `railway up` (CLI image push), which is why pushing `master`
  never deployed it. (The demo service, by contrast, was GitHub-connected to the demo
  branch.)
- **Connected to master:** `serviceConnect(alea-intake-dev, repo=alea-institute/alea-intake,
  branch=master)` via the Railway GraphQL API — no dashboard click needed (the GitHub
  app was already authorized for the repo via the demo service). Auto-deploy on push
  to `master` is now active.
- **Env confirmed/repaired:** `ALEA_DATABASE_BACKEND=postgresql` set explicitly;
  `ALEA_DB_*` already wired to `alea-intake-dev-db` (pgvector pg17);
  `ALEA_SKIP_MIGRATIONS=true`.
- **Redeploy:** `serviceConnect` auto-triggered a build from the `master` tip. The
  first build failed (pre-existing Dockerfile frontend bug — pnpm workspace lockfile;
  fixed in commit `fccc395`, see that commit). Subsequent build succeeded.

## Verified

`alea-intake-dev` is GitHub-connected to `master` with auto-deploy on; pushes to
`master` build and deploy automatically (confirmed across the `fccc395`, `dbe8a57`,
and `835b332` pushes). Build success confirmed via the deployments GraphQL query.

Functional verification of the running app is in `14-04-SUMMARY.md` (which also
covers the Postgres-compatibility fixes the deploy then exposed).
