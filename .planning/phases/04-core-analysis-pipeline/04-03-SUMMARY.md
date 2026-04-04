---
phase: 04-core-analysis-pipeline
plan: 03
subsystem: analysis
tags: [llm, issue-spotting, fact-mapping, folio, concept-resolver, composite-confidence, tdd]

# Dependency graph
requires:
  - phase: 04-01
    provides: "AnalysisClaim, ClaimElement, FactClaimMapping DB models and Pydantic schemas"
  - phase: 04-02
    provides: "compute_composite_confidence scoring function and ConfidenceWeights"
  - phase: 02-02
    provides: "ConceptResolver pipeline for FOLIO IRI matching"
  - phase: 02-03
    provides: "FOLIO adjacency discovery for research stub"
provides:
  - "IssueSpotStage: LLM-driven claim identification with FOLIO IRI resolution"
  - "FactMapStage: many-to-many fact-to-claim-element mapping with composite confidence"
  - "ResearchStubStage: FOLIO-based element discovery placeholder for Phase 6"
affects: [04-04, 04-05, 05-01, 06-01]

# Tech tracking
tech-stack:
  added: []
  patterns: ["lazy import for FOLIO-dependent modules to avoid import chain failures", "stage class pattern with _call_llm method for easy test mocking"]

key-files:
  created:
    - backend/app/services/analysis/stages/__init__.py
    - backend/app/services/analysis/stages/issue_spot.py
    - backend/app/services/analysis/stages/fact_map.py
    - backend/app/services/analysis/stages/research_stub.py
    - backend/tests/test_analysis_stages.py
  modified: []

key-decisions:
  - "Lazy imports for folio-dependent modules to avoid import chain failures when folio library unavailable"
  - "_resolve_folio_iri extracted as mockable method for testability without folio dependency"
  - "concept_confidence defaults to 0.5 when FOLIO unavailable for graceful degradation"
  - "Element satisfaction threshold set at > 0.5 composite confidence"

patterns-established:
  - "Stage class pattern: __init__ with services, _call_llm for mocking, execute for pipeline"
  - "Lazy import pattern for folio-dependent code to enable testing without folio library"

requirements-completed: [ANALYSIS-01, ANALYSIS-02, ANALYSIS-08]

# Metrics
duration: 7min
completed: 2026-04-04
---

# Phase 4 Plan 03: Analysis Stages Summary

**Three analysis stages (issue-spot, fact-map, research-stub) with LLM-driven claim identification, many-to-many composite-confidence mapping, and FOLIO adjacency placeholder**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-04T15:20:16Z
- **Completed:** 2026-04-04T15:27:52Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- IssueSpotStage identifies legal claims from facts via LLM, resolves FOLIO IRIs via ConceptResolver, persists AnalysisClaim/ClaimElement records, detects multiple jurisdictions (D-06), marks discovered claims as potential (D-08)
- FactMapStage creates many-to-many FactClaimMapping records with composite confidence scoring (D-05), tracks unmapped facts, updates ClaimElement satisfaction
- ResearchStubStage provides FOLIO adjacency-based element discovery as placeholder for Phase 6 full research
- 16 tests with mocked LLM covering all stage behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Issue-spotting and research stub stages** - `7b91e43` (feat)
2. **Task 2: Fact-mapping stage with composite confidence** - `6f6c475` (feat)

_Note: TDD tasks -- tests written first (RED), implementation second (GREEN)._

## Files Created/Modified
- `backend/app/services/analysis/stages/__init__.py` - Package init exporting all three stages
- `backend/app/services/analysis/stages/issue_spot.py` - IssueSpotStage with LLM-driven claim identification
- `backend/app/services/analysis/stages/fact_map.py` - FactMapStage with composite confidence scoring
- `backend/app/services/analysis/stages/research_stub.py` - ResearchStubStage using FOLIO adjacency
- `backend/tests/test_analysis_stages.py` - 16 tests covering all stage behaviors

## Decisions Made
- Lazy imports for folio-dependent modules: `resolve_concepts` and `discover_adjacent_concepts` imported inside methods, not at module level, to avoid import chain failures when the `folio` library is not installed
- Extracted `_resolve_folio_iri` as a separate mockable method on IssueSpotStage for testability without the folio dependency
- Default concept_confidence of 0.5 when FOLIO unavailable, ensuring graceful degradation in composite scoring
- Element satisfaction threshold of > 0.5 composite confidence for marking ClaimElement.is_satisfied

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed import chain failure from folio module**
- **Found during:** Task 1 (IssueSpotStage implementation)
- **Issue:** Module-level import of `resolve_concepts` triggered `from folio import FOLIO` chain, which fails when folio-python is not installed in the test environment
- **Fix:** Changed to lazy imports inside method bodies; extracted `_resolve_folio_iri` as mockable method
- **Files modified:** `backend/app/services/analysis/stages/issue_spot.py`, `backend/app/services/analysis/stages/research_stub.py`
- **Verification:** All 16 tests pass without folio-python installed
- **Committed in:** 7b91e43 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for test execution without folio library. No scope creep.

## Issues Encountered
None beyond the import chain issue documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all three stages are fully implemented for their defined scope. ResearchStubStage is intentionally a placeholder that Phase 6 will replace with full legal research tool integration.

## Next Phase Readiness
- Three stage classes ready for pipeline orchestration (Plan 04-05)
- Gap analysis and question generation stages (Plan 04-04) can now build on IssueSpotStage and FactMapStage outputs
- All stages are independently testable with mocked LLM

---
*Phase: 04-core-analysis-pipeline*
*Completed: 2026-04-04*
