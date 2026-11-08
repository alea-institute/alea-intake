---
topic: public-showcase-brainstorm
---

# Handoff — alea-intake public showcase (brainstorm done, planning next)

## State
- Requirements plan committed: `docs/plans/2026-11-08-0337-feat-public-showcase-launch-plan.md`.
- Tests green on master: backend 1281 passed / 3 skipped; frontend 192 passed.
- No live deployment: the Railway dev server was drained 2026-07-26 (returns "Application not found").

## Next
1. Run `ce-plan` on the plan above.
2. Cleanup lane first (R16–R18): adopt calibration q1/q2, run expansion-vocab calibration (q3), and replace PyMuPDF (stale branch `feat/s075.4-pymupdf-to-pdfplumber`).
3. Then the quality lane (50-state cited deadlines, issue completeness), the production stack, and the 8-persona launch campaign.

## Blocker
- Hosting on the ALEA EC2 host needs Mike (SSH allowlist + `intake.` DNS). Damien sends that request; the agent drafts it.
