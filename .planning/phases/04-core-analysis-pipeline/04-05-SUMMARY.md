---
phase: 04-core-analysis-pipeline
plan: 05
subsystem: analysis
tags: [orchestrator, asyncio, websocket, convergence, parallel-jurisdiction, fastapi, rest-api]

requires:
  - phase: 04-core-analysis-pipeline/plan-01
    provides: Analysis DB models (AnalysisRun, AnalysisIteration, AnalysisStage, AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap, FollowUpQuestion)
  - phase: 04-core-analysis-pipeline/plan-02
    provides: ConvergenceEvaluator and CompositeConfidenceScorer
  - phase: 04-core-analysis-pipeline/plan-03
    provides: IssueSpotStage, FactMapStage, ResearchStubStage
  - phase: 04-core-analysis-pipeline/plan-04
    provides: GapAnalyzeStage, QuestionGenStage
provides:
  - AnalysisOrchestrator with LLM-driven iterative loop and parallel jurisdiction execution
  - AnalysisTrigger with auto + manual triggering
  - REST API endpoints for analysis trigger, status, results, override, audit trail
  - WebSocket progress broadcasting integration
affects: [05-pre-research-exploration, 06-legal-research, 07-output-export, 08-frontend, 10-autonomy]

tech-stack:
  added: []
  patterns: [asyncio.gather for parallel jurisdiction branches, background task via asyncio.create_task, stage checkpoint with audit_json]

key-files:
  created:
    - backend/app/services/analysis/orchestrator.py
    - backend/app/services/analysis/trigger.py
    - backend/app/routers/analysis.py
    - backend/tests/test_analysis_orchestrator.py
    - backend/tests/test_analysis_trigger.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Orchestrator runs all stages sequentially by default; parallel only for multi-jurisdiction fact-map and gap-analyze"
  - "Auto-trigger creates run record immediately then spawns background task; manual trigger runs inline"
  - "Resume loads latest completed AnalysisStage and skips already-completed stages in current iteration"

patterns-established:
  - "Stage checkpoint pattern: every stage execution creates AnalysisStage with audit_json containing stage_name, input_fact_count, claims_produced, sources_consulted, confidence_scores_summary, duration_ms"
  - "Parallel jurisdiction pattern: asyncio.gather spawns per-jurisdiction branches for fact-map + gap-analyze"
  - "Analysis REST pattern: POST trigger returns 202, GET status/results/audit for polling"

requirements-completed: [ANALYSIS-01, ANALYSIS-08, ANALYSIS-09, ANALYSIS-10]

duration: 6min
completed: 2026-04-04
---

# Phase 4 Plan 5: Analysis Pipeline Orchestrator, Trigger, and REST API Summary

**LLM-driven iterative analysis orchestrator with parallel jurisdiction execution, auto/manual triggering, and REST API with WebSocket progress broadcasting**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-04T15:32:27Z
- **Completed:** 2026-04-04T15:38:55Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- AnalysisOrchestrator runs the full iterative loop (issue-spot, research, fact-map, gap-analyze, question) with LLM-driven stage selection, convergence evaluation, and AnalysisStage checkpoints with populated audit_json
- Parallel per-jurisdiction analysis via asyncio.gather when multiple jurisdictions detected -- fact-map and gap-analyze run concurrently for each jurisdiction
- AnalysisTrigger fires automatically when fact count reaches configurable threshold (default 5) and manually via REST API; skips when analysis already running
- REST API: POST /analyze (202 Accepted), GET /status, GET /results, POST /override, GET /audit -- all wired into main.py
- Pause/resume from latest checkpoint and convergence override to continue analysis after termination
- WebSocket progress broadcasting via send_to_session for real-time stage-by-stage updates

## Task Commits

Each task was committed atomically:

1. **Task 05-01: Analysis orchestrator with parallel jurisdiction execution** - `d4957cc` (feat)
2. **Task 05-02: Analysis trigger, REST API, main.py wiring** - `6b1adc4` (feat)

## Files Created/Modified
- `backend/app/services/analysis/orchestrator.py` - AnalysisOrchestrator with iterative loop, parallel jurisdictions, resume, override, progress broadcast
- `backend/app/services/analysis/trigger.py` - AnalysisTrigger with auto/manual triggering and running-check guard
- `backend/app/routers/analysis.py` - REST endpoints for trigger, status, results, override, audit trail
- `backend/app/main.py` - Added analysis router registration
- `backend/tests/test_analysis_orchestrator.py` - 7 tests: run/iterate, hard cap, checkpoint with audit_json, parallel jurisdictions, resume, override, WebSocket broadcast
- `backend/tests/test_analysis_trigger.py` - 7 tests: auto-trigger fires/skips, manual trigger, existing run return, router exists, main.py wiring

## Decisions Made
- Orchestrator runs all stages in sequence by default; parallel execution only for multi-jurisdiction fact-map and gap-analyze via asyncio.gather
- Auto-trigger creates the AnalysisRun record immediately then launches orchestrator via asyncio.create_task for background execution; manual trigger runs inline for immediate feedback
- Resume finds the latest completed AnalysisStage, determines which stages remain in the current iteration, and skips already-completed ones before continuing the loop

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
- IntakeSession model does not have a `mode` column (it is on Intake as `session_mode`) -- fixed test fixture to match actual schema

## User Setup Required

None -- no external service configuration required.

## Known Stubs

None -- all components are fully wired to their dependencies.

## Next Phase Readiness
- Phase 4 (Core Analysis Pipeline) is now complete with all 5 plans executed
- The full iterative analysis loop is operational: fact extraction triggers analysis, stages execute with convergence detection, results available via REST API
- Phase 5 (Pre-Research Exploration & Safety) can build on the orchestrator's stage execution pattern to add exploration stages
- Phase 6 (Legal Research) can replace ResearchStubStage with full research tool integration
- Phase 8 (Frontend) can consume the analysis REST API and WebSocket progress events

## Self-Check: PASSED

All 5 created files verified present. Both task commit hashes (d4957cc, 6b1adc4) verified in git log. 418 tests passing (0 failures).

---
*Phase: 04-core-analysis-pipeline*
*Completed: 2026-04-04*
