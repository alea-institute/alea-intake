---
phase: 06
slug: legal-research-verification
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-04
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_research*.py tests/test_kb*.py tests/test_citation*.py tests/test_mcp*.py -q --tb=short` |
| **Full suite command** | `.venv/bin/python -m pytest --tb=short -q` |
| **Estimated runtime** | ~30 seconds |

## Sampling Rate

- **After every task commit:** Run quick command (phase-specific tests)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

## Wave 0 Requirements

All test files created inline via TDD tasks within each plan. No separate Wave 0 needed.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CourtListener live API results | RESEARCH-06 | Requires live API key | Configure CourtListener key, search "negligence", verify real results |
| Citation verification against live databases | RESEARCH-07 | Requires live services | Verify a known case citation returns "verified" |
| KB document upload + retrieval | RESEARCH-09 | End-to-end visual | Upload a PDF, search for content, verify relevant chunks returned |

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or inline TDD
- [x] Sampling continuity maintained
- [x] Wave 0 covered by inline TDD
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set

**Approval:** pending
