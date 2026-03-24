---
phase: 3
slug: input-narrative-capture
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/ -x --timeout=30` |
| **Full suite command** | `cd backend && python -m pytest tests/ --timeout=60` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x --timeout=30`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | INGEST-01 | integration | `pytest tests/test_intake_chat.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | INGEST-05 | unit | `pytest tests/test_message_pipeline.py -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | INGEST-02 | unit + integration | `pytest tests/test_asr_service.py tests/test_voice_intake.py -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | INGEST-03 | unit + integration | `pytest tests/test_document_service.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | INGEST-04 | integration | `pytest tests/test_professional_intake.py -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | INGEST-06 | unit + integration | `pytest tests/test_fact_extraction.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_intake_chat.py` — WebSocket chat tests (INGEST-01)
- [ ] `tests/test_asr_service.py` — ASR provider unit tests with mocked providers (INGEST-02)
- [ ] `tests/test_voice_intake.py` — Voice intake integration (INGEST-02)
- [ ] `tests/test_document_service.py` — Document extraction tests with sample PDF/DOCX/image (INGEST-03)
- [ ] `tests/test_professional_intake.py` — Professional mode tests (INGEST-04)
- [ ] `tests/test_message_pipeline.py` — Normalization pipeline tests (INGEST-05)
- [ ] `tests/test_fact_extraction.py` — Fact extraction with mocked LLM (INGEST-06)
- [ ] `tests/fixtures/` — Sample test files: small PDF, DOCX, PNG image, WebM audio

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser audio recording via WebSocket | INGEST-02 | Requires real browser MediaRecorder API | Open chat UI, click record, speak, verify transcript appears |
| Voice transcript review/edit flow | INGEST-02 | Interactive UI flow with user corrections | Record voice, review transcript, make edit, verify corrected text enters pipeline |
| Multi-modal message mixing in session | INGEST-05 | Requires real user switching between text/voice/upload mid-session | Start chat, type message, upload PDF, record voice — all in same session |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
