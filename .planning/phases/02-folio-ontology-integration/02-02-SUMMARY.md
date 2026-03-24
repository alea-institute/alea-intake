---
phase: 02-folio-ontology-integration
plan: 02
subsystem: api
tags: [embeddings, faiss, pgvector, sentence-transformers, concept-resolution, folio, nlp]

# Dependency graph
requires:
  - phase: 02-folio-ontology-integration
    plan: 01
    provides: FOLIO singleton loader, term expansions, ConceptMapping model, OWL cache
provides:
  - EmbeddingService with dual-backend abstraction (pgvector/FAISS)
  - FAISSBackend for SQLite mode (cosine via IndexFlatIP on normalized vectors)
  - PgVectorBackend for PostgreSQL mode (cosine distance operator)
  - LocalEmbeddingProvider wrapping sentence-transformers all-MiniLM-L6-v2
  - Multi-stage concept resolution pipeline (embedding -> label/prefix -> LLM)
  - Combined confidence scoring with configurable weights
  - persist_resolutions for ConceptMapping DB persistence
affects: [03-concept-graph, 04-intake-workflow, 06-research-tools]

# Tech tracking
tech-stack:
  added: [faiss-cpu, sentence-transformers, all-MiniLM-L6-v2]
  patterns: [dual-backend-abstraction, multi-stage-pipeline, singleton-service, protocol-based-backends]

key-files:
  created:
    - backend/app/services/embedding/service.py
    - backend/app/services/embedding/backends/__init__.py
    - backend/app/services/embedding/backends/faiss_backend.py
    - backend/app/services/embedding/backends/pgvector_backend.py
    - backend/app/services/embedding/providers/__init__.py
    - backend/app/services/embedding/providers/local.py
    - backend/app/services/embedding/providers/cloud.py
    - backend/app/services/folio/concept_resolver.py
    - backend/tests/test_embedding_service.py
    - backend/tests/test_concept_resolver.py
  modified:
    - backend/app/main.py
    - backend/app/services/embedding/__init__.py
    - backend/pyproject.toml

key-decisions:
  - "FAISSBackend uses IndexFlatIP on L2-normalized vectors for cosine similarity (not IndexFlatL2)"
  - "EmbeddingService is a process-wide singleton with double-checked locking (matches FOLIO loader pattern)"
  - "build_index runs synchronously in executor; encodes all 18k+ FOLIO labels in batches of 256"
  - "Concept resolution weights: embedding=0.3, label=0.3, LLM=0.4; single-stage penalty=0.7"
  - "High-confidence embedding match (>0.85) skips LLM stage to save cost and latency"
  - "Branch determination walks sub_class_of hierarchy upward to find known branch roots"
  - "Lifespan calls build_index(folio) between FOLIO load and periodic updater start"
  - "pytest 'slow' marker registered for sentence-transformers tests (skipped in standard CI)"

patterns-established:
  - "Protocol-based backends: EmbeddingBackend protocol allows swapping FAISS/pgvector without code changes"
  - "Multi-stage pipeline: embedding -> label/prefix -> LLM with early exit on high confidence"
  - "Score normalization: all stage scores normalized to 0.0-1.0 before weighted combination"

requirements-completed: [FOLIO-02, FOLIO-03, FOLIO-04, FOLIO-05]

# Metrics
duration: 10min
completed: 2026-03-24
---

# Phase 2 Plan 02: Embedding Service and Concept Resolution Summary

**Dual-backend embedding service (FAISS/pgvector) with three-stage concept resolution pipeline mapping consumer text to FOLIO IRIs via embedding similarity, label matching, and LLM semantics**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-24T13:38:15Z
- **Completed:** 2026-03-24T13:49:12Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- EmbeddingService with dual-backend abstraction: FAISS for SQLite mode, pgvector for PostgreSQL
- Multi-stage concept resolution pipeline that maps consumer narratives to FOLIO concept IRIs
- Domain-aware term expansions integrated for query enrichment before resolution
- Combined confidence scoring with configurable weights and threshold filtering
- Lifespan updated to build embedding index at startup for populated search

