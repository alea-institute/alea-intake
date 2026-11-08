---
topic: showcase-pr1-fixes
---

# Handoff: alea-intake public showcase, PR1 review fixes in flight

## Goal
Ship PR1 of `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (units U1-U11). The simplification pass is committed (`767906a`). A full `ce-code-review` returned **Not ready**. Two Codex workers are applying its findings. Next: merge their branches, re-verify, open PR1, then do the gated deploy.

## State
- **Branch (pushed):** `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` at `3fa443a`.
- **Round-1 fixes merged.** They close the first review's findings: IDOR identifiers, transcript scoping, standard-mode socket, the per-guest lock, log privacy, corrupt PDF, test isolation, sweeper resilience, proxy headers, and the frontend erase, polling, timeout, keepalive, and Suspense issues.
  - **Real-browser fix:** a regression appeared only in a real browser. Late i18n loads suspended the page and aborted analysis. Local Suspense boundaries now prevent it.
- **Verified at `3fa443a`:**
  - **Backend:** 1416 passed / 3 skipped.
  - **Frontend:** vitest 233 passed; the build succeeded.
  - **Browser:** the Playwright smoke passed, and the 390 px and 1280 px screenshots were inspected.
- **Re-review of the fix round: Not ready.**
  - **#1 P0:** Content-Type case and `+json` variants bypass the body ownership checks in `backend/app/showcase.py`.
  - **#2 P1:** local erase waits on a slow server erase.
  - **#3 P2:** erase queues behind an inline analysis holding the guest lock.
  - **#4 P2:** a timeout retry duplicates the narrative.
  - **#5 P2:** `persona_run` passes on a timed-out narrative.
  - **Pre-existing P1:** the standard-mode socket has no session-ownership check.
- **Decisions (best practice, made by the agent):**
  - **Erase preempts:** erase cancels in-flight guest tasks through a per-guest registry.
  - **Local wipe first:** the browser wipes local data first, then sends a 10 s bounded server erase.
  - **Completion contract:** delivery means `message_ack`, shared by the browser and `persona_run`.
- **Round-2 workers:** branches `fix/pr1-review2-backend` and `fix/pr1-review2-frontend`. Task specs: cockpit `agents/tasks/alea-intake-pr1-fix2-{backend,frontend}.md`.

## Next
1. **Merge:** merge the round-2 branches into the PR1 branch.
2. **Verify:** rerun the full backend suite, vitest, the build, ruff, and the Playwright smoke at 390 and 1280 px.
3. **Re-review:** run a focused re-review of the round-2 commits.
4. **Ship:** open PR1 with `ce-commit-push-pr`.
5. **Deploy:** run the gated deploy once the Coolify write token arrives (`docs/DEV-DEPLOY-RUNBOOK.md`, including `ALEA_FORWARDED_ALLOW_IPS`; `scripts/verify-showcase.sh --mode gated`).

## Open with Damien
- **Coolify write token.**
- **LLM key and budget:** Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`.
- **Landing-page copy approval:** gates PR3.

## Gotchas
- **Earlier gotchas:** everything in `docs/handoffs/2026-11-08-showcase-pr1-review.md` still applies.
- **Worktree symlinks:** the worker worktrees symlink `backend/.venv` and `frontend/node_modules`. Never stage those symlinks, and remove the worktrees after merging.
- **Codex sandbox:** it cannot commit when the repo's `.git` is mounted read-only under synchronous `codex-run.sh`, so the orchestrator commits those edits. It also cannot finish aiosqlite tests, so rerun suites outside it.
- **Isolated test runs:** several backend modules fail when run alone without `ALEA_SECRET_KEY`. This predates PR1; the full suite sets it through import order.
