---
phase: 05-pre-research-exploration-safety
plan: 02
subsystem: analysis
tags: [exploration, llm, folio, asyncio, screening-protocols, tdd]

# Dependency graph
requires:
  - phase: 05-01
    provides: "ScreeningProtocol models, ProtocolService CRUD, TriggerMatcher, ExplorationConfig schemas, seed protocols"
  - phase: 04
    provides: "AnalysisOrchestrator stage loop, IssueSpotStage pattern, AnalysisClaim model, AnalysisStage checkpoints"
  - phase: 02
    provides: "FOLIO adjacency discovery, ConceptResolver for IRI deduplication"
provides:
  - "ExplorationEngine with four-layer hybrid parallel execution and multi-round stability"
  - "ExploreStage integrated into AnalysisOrchestrator between issue_spot and research"
  - "AnalysisClaim persistence for exploration-discovered issues (claim_type='discovered')"
  - "OrchestratorDecision schema accepting 'explore' as valid next_stage"
affects: [06-legal-research, 10-autonomy-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hybrid parallel via asyncio.gather: cheap LLM || sequential FOLIO->protocols->expensive LLM"
    - "Multi-round stability detection with min_rounds/max_rounds/stability_threshold"
    - "FOLIO IRI-based deduplication via ConceptResolver"
    - "Lazy imports to avoid circular dependency with folio package"

key-files:
  created:
    - "backend/app/services/exploration/engine.py"
    - "backend/app/services/exploration/layers.py"
    - "backend/app/services/analysis/stages/explore.py"
    - "backend/tests/test_exploration_engine.py"
    - "backend/tests/test_exploration_stage.py"
  modified:
    - "backend/app/services/analysis/stages/__init__.py"
    - "backend/app/services/analysis/orchestrator.py"
    - "backend/app/services/analysis/schemas.py"

key-decisions:
  - "Lazy imports for folio.adjacency inside layer functions to avoid circular import chain"
  - "ExplorationEngine uses _build_context helper for clean state passing between rounds"
  - "asyncio.gather with return_exceptions=True for graceful degradation on branch failure"
  - "Unresolvable concepts kept with synthetic key to avoid silent data loss"

patterns-established:
  - "Exploration layer pattern: async function returning list[ExplorationResult]"
  - "Stage integration pattern: add to STAGES list, _get_stage_instance, and _execute_stage dispatch"

requirements-completed: [EXPLORE-01, EXPLORE-02, EXPLORE-05, EXPLORE-06, EXPLORE-10]

# Metrics
duration: 11min
completed: 2026-04-04
---

# Phase 5 Plan 02: Three-Layer Exploration Engine and Orchestrator Integration Summary

**ExplorationEngine with four-layer hybrid parallel execution (cheap LLM || FOLIO->protocols->expensive LLM), multi-round stability detection, ConceptResolver deduplication, and ExploreStage integrated between issue_spot and research in the orchestrator pipeline**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-04T17:17:47Z
- **Completed:** 2026-04-04T17:29:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- ExplorationEngine runs four layers in hybrid parallel per D-05: cheap LLM wide-net scan runs concurrently with sequential FOLIO adjacency -> protocol matching -> expensive LLM pipeline via asyncio.gather
- Multi-round stability loop (D-06) respects min_rounds, max_rounds, and stability_threshold from ExplorationConfig, stopping when no new issues found after minimum rounds met
- ExploreStage integrated into AnalysisOrchestrator as the second stage: issue_spot -> explore -> research -> fact_map -> gap_analyze -> question_gen (D-07)
- Discovered issues persisted as AnalysisClaim records with claim_type="discovered" and is_potential=True (EXPLORE-10)
- Deduplication merges results from all layers to FOLIO IRIs via ConceptResolver, keeping highest confidence per IRI

## Task Commits

Each task was committed atomically:

1. **Task 1: ExplorationEngine with four layers, parallel execution, deduplication, and multi-round stability**
   - `e252ed4` (test): add failing tests for ExplorationEngine layers and multi-round stability
   - `aae4249` (feat): implement ExplorationEngine with four layers, parallel execution, and multi-round stability
2. **Task 2: ExploreStage, orchestrator integration, and AnalysisClaim persistence**
   - `a1c8cdd` (test): add failing tests for ExploreStage and orchestrator integration
   - `6a886f0` (feat): implement ExploreStage, orchestrator integration, and AnalysisClaim persistence

## Files Created/Modified
- `backend/app/services/exploration/engine.py` - ExplorationEngine with three-layer parallel execution and multi-round stability
- `backend/app/services/exploration/layers.py` - Four layer implementations: folio_adjacency, protocol_match, cheap_llm, expensive_llm
- `backend/app/services/analysis/stages/explore.py` - ExploreStage following IssueSpotStage pattern for orchestrator integration
- `backend/app/services/analysis/stages/__init__.py` - Added ExploreStage to stage exports
- `backend/app/services/analysis/orchestrator.py` - Updated STAGES list with 'explore' and _get_stage_instance dispatch
- `backend/app/services/analysis/schemas.py` - OrchestratorDecision accepts 'explore' as valid next_stage
- `backend/tests/test_exploration_engine.py` - 17 tests for engine layers, dedup, rounds, degradation
- `backend/tests/test_exploration_stage.py` - 8 tests for ExploreStage, orchestrator integration, schema

## Decisions Made
- **Lazy imports for FOLIO adjacency:** The folio package __init__.py eagerly imports folio-python which may not be installed in all test environments. Layer functions import discover_adjacent_concepts lazily inside the function body to break the circular import chain.
- **asyncio.gather with return_exceptions:** Both parallel branches use return_exceptions=True so that a failure in the cheap LLM branch doesn't block the sequential pipeline (and vice versa). Failed branches return empty lists.
- **Unresolvable concepts preserved:** Results that cannot be resolved to FOLIO IRIs via ConceptResolver are kept with synthetic keys rather than being silently dropped, ensuring no discovered issues are lost.
- **ExplorationEngine._build_context helper:** Clean separation of context building from round execution, making the state passed between rounds explicit and testable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed folio package import chain**
- **Found during:** Task 1 (ExplorationEngine implementation)
- **Issue:** layers.py top-level import of `app.services.folio.adjacency` triggered `folio.__init__` -> `folio_service.py` -> `from folio import FOLIO`, failing when folio-python not installed
- **Fix:** Changed to lazy import inside `layer_folio_adjacency` function body, only importing when folio is not None
- **Files modified:** backend/app/services/exploration/layers.py
- **Verification:** All 25 tests pass without folio-python installed at import time
- **Committed in:** aae4249 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test keyword matching assertion**
- **Found during:** Task 1 (TDD RED phase)
- **Issue:** Test used "abusing" in facts text but keyword "abuse" is not a substring of "abusing" (e vs i)
- **Fix:** Changed test facts text to include "domestic violence" which exactly matches the keyword
- **Files modified:** backend/tests/test_exploration_engine.py
- **Verification:** Protocol match test passes correctly
- **Committed in:** aae4249 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correct test execution. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## Known Stubs
None - all data flows are wired to real implementations (ExplorationEngine -> layers -> ConceptResolver, ExploreStage -> AnalysisClaim persistence).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Exploration engine complete and integrated into orchestrator pipeline
- Plan 05-03 (continuous safety screening middleware) can proceed -- it uses the same ProtocolService and TriggerMatcher from Plan 05-01
- Phase 6 (Legal Research) depends on this exploration stage feeding discovered issues into the research stage

---
*Phase: 05-pre-research-exploration-safety*
*Completed: 2026-04-04*
