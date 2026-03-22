---
phase: 1
slug: foundation-security
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | SECURITY-01 | unit | `pytest tests/test_auth.py -x -q` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | SECURITY-02 | unit | `pytest tests/test_rbac.py -x -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 1 | SECURITY-03,04 | unit | `pytest tests/test_encryption.py -x -q` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | SECURITY-05,06 | unit | `pytest tests/test_audit.py -x -q` | ❌ W0 | ⬜ pending |
| 01-05-01 | 05 | 2 | SECURITY-07,08,09 | unit | `pytest tests/test_consent.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (test DB, test client, auth helpers)
- [ ] `tests/test_auth.py` — stubs for SECURITY-01 (JWT auth, registration, login)
- [ ] `tests/test_rbac.py` — stubs for SECURITY-02 (role-based access)
- [ ] `tests/test_encryption.py` — stubs for SECURITY-03, SECURITY-04 (AES-256, TLS)
- [ ] `tests/test_audit.py` — stubs for SECURITY-05, SECURITY-06 (audit logging)
- [ ] `tests/test_consent.py` — stubs for SECURITY-07, SECURITY-08, SECURITY-09 (consent, deletion)
- [ ] `tests/test_tenant.py` — stubs for SECURITY-10 (multi-tenant isolation)
- [ ] `tests/test_llm.py` — stubs for INTEGRATE-04 (LLM training opt-out)
- [ ] `pytest` + `pytest-asyncio` + `httpx` — install test dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TLS enforcement on API traffic | SECURITY-03 | Requires deployed environment with cert | Deploy to staging, verify `curl -I https://` returns valid cert |
| Cloud KMS key rotation | SECURITY-04 | Requires cloud provider access | Rotate key in KMS console, verify app still decrypts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
