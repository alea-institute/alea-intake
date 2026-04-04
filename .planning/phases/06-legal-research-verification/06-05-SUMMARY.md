---
phase: 06-legal-research-verification
plan: 05
subsystem: research
tags: [asyncio, research-pipeline, admin-api, usage-tracking, mcp, citation-verification]

# Dependency graph
requires:
  - phase: 06-legal-research-verification (Plans 01-04)
    provides: tool registry, FolioMCPClient, citation normalizer, adapters, verifier, ranker, KB retriever, InsightsService
provides:
  - ResearchStage replacing research_stub in orchestrator
  - Research admin API for tool config, usage, budget, health
  - UsageTracker for per-org research tool budget enforcement
  - FolioMCPClient lifespan integration
  - KB admin router registration in main.py
affects: [analysis-orchestrator, research-pipeline, admin-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [parallel-asyncio-gather, budget-enforcement, admin-router-pattern]

key-files:
  created:
    - backend/app/services/research/research_stage.py
    - backend/app/services/research/usage_tracker.py
    - backend/app/routers/research_admin.py
    - backend/tests/test_research_stage.py
    - backend/tests/test_research_admin.py
  modified:
    - backend/app/services/analysis/orchestrator.py
    - backend/app/services/analysis/stages/research_stub.py
    - backend/app/main.py

key-decisions:
  - "ResearchStage uses asyncio.gather with return_exceptions=True for parallel tool queries -- failing tools don't block others"
  - "UsageTracker uses in-memory storage for MVP; production would persist to ResearchToolConfig"
  - "FolioMCPClient connection is graceful (try/except) -- unavailability doesn't prevent startup"
  - "research_admin router follows screening_admin pattern: router-level Depends(require_role(Role.ADMIN))"
  - "Platform tools are a static list in research_admin; production would use DB-backed tool catalog"
  - "Router registration tests use AST parsing of main.py to avoid email-validator import chain"

patterns-established:
  - "Research pipeline pattern: parallel query -> deduplicate -> verify -> rank -> store"
  - "Budget enforcement pattern: check_budget before query, record_call after success"
  - "Lifespan MCP pattern: connect in startup (graceful), close in shutdown (finally)"

requirements-completed: [RESEARCH-01, RESEARCH-02, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-09, INTEGRATE-05]

# Metrics
duration: 9min
completed: 2026-04-04
---

# Phase 6 Plan 05: Research Stage Integration Summary

**Full ResearchStage pipeline replacing stub with parallel tool queries, citation verification, ranking, KB/insights integration, usage tracking, and research admin API**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-04T23:26:00Z
- **Completed:** 2026-04-04T23:35:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- ResearchStage replaces ResearchStubStage in orchestrator with full parallel research pipeline (asyncio.gather + return_exceptions=True)
- Citation deduplication, batch verification, and multi-signal ranking pipeline wired end-to-end
- KB retriever and InsightsService integrated in parallel with external tool queries
- UsageTracker with budget enforcement -- tools exceeding cap are skipped
- FolioMCPClient connected in application lifespan (graceful degradation if unavailable)
- Research admin API with 6 endpoints: list tools, activate/deactivate, usage, budget, health
- Both research_admin and kb_admin routers registered in main.py

## Task Commits

Each task was committed atomically:

1. **Task 1: ResearchStage + orchestrator wiring + lifespan integration**
   - `773abfa` (test: failing tests for ResearchStage pipeline)
   - `65dd4be` (feat: ResearchStage pipeline with orchestrator wiring and lifespan integration)
2. **Task 2: Research admin API + router registration**
   - `26f1ce1` (test: failing tests for research admin API)
   - `db43ca5` (feat: research admin API with tool config, usage, budget, health endpoints)

## Files Created/Modified
- `backend/app/services/research/research_stage.py` - Full ResearchStage replacing research_stub
- `backend/app/services/research/usage_tracker.py` - Per-org research tool usage tracking and budget enforcement
- `backend/app/routers/research_admin.py` - Admin endpoints for research tool configuration
- `backend/app/services/analysis/orchestrator.py` - _get_stage_instance returns ResearchStage instead of stub
- `backend/app/services/analysis/stages/research_stub.py` - Deprecated with comment
- `backend/app/main.py` - FolioMCPClient lifespan, research_admin + kb_admin router registration
- `backend/tests/test_research_stage.py` - 16 tests for ResearchStage pipeline
- `backend/tests/test_research_admin.py` - 14 tests for admin API and UsageTracker

## Decisions Made
- ResearchStage uses asyncio.gather with return_exceptions=True -- a failing adapter does not block others
- UsageTracker uses in-memory storage for MVP (production would persist to DB)
- FolioMCPClient connection is graceful in lifespan -- unavailability does not block app startup
- Platform tools defined as static list in research_admin for now; production would use DB catalog
- Router registration tests use AST parsing of main.py to avoid email-validator import dependency chain

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created missing UsageTracker module**
- **Found during:** Task 1 (ResearchStage implementation)
- **Issue:** Plan referenced UsageTracker interface from Plan 01 but no file existed at backend/app/services/research/usage_tracker.py
- **Fix:** Created UsageTracker with record_call, check_budget, get_usage_summary, set_budget_cap methods matching the plan interface
- **Files modified:** backend/app/services/research/usage_tracker.py
- **Verification:** All budget enforcement tests pass
- **Committed in:** 65dd4be (part of Task 1 commit)

**2. [Rule 3 - Blocking] Adjusted test to avoid mcp module import**
- **Found during:** Task 1 (FolioMCPClient lifespan test)
- **Issue:** mcp Python package not installed in test environment, causing import error when testing FolioMCPClient lifecycle
- **Fix:** Rewrote Test 17 to mock the entire class without importing the real module
- **Files modified:** backend/tests/test_research_stage.py
- **Verification:** Test passes without requiring mcp package
- **Committed in:** 65dd4be (part of Task 1 commit)

**3. [Rule 3 - Blocking] Router registration tests avoid app import chain**
- **Found during:** Task 2 (registration verification tests)
- **Issue:** Importing app.main triggers auth router -> pydantic EmailStr -> email-validator chain
- **Fix:** Used AST parsing of main.py source to verify imports and include_router calls exist
- **Files modified:** backend/tests/test_research_admin.py
- **Verification:** Tests pass without triggering import chain
- **Committed in:** db43ca5 (part of Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes necessary for test environment compatibility. No scope creep.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 (Legal Research & Verification) is now complete with all 5 plans delivered
- Full research pipeline: tool registry, adapters, MCP client, citation normalizer, verifier, ranker, KB retriever, insights service, ResearchStage, admin API
- Ready for Phase 7 or subsequent phases that depend on research infrastructure

## Self-Check: PASSED

All 5 created files verified present. All 4 commit hashes verified in git log.

---
*Phase: 06-legal-research-verification*
*Completed: 2026-04-04*
