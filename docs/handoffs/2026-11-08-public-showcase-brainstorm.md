---
topic: public-showcase-brainstorm
---

# Handoff — alea-intake public showcase (plan done, ce-work starting)

## State
- Implementation-ready plan: `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md` (19 units, 3 PRs; reviewed by 6 Claude reviewers plus a Codex cross-model pass; 24 fixes applied).
- Tests green on master before work: backend 1281 passed / 3 skipped; frontend 192 passed.
- No live deployment yet; Railway was drained 2026-07-26.

## Next
1. `ce-work` on PR1 (U1–U11): cleanup, CPU image, BYOK, guest mode with ownership checks, retention purge, frontend flow, regression replay, Coolify deploy behind an access gate, persona harness.
2. PR2 (U12–U16) and PR3 (U17–U19) follow per the plan.

## Open with Damien
- Spend: which LLM key and budget fund live persona runs and UAT. Blocks only live runs.
- Landing-page copy approval (Claude Doc) gates the PR3 merge.
