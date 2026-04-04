---
phase: 04-core-analysis-pipeline
plan: 02
subsystem: analysis
tags: [convergence, confidence-scoring, weighted-signals, hysteresis, pure-functions]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: project scaffolding and test harness
provides:
  - ConvergenceEvaluator with five weighted signals and hysteresis
  - compute_composite_confidence with org-configurable weights
  - ConvergenceWeights, ConvergenceSignals, ConfidenceWeights dataclasses
affects: [04-core-analysis-pipeline, 05-pre-research-exploration]

# Tech tracking
tech-stack:
  added: []
  patterns: [pure-function analysis modules, dataclass-based configuration, hysteresis state tracking]

key-files:
  created:
    - backend/app/services/analysis/__init__.py
    - backend/app/services/analysis/schemas.py
    - backend/app/services/analysis/convergence.py
    - backend/app/services/analysis/scoring.py
    - backend/tests/test_convergence.py
    - backend/tests/test_scoring.py
  modified: []

key-decisions:
  - "Hysteresis uses instance state (_previously_converged) for sticky convergence"
  - "Schemas defined in shared schemas.py for Plan 01 compatibility (not inline)"
  - "Clamping on composite confidence handles edge cases with non-standard weights"

patterns-established:
  - "Pure-function analysis modules: stateless scoring, stateful evaluator with clear API"
  - "Dataclass configuration: ConvergenceWeights/ConfidenceWeights as lightweight config objects"
  - "from_org_config pattern: classmethod to create configured instances from org dict"

requirements-completed: [ANALYSIS-06, ANALYSIS-07]

# Metrics
duration: 5min
completed: 2026-04-04
---

# Phase 4 Plan 02: Convergence Evaluator and Composite Confidence Scoring Summary

**Multi-signal convergence evaluator with five weighted signals, hysteresis anti-oscillation, and composite confidence scoring with org-configurable weights**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-04T15:08:07Z
- **Completed:** 2026-04-04T15:13:00Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments
- ConvergenceEvaluator implements five weighted signals (coverage, confidence plateau, iteration cap, user fatigue, diminishing gaps) with hard cap always-terminate and hysteresis sticky convergence
- compute_composite_confidence combines LLM, concept, and fact confidence with weighted sum, clamping, and org-configurable weights
- Shared schemas.py provides ConvergenceWeights, ConvergenceSignals, and ConfidenceWeights dataclasses used across the analysis pipeline
- 33 total tests (14 convergence + 19 scoring) covering all signal combinations, edge cases, and org config overrides

## Task Commits

Each task was committed atomically:

1. **Task 1: Convergence evaluator with five weighted signals and hysteresis** - `18d8cf5` (test+feat)
2. **Task 2: Composite confidence scoring** - `af3fe79` (feat)

_TDD approach: tests written first (RED), then implementation (GREEN)_

## Files Created/Modified
- `backend/app/services/analysis/__init__.py` - Analysis service package init
- `backend/app/services/analysis/schemas.py` - Shared dataclasses (ConvergenceWeights, ConvergenceSignals, ConfidenceWeights)
- `backend/app/services/analysis/convergence.py` - ConvergenceEvaluator with evaluate() and from_org_config()
- `backend/app/services/analysis/scoring.py` - compute_composite_confidence() and get_confidence_weights()
- `backend/tests/test_convergence.py` - 14 tests for convergence evaluator
- `backend/tests/test_scoring.py` - 19 tests for confidence scoring

## Decisions Made
- **Hysteresis via instance state:** ConvergenceEvaluator tracks `_previously_converged` to lower the effective threshold after convergence, preventing oscillation. Margin of 0.1 means a converged state requires a 0.1+ drop to un-converge.
- **Shared schemas.py:** Rather than defining dataclasses inline in convergence.py and scoring.py, created a shared schemas.py that Plan 01 can extend with Pydantic models. This avoids duplication and establishes the canonical location.
- **Clamping on composite confidence:** `compute_composite_confidence` clamps output to [0.0, 1.0] to handle edge cases where custom weights sum to > 1.0 or inputs are negative.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- convergence.py and scoring.py are pure-logic modules ready for Plan 03 (fact-mapping) and Plan 05 (pipeline orchestrator)
- schemas.py provides the shared dataclass definitions Plan 01 may extend with additional Pydantic schemas
- Both modules are independently testable with no DB or network dependencies

---
*Phase: 04-core-analysis-pipeline*
*Completed: 2026-04-04*
