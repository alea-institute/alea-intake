---
phase: 04-core-analysis-pipeline
plan: 04
subsystem: analysis
tags: [gap-analysis, question-generation, topic-grouping, rationale-transparency, tdd]

# Dependency graph
requires:
  - phase: 04-core-analysis-pipeline
    plan: 01
    provides: AnalysisGap, FollowUpQuestion, AnalysisClaim, ClaimElement, FactClaimMapping models; GapSchema, QuestionGenResult schemas
  - phase: 04-core-analysis-pipeline
    plan: 02
    provides: ConvergenceEvaluator, confidence scoring
provides:
  - GapAnalyzeStage detecting four gap types with priority and coverage calculation
  - QuestionGenStage with topic grouping, rationale transparency, and gap linkage
affects: [04-05-pipeline-orchestrator, 05-pre-research-exploration]

# Tech tracking
tech-stack:
  added: []
  patterns: [stage-pattern-with-execute, gap-signature-deduplication, llm-json-structured-output, transparency-toggle]

key-files:
  created:
    - backend/app/services/analysis/stages/__init__.py
    - backend/app/services/analysis/stages/gap_analyze.py
    - backend/app/services/analysis/stages/question_gen.py
  modified:
    - backend/tests/test_gap_analysis.py

key-decisions:
  - "All existing gaps (addressed and open) included in dedup signature set to prevent re-detection"
  - "Gap priority formula: unsupported_element = claim.confidence * 100, unexplored_claim = 50, weak_mapping = (1-confidence) * 100"
  - "Procedural requirement detection via LLM with graceful fallback (empty list on failure)"
  - "Question transparency is a boolean toggle -- rationale is either fully included or None"
  - "Gap-to-question matching uses description equality with substring fuzzy fallback"

patterns-established:
  - "Stage execute pattern: (run, iteration, domain-specific args) -> dict with metrics"
  - "Gap signature deduplication: (gap_type, claim_id, element_id) tuple set"
  - "LLM structured output: json_async(prompt, schema) -> Pydantic model"

requirements-completed: [ANALYSIS-03, ANALYSIS-04, ANALYSIS-05]

# Metrics
duration: 5min
completed: 2026-04-04
---

# Phase 4 Plan 04: Gap Analysis and Question Generation Summary

**GapAnalyzeStage detecting four gap types with priority/coverage, and QuestionGenStage generating topic-grouped consumer-friendly questions with configurable rationale transparency**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-04T15:19:09Z
- **Completed:** 2026-04-04T15:24:28Z
- **Tasks:** 2
- **Files created:** 3
- **Files modified:** 1

## Accomplishments
- GapAnalyzeStage detects four gap types from analysis state: unsupported_element, unexplored_claim, weak_mapping, procedural_requirement (D-09)
- Gaps prioritized by impact: unsupported elements on high-confidence claims first, with configurable weak_mapping_threshold
- Coverage percentage computed as satisfied_elements / total_elements
- Previously resolved gaps not re-detected via comprehensive signature deduplication
- QuestionGenStage generates consumer-friendly questions grouped by topic (D-10) with priority ranking
- Configurable rationale transparency: when enabled, rationale explains why each question is being asked (D-12)
- All gaps produce at least one question (D-11), with deduplication against previously answered questions
- Both stages persist records to DB (AnalysisGap, FollowUpQuestion) with full traceability
- 17 tests total (9 gap analysis + 8 question generation) all passing via TDD

## Task Commits

Each task was committed atomically:

1. **Task 1: Gap analysis stage with four gap types** - `98d0a3a` (feat, TDD)
2. **Task 2: Question generation stage with topic grouping** - `65ea06e` (feat, TDD)

## Files Created/Modified
- `backend/app/services/analysis/stages/__init__.py` - Package init exporting GapAnalyzeStage and QuestionGenStage
- `backend/app/services/analysis/stages/gap_analyze.py` - GapAnalyzeStage with four gap type detection, priority calculation, coverage computation, LLM procedural gap detection
- `backend/app/services/analysis/stages/question_gen.py` - QuestionGenStage with topic grouping, priority ranking, rationale transparency toggle, gap linkage, answered-question deduplication
- `backend/tests/test_gap_analysis.py` - 17 tests covering all gap types, priorities, coverage, deduplication, persistence, topic grouping, transparency toggle, and answered-question filtering

## Decisions Made
- All existing gaps (both addressed and open) are included in the deduplication signature set -- addressed gaps should not be re-detected and open gaps should not be duplicated
- Gap priority formula varies by type: unsupported_element uses parent claim confidence * 100, unexplored_claim uses fixed 50, weak_mapping uses (1 - mapping.confidence) * 100, procedural_requirement uses LLM-provided priority
- Procedural requirement detection via LLM fails gracefully -- returns empty list on any exception, since procedural gaps are optional enrichment
- Question transparency is a boolean toggle: rationale is either fully included or set to None (no partial disclosure)
- Gap-to-question matching uses description string equality with substring fuzzy fallback for robustness

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed gap signature deduplication logic**
- **Found during:** Task 1, test_resolved_gaps_not_redetected
- **Issue:** Initial implementation excluded addressed gaps from the deduplication set, causing them to be re-detected
- **Fix:** Changed to include ALL existing gaps in signature set regardless of status
- **Files modified:** backend/app/services/analysis/stages/gap_analyze.py
- **Commit:** 98d0a3a

## Issues Encountered
None beyond the deduplication fix above.

## User Setup Required
None -- no external service configuration required.

## Known Stubs
None -- all stages are fully implemented with no placeholder data.

## Next Phase Readiness
- GapAnalyzeStage and QuestionGenStage are ready for Plan 04-05 (pipeline orchestrator) to wire into the iterative analysis loop
- Both stages follow the consistent execute() pattern returning dict metrics
- FollowUpQuestion records link back to gaps for traceability in the analysis output

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 04-core-analysis-pipeline*
*Completed: 2026-04-04*
