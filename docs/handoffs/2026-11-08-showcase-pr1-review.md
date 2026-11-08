---
topic: showcase-pr1-review
---

# Handoff — alea-intake public showcase: finish PR1 (simplify, review, gated deploy)

## Goal
Ship PR1 of `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (units U1–U11): verify the pending simplification fixes, run `ce-code-review`, open PR1, then deploy behind the preview gate when access arrives. Continue with `ce-work` on that plan.

## State
- Branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` (pushed). Committed: PDF swap + CPU-only torch, tracked `backend/uv.lock`, calibration (0.85/0.55 + floor), expansion-vocabulary study (no change), request-scoped BYOK, regression replay harness, guest mode with ownership checks and abuse limits, session purge + redaction, frontend showcase flow, persona harness, Dockerfile build args, preview gate + `scripts/verify-showcase.sh` + Coolify runbook.
- Last verified: backend 1377 passed / 3 skipped; frontend vitest 220 passed; Playwright smoke green at 390 and 1280 px with zero axe violations.
- **Uncommitted in the working tree:** a simplification-fix pass (report at `.codex-out/simp.md`). It must fix an undefined `admit()` call in the showcase WebSocket loop in `backend/app/routers/intake.py` (first chat message would crash) and add a showcase WebSocket `text_message` test, plus reuse/efficiency/comment/lint cleanups. Read the report, rerun the full backend suite, `cd frontend && npx vitest run && npm run build`, the Playwright smoke, and ruff on changed files; then commit path-limited (never stage `.codex-out/`, `.claude/RESUME.md`, `.codex/`).

## Next
1. Verify and commit the simplification pass (above).
2. Run `ce-code-review` on the PR1 diff (`base:origin/master`, `plan:` the plan, `plan_group:PR1`); apply justified findings; open PR1 with `ce-commit-push-pr`.
3. Deploy (needs Damien's Coolify write token): the existing Coolify app `alea-intake` auto-deploys `master`, so set its showcase env first (names in `docs/DEV-DEPLOY-RUNBOOK.md`), widen the healthcheck, set a memory limit, add the `intake.dev.openlegalstandard.org` domain, deploy the PR1 branch behind the preview gate, run `scripts/verify-showcase.sh --mode gated`, then merge.
4. After the LLM-key decision: live persona campaign, regression recordings, reference-model comparison, peak-memory measurement. Then PR2 and PR3 per the plan.

## Open with Damien
- Coolify **write** token (the one on the deploy box is read-only).
- Spend: which LLM key and budget fund live runs (Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`).
- Landing-page copy approval gates the PR3 merge.

## Gotchas
- Background Codex work must use the cockpit `agents/worker-wrapper.sh` from a worktree under `~/worktrees/` (a global hook blocks other background launches). Give background Claude subagents a time budget and a fallback timer.
- Codex sandboxes cannot finish SQLite async tests, bind ports, or reach the network; rerun suites in the main checkout.
- Playwright cannot download browsers on this OS; run the smoke with a local, uncommitted config pointing `executablePath` at the system Chrome (`/usr/bin/google-chrome`, headless, no-sandbox).
- The shared Postgres on the deploy box was down 12 days after a disk-full crash and was restarted 2026-11-08; keep disk under 85%.
