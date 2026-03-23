---
phase: 02
slug: folio-ontology-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.24.x |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds (unit), ~45 seconds (integration with cached FOLIO) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | FOLIO-01 | integration | `pytest tests/test_folio_service.py::test_folio_loads -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | FOLIO-01 | unit | `pytest tests/test_owl_cache.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | FOLIO-01 | unit | `pytest tests/test_owl_updater.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | FOLIO-02 | integration | `pytest tests/test_concept_resolver.py::test_resolve_objectives -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | FOLIO-03 | integration | `pytest tests/test_concept_resolver.py::test_resolve_areas_of_law -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | FOLIO-04 | integration | `pytest tests/test_concept_resolver.py::test_resolve_legal_authorities -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 2 | FOLIO-05 | integration | `pytest tests/test_concept_resolver.py::test_resolve_jurisdictions -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | FOLIO-06 | unit | `pytest tests/test_unmapped.py -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | FOLIO-07 | integration | `pytest tests/test_adjacency.py -x` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 2 | FOLIO-07 | integration | `pytest tests/test_concept_graph.py -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | - | unit | `pytest tests/test_embedding_service.py -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 3 | - | integration | `pytest tests/test_folio_admin.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_folio_service.py` — stubs for FOLIO-01 (loading, singleton, IRI access)
- [ ] `tests/test_owl_cache.py` — stubs for FOLIO-01 (freshness check, download, rollback)
- [ ] `tests/test_owl_updater.py` — stubs for FOLIO-01 (background update, hot-swap, idle-wait)
- [ ] `tests/test_concept_resolver.py` — stubs for FOLIO-02, FOLIO-03, FOLIO-04, FOLIO-05 (multi-stage pipeline)
- [ ] `tests/test_unmapped.py` — stubs for FOLIO-06 (unmapped handling, local IRI generation)
- [ ] `tests/test_adjacency.py` — stubs for FOLIO-07 (hierarchy + property traversal)
- [ ] `tests/test_concept_graph.py` — stubs for FOLIO-07 (graph node/edge persistence)
- [ ] `tests/test_embedding_service.py` — stubs for embedding dual-backend abstraction
- [ ] `tests/test_folio_admin.py` — stubs for admin API endpoints
- [ ] `tests/conftest.py` additions — FOLIO mock fixture (`mock_folio`), embedding service mock fixture, `real_folio` integration fixture

**Testing strategy:** Full FOLIO ontology requires ~18MB download and 3-5s parse. Unit tests use `mock_folio` (small subset, 10-20 classes, no network). Integration tests use `@pytest.mark.integration` marker with `real_folio` fixture (cached, network on first run).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hot-reload under load | FOLIO-01 | Requires concurrent active analyses during OWL swap | Start 2+ concurrent analyses, trigger OWL update, verify no errors and swap completes after analyses finish |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
