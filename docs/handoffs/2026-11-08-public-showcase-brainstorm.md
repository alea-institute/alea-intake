---
topic: public-showcase-brainstorm
---

# Handoff — alea-intake public showcase (PR1 built; review and deploy next)

## State
- Plan: `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md`.
- Branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` (pushed, 13 commits): PDF swap + CPU torch, tracked uv.lock, calibration, BYOK, expansion study, replay harness, guest mode + ownership + limits, retention purge + redaction, frontend showcase flow, persona harness, Dockerfile build args, preview gate + probe + runbook. Backend 1377 passed; frontend 220 passed; Playwright e2e green at 390 and 1280 px (needs a local config pointing at system Chrome: Playwright cannot download browsers on Ubuntu 26.04).
- In flight: a simplification-fix worker (uncommitted changes in the main checkout) that fixes an undefined `admit()` in the showcase WebSocket loop plus reuse/efficiency/comment cleanups. Verify, then commit.
- Live deploy target already exists: Coolify app `alea-intake` on hetzner-dev (`alea-intake.dev.openlegalstandard.org`, auto-deploys `master`). A showcase DB role/database exists on the shared Postgres (isolation verified). Merging PR1 to master deploys publicly, so set the Coolify env and gate first.

## Next
1. Verify and commit the simplification fixes; run `ce-code-review` on the PR1 diff; apply findings; open PR1.
2. With a Coolify write token: set env (showcase mode, build flag, DB settings, preview passphrase), healthcheck, memory limit, domains; deploy PR1 branch behind the gate; `scripts/verify-showcase.sh --mode gated`; merge.
3. Live runs after the LLM-key decision; then PR2 and PR3 per the plan.

## Open with Damien
- Coolify write token (the box token is read-only).
- LLM key and budget for live runs (Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`).
- Landing-page copy approval gates PR3.

## Gotchas
- Background Codex work now must use `agents/worker-wrapper.sh` (global hook enforces). `codex-run.sh` accepts a run only when the worker writes the named out-file.
- Codex sandboxes cannot finish SQLite async tests, bind ports, or reach the network; rerun suites in the main checkout.
