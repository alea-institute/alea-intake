---
phase: 02-folio-ontology-integration
plan: 01
subsystem: folio
tags: [folio, owl, ontology, singleton, cache, etag, httpx, lxml, faiss, sentence-transformers]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: TenantBase, SharedBase, Settings, FastAPI lifespan, health endpoint
provides:
  - FOLIO singleton loader with thread-safe hot-swap (get_folio, reload_folio)
  - OWL cache with ETag-based freshness checking (ensure_owl_fresh, get_owl_status, rollback_owl)
  - OWLUpdateManager with background periodic check, idle-wait, and hot-swap
  - Tenant DB models for concept storage (ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConceptRecord)
  - Legal term expansions and branch signal words (LEGAL_TERM_EXPANSIONS, BRANCH_SIGNAL_WORDS)
  - Lifespan integration (startup FOLIO loading + periodic update task)
  - Health endpoint with OWL cache status
  - mock_folio and real_folio test fixtures
affects: [02-02-embedding-concept-resolution, 02-03-adjacency-unmapped-admin, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: [folio-python[search], faiss-cpu, sentence-transformers, lxml]
  patterns: [singleton-with-lock, etag-freshness, atomic-write-rename, idle-wait-hot-swap, run-in-executor-sync-bridge]

key-files:
  created:
    - backend/app/models/folio_concepts.py
    - backend/app/services/folio/__init__.py
    - backend/app/services/folio/folio_service.py
    - backend/app/services/folio/owl_cache.py
    - backend/app/services/folio/owl_updater.py
    - backend/app/services/folio/term_expansions.py
    - backend/tests/test_folio_service.py
    - backend/tests/test_owl_cache.py
    - backend/tests/test_owl_updater.py
  modified:
    - backend/app/config.py
    - backend/app/models/__init__.py
    - backend/app/main.py
    - backend/tests/conftest.py
    - backend/pyproject.toml

key-decisions:
  - "folio_owl_branch defaults to 'main' overriding folio-python's '2.0.0' default"
  - "OWL cache uses standalone cache_dir (./data/folio_cache) not folio-python's ~/.folio/cache"
  - "ensure_owl_fresh returns bool (not raises) for graceful degradation on network errors"
  - "rollback_owl returns bool (not raises) when no previous version exists"
  - "EmbeddingService.rebuild_index call guarded by try/except ImportError for forward compatibility"

patterns-established:
  - "Singleton with threading.Lock: double-checked locking for thread-safe initialization"
  - "ETag-based HTTP freshness: HEAD with If-None-Match header, 304 = up-to-date"
  - "Atomic file write: write .tmp then rename (prevents partial writes)"
  - "Idle-wait hot-swap: asyncio.Event + active_count reference tracking before singleton replacement"
  - "run_in_executor bridge: sync FOLIO/httpx calls wrapped for async lifespan"

requirements-completed: [FOLIO-01]

# Metrics
duration: 9min
completed: 2026-03-24
---

# Phase 2 Plan 01: FOLIO Ontology Loading Infrastructure Summary

**FOLIO singleton with ETag-based OWL cache, idle-wait hot-swap manager, tenant concept DB models, and 35+ legal term expansions**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-24T13:24:57Z
- **Completed:** 2026-03-24T13:34:29Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- FOLIO singleton loads at startup via run_in_executor with thread-safe double-checked locking and hot-swap support
- OWL cache checks GitHub freshness via ETag conditional HTTP requests, downloads only when stale, with atomic write and one-version rollback
- OWLUpdateManager runs periodic background checks (configurable, default 24h) with idle-wait before singleton replacement
- Four tenant DB models ready for concept data storage (ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConceptRecord)
- Health endpoint extended with OWL cache status (cached, etag, last_checked, content_hash)
- 35+ legal term expansions and 13 branch signal word mappings ported from folio-mapper

## Task Commits

Each task was committed atomically:

1. **Task 1: DB models, OWL cache, FOLIO singleton, term expansions, and test fixtures**
   - `d984777` (test) - Failing tests for FOLIO service, OWL cache, term expansions, DB models
   - `8976d19` (feat) - Implementation: DB models, OWL cache, singleton, term expansions, test fixtures
2. **Task 2: OWL update manager, lifespan integration, and health endpoint extension**
   - `113d0e8` (test) - Failing tests for OWL update manager, lifespan, health endpoint
   - `cbfa830` (feat) - Implementation: OWLUpdateManager, lifespan integration, health endpoint

## Files Created/Modified
- `backend/app/models/folio_concepts.py` - ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConceptRecord tenant models
- `backend/app/services/folio/__init__.py` - Re-exports for FOLIO service functions
- `backend/app/services/folio/folio_service.py` - FOLIO singleton with get_folio, reload_folio, reset_folio
- `backend/app/services/folio/owl_cache.py` - ETag-based OWL cache with ensure_owl_fresh, get_owl_status, rollback_owl
- `backend/app/services/folio/owl_updater.py` - OWLUpdateManager with idle-wait hot-swap and periodic background check
- `backend/app/services/folio/term_expansions.py` - LEGAL_TERM_EXPANSIONS (35+), BRANCH_SIGNAL_WORDS (13), expand_legal_terms, get_branch_signals
- `backend/app/config.py` - Added folio_owl_branch, folio_update_interval_hours, folio_cache_dir, folio_confidence_threshold, folio_traversal_depth
- `backend/app/models/__init__.py` - Added FOLIO concept model imports
- `backend/app/main.py` - Lifespan: ensure_owl_fresh + get_folio + periodic update task; health endpoint with OWL status
- `backend/tests/conftest.py` - mock_folio and real_folio fixtures
- `backend/tests/test_folio_service.py` - Tests for singleton, term expansions, settings, DB models
- `backend/tests/test_owl_cache.py` - Tests for ensure_owl_fresh, get_owl_status, rollback_owl
- `backend/tests/test_owl_updater.py` - Tests for OWLUpdateManager, check_and_update, health endpoint, lifespan
- `backend/pyproject.toml` - Added folio-python[search], faiss-cpu, sentence-transformers, lxml

## Decisions Made
- **folio_owl_branch="main":** Overrides folio-python's default of "2.0.0" per CONTEXT.md decision
- **Standalone cache directory:** Uses `./data/folio_cache` instead of folio-python's `~/.folio/cache` for explicit control
- **Graceful degradation:** ensure_owl_fresh returns False (no exception) on network errors, allowing app to start with stale cache
- **rollback_owl returns bool:** Returns False when no previous version exists instead of raising, enabling safe calling
- **Forward-compatible embedding rebuild:** EmbeddingService.rebuild_index call guarded by ImportError catch since Plan 02-02 creates that service

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- FOLIO singleton loaded and accessible via get_folio()
- OWL cache with freshness checking operational
- OWLUpdateManager ready for idle-wait hot-swap
- Term expansions ready for concept resolution pipeline (Plan 02-02)
- Tenant DB models ready for concept data storage
- mock_folio fixture available for all downstream tests
- Empty service directories created for embedding module (Plan 02-02)

## Self-Check: PASSED

All 9 created files verified present. All 4 task commits (d984777, 8976d19, 113d0e8, cbfa830) verified in git log.

---
*Phase: 02-folio-ontology-integration*
*Completed: 2026-03-24*
