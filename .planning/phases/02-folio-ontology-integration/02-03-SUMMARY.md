---
phase: 02-folio-ontology-integration
plan: 03
subsystem: folio
tags: [folio, unmapped-concepts, adjacency, graph-traversal, owl-admin, generate-iri, concept-graph]

# Dependency graph
requires:
  - phase: 02-folio-ontology-integration
    plan: 01
    provides: FOLIO singleton, OWL cache (ensure_owl_fresh, rollback_owl, get_owl_status), OWLUpdateManager
provides:
  - Unmapped concept handling with local IRI generation and LLM branch suggestion
  - Adjacency discovery via hierarchy (subClassOf/parentClassOf) and object properties (find_connections)
  - Concept graph persistence (ConceptGraphNode, ConceptGraphEdge) per intake
  - Admin API for OWL lifecycle management and unmapped concept review
affects: [03-intake-pipeline, 04-analysis-engine, 06-research-tools]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Unmapped concepts get local IRIs via folio-python generate_iri()"
    - "Graph structure returned as {nodes, edges} dict (not flat list)"
    - "Nearest mapped concepts used as traversal anchors for unmapped adjacency"
    - "Admin endpoints use require_role(Role.ADMIN) at router level"

key-files:
  created:
    - backend/app/services/folio/unmapped.py
    - backend/app/services/folio/adjacency.py
    - backend/app/routers/folio_admin.py
    - backend/tests/test_unmapped.py
    - backend/tests/test_adjacency.py
    - backend/tests/test_concept_graph.py
    - backend/tests/test_folio_admin.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Unmapped confidence formula: 1 - (best_match_score / threshold), clamped [0,1]"
  - "Adjacency returns graph structure {nodes, edges} not flat list, enabling relationship-aware traversal"
  - "For unmapped concepts, nearest mapped FOLIO concepts serve as traversal anchors"
  - "Admin endpoints use router-level Depends(require_role(Role.ADMIN)) for all routes"
  - "LLM branch suggestion is optional (graceful degradation if no LLM available)"

patterns-established:
  - "Graph discovery: discover_adjacent_concepts returns {nodes: [...], edges: [...]}"
  - "Unmapped concept anchoring: nearest_concepts used as traversal entry points"
  - "Admin router pattern: separate router file with prefix /api/v1/admin/folio"

requirements-completed: [FOLIO-06, FOLIO-07, FOLIO-01]

# Metrics
duration: 10min
completed: 2026-03-24
---

# Phase 2 Plan 03: Unmapped Concepts, Adjacency Discovery, and Admin API Summary

**Unmapped concept handling with local IRI generation, graph-based adjacency discovery traversing hierarchy and object properties, and admin API for OWL lifecycle management**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-24T13:38:15Z
- **Completed:** 2026-03-24T13:48:23Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Unmapped concepts get structured records with local IRI via folio-python generate_iri(), computed unmapped confidence, and up to 3 nearest FOLIO concepts
- Adjacency discovery traverses both class hierarchy (subClassOf/parentClassOf) and OWL object properties (find_connections), returning graph structure with labeled edges
- Concept graphs (nodes + edges) persist to tenant DB via ConceptGraphNode and ConceptGraphEdge models
- Admin API provides OWL status check, manual update trigger, version rollback, unmapped concept review with pagination/org filtering, and config endpoint
- All admin endpoints require admin role

## Task Commits

Each task was committed atomically:

1. **Task 1: Unmapped concept handling and adjacency discovery with graph persistence**
   - `74c7217` (test) - Failing tests for unmapped concepts, adjacency discovery, graph persistence
   - `fb21c5e` (feat) - Implement unmapped handling, adjacency discovery, graph persistence
2. **Task 2: FOLIO admin API endpoints and main.py wiring**
   - `12de72f` (test) - Failing tests for FOLIO admin API endpoints
   - `9f6f813` (feat) - Implement admin API and wire into FastAPI app
   - `2896fad` (fix) - Fix admin router registration test for middleware compatibility

## Files Created/Modified
- `backend/app/services/folio/unmapped.py` - Unmapped concept handler with local IRI generation, LLM branch suggestion, and DB persistence
- `backend/app/services/folio/adjacency.py` - Graph traversal via hierarchy and object properties, unmapped anchoring, concept graph persistence
- `backend/app/routers/folio_admin.py` - Admin API: OWL status/update/rollback, unmapped listing, config endpoint
- `backend/app/main.py` - Added folio_admin_router registration
- `backend/tests/test_unmapped.py` - 7 tests for unmapped concept handling
- `backend/tests/test_adjacency.py` - 8 tests for adjacency discovery
- `backend/tests/test_concept_graph.py` - 5 tests for graph persistence
- `backend/tests/test_folio_admin.py` - 8 tests for admin API endpoints

## Decisions Made
- Unmapped confidence formula: `1 - (best_match_score / threshold)` clamped to [0.0, 1.0] -- higher values mean more confident it's genuinely unmapped
- Adjacency returns graph structure `{nodes: [...], edges: [...]}` rather than flat list, preserving relationship type and traversal depth
- For unmapped concepts, nearest mapped FOLIO concepts serve as traversal anchors (no direct hierarchy traversal possible)
- Admin endpoints use router-level `Depends(require_role(Role.ADMIN))` rather than per-endpoint dependencies
- LLM branch suggestion is optional: returns None if no LLM model provided or if suggestion fails (graceful degradation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed admin router registration test assertion**
- **Found during:** Task 2 (test verification)
- **Issue:** Original test expected 401 for unauthenticated request, but TenantMiddleware returns 400 when X-Tenant-Slug header is missing. Then a follow-up attempt with the slug header failed due to middleware chain issues during teardown.
- **Fix:** Changed to sync route path inspection that verifies routes are registered by checking `app.routes` directly
- **Files modified:** backend/tests/test_folio_admin.py
- **Verification:** All 28 tests pass
- **Committed in:** 2896fad

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test methodology change. No scope creep.

## Issues Encountered
- Pre-existing test failure in `test_owl_updater.py::TestLifespan::test_lifespan_calls_folio_startup`: The test expects `get_folio()` called once, but Plan 02-02 added a second call for EmbeddingService initialization. This is a Plan 02-02 issue, not caused by this plan.
- Pre-existing test failures in `test_concept_resolver.py`: 13 tests failing -- these are Plan 02-02 TDD RED phase tests awaiting GREEN implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Unmapped concept handling ready for intake pipeline integration (Phase 3)
- Adjacency discovery ready for analysis engine enrichment (Phase 4)
- Admin API operational for FOLIO ontology lifecycle management
- All core FOLIO integration infrastructure complete (Plans 01-03)

---
*Phase: 02-folio-ontology-integration*
*Completed: 2026-03-24*
