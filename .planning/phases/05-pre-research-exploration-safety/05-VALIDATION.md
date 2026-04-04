---
phase: 05
slug: pre-research-exploration-safety
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-04
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_protocol*.py tests/test_exploration*.py tests/test_screening*.py -q --tb=short` |
| **Full suite command** | `.venv/bin/python -m pytest --tb=short -q` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command (phase-specific tests)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

Plans create test files inline via TDD. No separate Wave 0 needed.

*Existing test infrastructure covers all framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Trauma-informed question framing | EXPLORE-06 | Subjective quality | Review LLM output for sensitivity |
| Safety resource display | EXPLORE-09 | Visual verification | Trigger DV protocol, check resources shown |
| Real-time screening interrupts | EXPLORE-04 | WebSocket timing | Send trigger message, verify immediate alert |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or inline TDD
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered by inline TDD task structure
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
