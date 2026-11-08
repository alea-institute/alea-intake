---
topic: showcase-pr1-fixes
---

# Handoff — alea-intake showcase: PR1 live behind the preview gate for the 2026-11-09 demo

## Goal
Ship PR1 of `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md`. Tonight's goal was a bulletproof live demo on Monday 2026-11-09 (Damien: live demo, Sonnet 5.5, built-in examples plus a story from the audience; keep a recorded backup).

## State (2026-11-08 night)
- **PR #3 (draft):** branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1`, pushed. Backend 1585 passed / 3 skipped; frontend 278 passed.
- **Deployed:** the Coolify app serves the branch's latest commit on `intake.dev.openlegalstandard.org` and `alea-intake.dev.openlegalstandard.org`, behind the preview passphrase; `intake.damienriehl.com` reaches the same app through Cloudflare Access (Damien-only one-time PIN; the gate trusts the Access JWT). `scripts/verify-showcase.sh --mode gated` passes 19/19 on both domains.
- **Live measurements (Sonnet 5.5):** about $0.23 and 2.5 minutes per intake; three browser rehearsals completed with no errors. Spend so far about $8 of the $25/month ceiling (Cockpit ask `alea-intake-2026-11-08-1051-showcase-llm-key-budget`).
- **Fixed tonight:** Anthropic system prompt and max_tokens, extraction parsing, background `/analyze`, bounded analysis stages, showcase speed caps (1 iteration), third-party log redaction, current model list, dates and memo deadline headings, Access-trusting preview gate, friendly progress stages, shifted example-story dates, deposit probe wording.
- **Coolify state to restore after the demo:** auto-deploy paused, PR preview deployments disabled, app pinned to the PR1 branch commit. `ALEA_DB_HOST` points at the unique alias (see runbook).

## Next
1. After the demo: merge PR1, repoint the app to `master`, re-enable auto-deploy (see `docs/DEV-DEPLOY-RUNBOOK.md`).
2. Move the app to a registry-image build pack so releases never build on the deploy box.
3. Content follow-ups from rehearsals: wage rule for an employee who quits (confirm with Damien whether § 181.14 applies), model-chosen deadline labels ("Injury" for a hospital stay, undated "Incident"), duplicate and filler claims, sparse FOLIO concept chips, no 21-day deposit deadline card, 500 in the console when erasing mid-analysis, the standard mode's per-jurisdiction repeated fact mapping.
4. Example story `landlord-tenant` kept its old dates (no clean offset); rewriting it needs Damien's copy approval.

## Gotchas
- Read `docs/DEV-DEPLOY-RUNBOOK.md` sections "Shipping an image built off the deploy box" and "Box hazards": Coolify deploys and commit-changing restarts rebuild on the box without the showcase flag; two containers share the `postgres` alias; Docker's data disk is separate from `/` and filled to 100% once tonight.
- Workers: Codex timed out tonight; Claude subagents stood in.
