---
phase: 04
slug: core-analysis-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Quick run command** | `.venv/bin/python -m pytest tests/test_analysis*.py -q --tb=short` |
| **Full suite command** | `.venv/bin/python -m pytest --tb=short -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_analysis*.py -q --tb=short`
- **After every plan wave:** Run `.venv/bin/python -m pytest --tb=short -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | ANALYSIS-01, ANALYSIS-09 | unit+integration | `pytest tests/test_analysis_loop.py` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | ANALYSIS-10 | unit | `pytest tests/test_analysis_audit.py` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | ANALYSIS-02, ANALYSIS-08 | unit | `pytest tests/test_claim_mapping.py` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | ANALYSIS-03, ANALYSIS-04, ANALYSIS-05 | unit | `pytest tests/test_gap_analysis.py` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | ANALYSIS-06, ANALYSIS-07 | unit | `pytest tests/test_convergence.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analysis_loop.py` — stubs for analysis orchestrator loop
- [ ] `tests/test_claim_mapping.py` — stubs for fact-to-claim mapping
- [ ] `tests/test_gap_analysis.py` — stubs for gap detection and question generation
- [ ] `tests/test_convergence.py` — stubs for convergence evaluator
- [ ] `tests/test_analysis_audit.py` — stubs for audit trail

*Existing test infrastructure (pytest-asyncio, conftest.py, aiosqlite fixtures) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Follow-up questions read naturally | ANALYSIS-04 | Subjective quality | Review LLM output for consumer-friendliness |
| Progress indicator updates in real-time | ANALYSIS-01 | WebSocket visual | Open browser, trigger analysis, watch progress |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
