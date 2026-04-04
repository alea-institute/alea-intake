---
phase: 04
slug: core-analysis-pipeline
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-03
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_analysis*.py tests/test_convergence.py tests/test_scoring.py tests/test_gap_analysis.py -q --tb=short` |
| **Full suite command** | `.venv/bin/python -m pytest --tb=short -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command (phase-specific tests)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 04-01-01 | 01 | 1 | ANALYSIS-02, ANALYSIS-09, ANALYSIS-10 | unit | `pytest tests/test_analysis_models.py` | ⬜ pending |
| 04-01-02 | 01 | 1 | ANALYSIS-07 | unit | `pytest tests/test_analysis_schemas.py` | ⬜ pending |
| 04-02-01 | 02 | 1 | ANALYSIS-06, ANALYSIS-07 | unit | `pytest tests/test_convergence.py` | ⬜ pending |
| 04-02-02 | 02 | 1 | ANALYSIS-02 | unit | `pytest tests/test_scoring.py` | ⬜ pending |
| 04-03-01 | 03 | 2 | ANALYSIS-01, ANALYSIS-02, ANALYSIS-08 | unit | `pytest tests/test_analysis_stages.py` | ⬜ pending |
| 04-04-01 | 04 | 2 | ANALYSIS-03, ANALYSIS-04, ANALYSIS-05 | unit | `pytest tests/test_gap_analysis.py` | ⬜ pending |
| 04-05-01 | 05 | 3 | ANALYSIS-01, ANALYSIS-08, ANALYSIS-09, ANALYSIS-10 | integration | `pytest tests/test_analysis_orchestrator.py` | ⬜ pending |
| 04-05-02 | 05 | 3 | ANALYSIS-01 | unit | `pytest tests/test_analysis_trigger.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Plans 01-04 create test files via TDD (test-first commits). Plan 05 also creates its own test files. No separate Wave 0 needed — all test files are created inline by plan tasks.

*Existing infrastructure (pytest-asyncio, conftest.py, aiosqlite fixtures) covers all framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Follow-up questions read naturally | ANALYSIS-04 | Subjective quality | Review LLM output for consumer-friendliness |
| Progress indicator updates in real-time | ANALYSIS-01 | WebSocket visual | Open browser, trigger analysis, watch progress |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or inline TDD
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered by inline TDD task structure
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
