---
topic: showcase-pr1-fixes
---

# Handoff: alea-intake public showcase, PR1 review fixes in flight

## Goal
Ship PR1 of `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (units U1-U11). The simplification pass is committed (`767906a`). A full `ce-code-review` returned **Not ready**. Two Codex workers are applying its findings. Next: merge their branches, re-verify, open PR1, then do the gated deploy.

## State
- **PR1 open (draft):** https://github.com/alea-institute/alea-intake/pull/3, branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` at `b6dd460`, pushed. Draft on purpose: any merge to master auto-deploys publicly.
- **Review fixes:** four review rounds, all findings fixed with regression tests (round summary in the PR body).
- **Verified at `b6dd460`:**
  - **Backend:** 1483 passed / 3 skipped on two full runs.
  - **Frontend:** 258 vitest tests passed; the build succeeds.
  - **Browser:** the Playwright smoke passed at 390 and 1280 px.
  - **Lint:** ruff clean on changed files (`test_voice_intake.py`'s 9 findings already exist on master).
- **Deploy box disk:** at 87%. Build cache pruned (about 1 GB); no dangling images. The remaining reclaimable space is mostly Coolify's previous app images kept for rollback, left in place on purpose.
- **Unrelated box issue:** a Plausible container has been unhealthy for 3 months (pre-existing, not this work).

## Next
1. **Coolify write token (Damien):** waiting on him. Steps were given inline: create it in Keys & Tokens with read/write/deploy, then save it on the box with the prompting one-liner to `~/.coolify-token-write`.
2. **Gated deploy, once the token exists:**
   - **Coolify config:** set the showcase env vars on app `alea-intake` (names in `docs/DEV-DEPLOY-RUNBOOK.md`, including `ALEA_FORWARDED_ALLOW_IPS`), widen the healthcheck, set a memory limit, and add the `intake.dev.openlegalstandard.org` domain.
   - **Never build on the deploy box:** Damien's rule (relayed by the folio-enrich session, 2026-11-08). Build the image on the home box, ship it with `docker save | ssh <deploy-box> docker load`, and tag it `<app-uuid>:<commit>` so Coolify skips its own build. A home-box build of `e31c880` came out at 2.26 GB, against 10.2 GB for the running pre-PR1 image.
   - **Coolify queue was cleared 2026-11-08:** the folio-enrich session cancelled a stuck deploy and every queued alea-intake deploy, including PR #3's preview deploys. The app still runs its previous image. Redeploy deliberately; nothing will deploy on its own.
   - **Deploy and verify:** deploy the PR1 branch behind the preview gate, run `scripts/verify-showcase.sh --mode gated`, measure peak RAM (the box has 7 GB total, about 1 GB available), and run the retention test against real Postgres.
   - **Ship:** mark PR3 ready and merge.
3. **After the LLM-key decision** (Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`, q1, re-asked inline 2026-11-08): run the live persona campaign, regression recordings, and the reference-model comparison. Then PR2 (deadline rules) per the plan.

## Open with Damien
- **Coolify write token.**
- **LLM key and budget (q1):** a hard block on live runs only.
- **Disk space, possibly:** if the new image pushes disk past 90%, choose between Coolify's image-retention cleanup setting and a larger disk.
- **Landing-page copy (PR3):** draft it in a Claude Doc first.

## Gotchas
- **Earlier gotchas:** everything in `docs/handoffs/2026-11-08-showcase-pr1-review.md` still applies.
- **Codex sandbox:** under `codex-run.sh` it cannot commit (read-only `.git`), so the orchestrator commits those edits. It also cannot finish aiosqlite tests, so rerun suites outside it.
- **Real browser vs mocks:** a regression appeared only in a real browser. Late i18n loads with `useSuspense` suspended the page and aborted analysis. Always run the Playwright smoke after showcase frontend changes.
- **Isolated test runs:** several backend modules fail when run alone without `ALEA_SECRET_KEY`. This predates PR1.
