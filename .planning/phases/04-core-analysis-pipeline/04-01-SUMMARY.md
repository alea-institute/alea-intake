---
phase: 04-core-analysis-pipeline
plan: 01
subsystem: database, api
tags: [sqlalchemy, pydantic, analysis-pipeline, convergence, gap-analysis]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: TenantBase, SharedBase, DB engine, OrganizationConfig model
  - phase: 02-folio-ontology-integration
    provides: ConceptResolver, FOLIO IRI matching, adjacency discovery
  - phase: 03-input-narrative-capture
    provides: ExtractedFact model, fact extraction service, intake models
provides:
  - 8 analysis DB models (AnalysisRun, AnalysisIteration, AnalysisStage, AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap, FollowUpQuestion)
  - 15 Pydantic schemas for LLM I/O contracts (orchestrator, issue-spot, fact-map, gap-analyze, question-gen, convergence)
  - OrganizationConfig.analysis_config_json for per-org analysis settings
affects: [04-02, 04-03, 04-04, 04-05, 05-pre-research-exploration, 07-output-export]

# Tech tracking
tech-stack:
  added: []
  patterns: [analysis-stage-models, composite-confidence-scoring, convergence-signal-weights, topic-grouped-questions]

key-files:
  created:
    - backend/app/models/analysis.py
    - backend/app/services/analysis/__init__.py
    - backend/app/services/analysis/schemas.py
    - backend/tests/test_analysis_models.py
    - backend/tests/test_analysis_schemas.py
  modified:
    - backend/app/models/organization.py
    - backend/app/models/__init__.py

key-decisions:
  - "All 8 analysis models inherit TenantBase for tenant-schema isolation (consistent with existing pattern)"
  - "AnalysisClaim.is_potential defaults to False per D-08 (discovered claims surfaced separately)"
  - "FactClaimMapping stores composite confidence with llm/concept/fact sub-scores per D-05"
  - "ConvergenceWeights and ConfidenceWeights default to sum 1.0 with org-configurable overrides"
  - "AnalysisConfig stored as JSON in OrganizationConfig for schema-free org customization"

patterns-established:
  - "Analysis state checkpointing: AnalysisRun -> AnalysisIteration -> AnalysisStage hierarchy for pause/resume"
  - "Composite confidence: three sub-scores (LLM, concept, fact) combined with configurable weights"
  - "Gap taxonomy: four types (unsupported_element, unexplored_claim, weak_mapping, procedural_requirement)"
  - "Topic-grouped questions: FollowUpQuestion.topic_group for consumer-friendly grouping"

requirements-completed: [ANALYSIS-02, ANALYSIS-07, ANALYSIS-09, ANALYSIS-10]

# Metrics
duration: 5min
completed: 2026-04-04
---

# Phase 4 Plan 01: Analysis Data Layer Summary

**8 analysis DB models with TDD, 15 Pydantic LLM I/O schemas, and org-configurable analysis settings via JSON column extension**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-04T15:08:33Z
- **Completed:** 2026-04-04T15:13:53Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- 8 SQLAlchemy analysis models covering the full analysis lifecycle (runs, iterations, stages, claims, elements, mappings, gaps, questions)
- 15 Pydantic schemas defining typed contracts for every LLM call and stage output in the analysis pipeline
- OrganizationConfig extended with analysis_config_json for per-org convergence weights, confidence weights, and auto-trigger settings
- 44 tests total (12 model creation + 32 schema validation) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Analysis DB models and org config extension** - `24da7db` (test) + `9d197e2` (feat) [TDD]
2. **Task 2: Pydantic schemas for LLM I/O and stage contracts** - `aea988f` (feat)

_Note: Task 1 used TDD with separate RED (test) and GREEN (implementation) commits._

## Files Created/Modified
- `backend/app/models/analysis.py` - 8 analysis models: AnalysisRun, AnalysisIteration, AnalysisStage, AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap, FollowUpQuestion
- `backend/app/services/analysis/__init__.py` - Analysis service package init
- `backend/app/services/analysis/schemas.py` - 15 Pydantic schemas for orchestrator, issue-spot, fact-map, gap-analyze, question-gen, convergence, and config
- `backend/app/models/organization.py` - Added analysis_config_json (JSON) column to OrganizationConfig
- `backend/app/models/__init__.py` - Re-exports all 8 new analysis models
- `backend/tests/test_analysis_models.py` - 12 tests for model creation, field defaults, relationships
- `backend/tests/test_analysis_schemas.py` - 32 tests for schema validation, literals, bounds, JSON round-trip

## Decisions Made
- All analysis models inherit TenantBase (consistent with ExtractedFact, Intake, Message patterns)
- AnalysisClaim.is_potential defaults to False per D-08 -- discovered claims explicitly marked
- FactClaimMapping stores composite confidence (overall) plus three sub-scores (llm, concept, fact) per D-05
- ConvergenceWeights defaults: coverage=0.30, confidence_plateau=0.20, iteration_cap=0.10, user_fatigue=0.15, diminishing_gaps=0.25 (sum=1.0)
- ConfidenceWeights defaults: llm=0.4, concept=0.3, fact=0.3 (sum=1.0)
- AnalysisConfig stored as JSON column (not separate table) for flexible schema evolution

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all models and schemas are fully implemented with no placeholder data.

## Next Phase Readiness
- Analysis data layer complete -- Plans 04-02 through 04-05 can build orchestrator, stages, and convergence logic against these models and schemas
- All models registered in TenantBase metadata for automatic table creation in tests and migrations
- Pydantic schemas provide typed contracts for LLM structured output validation

---
*Phase: 04-core-analysis-pipeline*
*Completed: 2026-04-04*
