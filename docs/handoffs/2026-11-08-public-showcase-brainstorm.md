---
topic: public-showcase-brainstorm
---

# Handoff — alea-intake public showcase (PR1 in progress)

## State
- Plan: `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (19 units, 3 PRs).
- Branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1` (pushed). Done and committed: PDF swap + CPU torch (U3, U4 code), tracked `uv.lock`, calibration (U1), BYOK (U5), expansion study (U2, recommends no change), replay harness (U9, recordings pending), guest mode + ownership + limits (U6). Backend suite 1350 passed.
- Image smoke: builds, boots in ~70 s, 645 MiB idle, no nvidia packages. Peak-under-analysis RAM still unmeasured (needs an LLM key).
- In flight: U7 (purge, TTL sweeper, redaction) and U8 (frontend showcase flow) as Codex workers in `~/worktrees/alea-intake-pr1-u7` / `-u8`.

## Next
1. Integrate U7 and U8 (review diffs, full suites, screenshots), then U10 (Coolify deploy behind access gate) and U11 (persona harness on BYOK/guest).
2. Open PR1; then PR2 (rules as data, Minnesota rule set, state scoping, UAT matrix) and PR3 (launch).

## Open with Damien
- Spend: LLM key and budget for live runs — filed as Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget` (hard block). Blocks only live runs.
- Landing-page copy approval gates the PR3 merge.

## Gotchas
- `codex-run.sh` accepts a run only when the worker writes the named out-file; say so in the prompt.
- Codex sandboxes cannot finish SQLite async tests or reach the network; rerun suites in the main checkout.
