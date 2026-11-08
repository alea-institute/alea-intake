---
topic: showcase-pr1-fixes
---

# Handoff: alea-intake public showcase, PR1 review fixes in flight

## Goal
Ship PR1 of `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (units U1-U11). The simplification pass is committed (`767906a`). A full `ce-code-review` returned **Not ready**. Two Codex workers are applying its findings. Next: merge their branches, re-verify, open PR1, then do the gated deploy.

## State
- **Branch:** `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` at `767906a` (the simplification pass, not yet pushed).
- **Last verification:** backend 1380 passed / 3 skipped in 3 of 4 full runs. One run failed `tests/test_security_headers.py::test_csp_header_present`, which passes in isolation (an order-dependent flake). Frontend vitest 220 passed and the build passed.
- **Review verdict, Not ready.**
  - **P0 #1:** a query or body `document_id` overrides the ownership check in `backend/app/showcase.py` (IDOR).
  - **P1 #2/#6:** the standard-mode chat socket fails auth, and its messages are dropped unstored.
  - **P1 #3:** a failed or expired erase strands local data (`frontend/src/features/showcase/ShowcasePage.tsx`).
  - **P1 #4:** visitor text reaches logs through interpolated messages.
  - **P1 #5:** erase races in-flight socket writes and leaves orphan messages.
  - **P1 #7:** transcript approve/edit trusts any `recording_id`.
  - **P2:** #9 (test_retention depends on suite order), #10 (`max_iterations` never stops polling), #11 (persona_run exits 0 on failed gates), and #12 (a corrupt PDF returns 500).
- **Decision on #5:** use one per-guest asyncio lock, shared by socket handlers, erase, and the sweeper. This relies on the single-worker assumption. Best practice settles it, so it is not a question for Damien.
- **Fix workers:**
  - **Branch `fix/pr1-review-backend`:** findings #1, #2, #4-#7, #9, #12, plus the CSP flake, sweeper logging, and proxy headers.
  - **Branch `fix/pr1-review-frontend`:** findings #3, #10, #11, plus the sendStory timeout and the idle keepalive.
  - **Task specs:** cockpit `agents/tasks/alea-intake-pr1-fix-{backend,frontend}.md`.

## Next
1. When both workers report `review_ready` or `completed`, inspect each branch's commits and summary.
2. Merge both branches into the PR1 branch.
3. Rerun the full backend suite (outside the Codex sandbox), vitest, the build, ruff, and the Playwright smoke at 390 and 1280 px.
4. Run a focused re-review of the fixes.
5. Push and open PR1 with `ce-commit-push-pr`.
6. Gated deploy, once the Coolify write token arrives: follow `docs/DEV-DEPLOY-RUNBOOK.md`, then run `scripts/verify-showcase.sh --mode gated`. The runbook now also covers `ALEA_FORWARDED_ALLOW_IPS`.

## Open with Damien
- The Coolify write token.
- The LLM key and spend budget (Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`).
- Landing-page copy approval, which gates the PR3 merge.
- Possible product question: standard-mode REST analysis now requires `X-LLM-API-Key`, and the authenticated frontend sends none. Plan AE3 appears to intend this, so it stays a residual note, not an ask.

## Gotchas
- Same as `docs/handoffs/2026-11-08-showcase-pr1-review.md`.
- The worker worktrees symlink `backend/.venv` and `frontend/node_modules` from the main checkout. Never stage those symlinks, and remove the worktrees after merging.