## Task Commits

Each task was committed atomically:

1. **Task 1: Embedding service with dual-backend abstraction**
   - `d35c860` (test): add failing tests for embedding service
   - `a24841d` (feat): implement embedding service with dual-backend abstraction
2. **Task 2: Multi-stage concept resolution pipeline**
   - `2d40d66` (test): add failing tests for concept resolution pipeline
   - `bea5870` (feat): implement multi-stage concept resolution pipeline

## Files Created/Modified
- `backend/app/services/embedding/service.py` - EmbeddingService singleton with build_index, search, rebuild_index
- `backend/app/services/embedding/backends/__init__.py` - EmbeddingBackend protocol and SearchResult dataclass
- `backend/app/services/embedding/backends/faiss_backend.py` - FAISS in-memory backend (IndexFlatIP, cosine via normalized IP)
- `backend/app/services/embedding/backends/pgvector_backend.py` - PostgreSQL pgvector backend (cosine distance <=>)
- `backend/app/services/embedding/providers/__init__.py` - EmbeddingProvider protocol
- `backend/app/services/embedding/providers/local.py` - LocalEmbeddingProvider (sentence-transformers all-MiniLM-L6-v2)
- `backend/app/services/embedding/providers/cloud.py` - CloudEmbeddingProvider stub for OpenAI
- `backend/app/services/folio/concept_resolver.py` - Multi-stage pipeline with resolve_concepts and persist_resolutions
- `backend/tests/test_embedding_service.py` - 11 embedding tests (FAISS, pgvector, service, lifespan)
- `backend/tests/test_concept_resolver.py` - 13 concept resolver tests (pipeline, scoring, persistence)
- `backend/app/main.py` - Lifespan updated with embedding index build step
- `backend/app/services/embedding/__init__.py` - Package exports
- `backend/pyproject.toml` - Registered pytest 'slow' marker

## Decisions Made
- FAISSBackend uses IndexFlatIP on normalized vectors (not IndexFlatL2) for cosine similarity
- EmbeddingService singleton with double-checked locking matches FOLIO loader pattern
- Score combination weights: embedding=0.3, label=0.3, LLM=0.4 with 0.7 penalty for single-stage matches
- High-confidence embedding (>0.85) skips LLM stage to save cost
- Lifespan embedding build placed between FOLIO load and periodic updater

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed owl_updater lifespan test for new build_index step**
- **Found during:** Task 1
- **Issue:** test_lifespan_calls_folio_startup didn't mock EmbeddingService, causing PostgreSQL connection attempt
- **Fix:** Added EmbeddingService mock and _periodic_owl_check coroutine mock to test
- **Files modified:** backend/tests/test_owl_updater.py
- **Verification:** Test passes with mocked embedding service
- **Committed in:** a24841d (Task 1 commit)

**2. [Rule 1 - Bug] Fixed get_folio call count assertion in owl_updater test**
- **Found during:** Task 1
- **Issue:** Lifespan now calls get_folio twice (executor load + instance retrieval); test expected once
- **Fix:** Changed assert from assert_called_once to assert call_count == 2
- **Files modified:** backend/tests/test_owl_updater.py
- **Committed in:** a24841d (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs from lifespan changes)
**Impact on plan:** Both fixes necessary for test compatibility with new lifespan steps. No scope creep.

## Issues Encountered
- External tool repeatedly added `folio_admin` router import to main.py during execution (from parallel Plan 02-03); resolved by writing definitive main.py without the premature import

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Embedding service ready for concept graph traversal (Plan 02-03)
- resolve_concepts pipeline ready for intake workflow integration (Phase 4)
- EmbeddingService.rebuild_index ready for OWLUpdateManager callback
- persist_resolutions ready for intake processing pipeline

## Self-Check: PASSED

All 10 created files verified present. All 4 task commits verified in git log.

---
*Phase: 02-folio-ontology-integration*
*Completed: 2026-03-24*
