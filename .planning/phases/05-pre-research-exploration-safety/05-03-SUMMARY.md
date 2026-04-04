---
phase: 05-pre-research-exploration-safety
plan: 03
subsystem: screening
tags: [screening-middleware, safety-screening, websocket, trigger-matching, priority-dispatch, audit-trail]

# Dependency graph
requires:
  - phase: 05-pre-research-exploration-safety
    plan: 01
    provides: "TriggerMatcher, ProtocolService, ScreeningEvent model, ScreeningResult schema"
  - phase: 03-input-narrative-capture
    provides: "intake.py WebSocket handler, _handle_text_message, _handle_transcript_approve"
provides:
  - "screen_message_fast function for <50ms per-message screening"
  - "Three-tier priority dispatch: critical=immediate_alert, elevated=queued, advisory=folded_to_exploration"
  - "build_safety_alert_message for WebSocket safety_alert JSON"
  - "persist_screening_event for ScreeningEvent audit trail"
  - "queue_elevated_screening and add_to_exploration_queue dispatch helpers"
  - "TriggerMatcher session-level caching with 5-min TTL"
  - "Screening wired into _handle_text_message and _handle_transcript_approve"
affects: [05-02-exploration-engine, 08-frontend-application]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-message-screening-middleware, priority-interrupt-model, session-level-matcher-cache]

key-files:
  created:
    - backend/app/services/screening/middleware.py
    - backend/tests/test_screening_middleware.py
  modified:
    - backend/app/routers/intake.py
    - backend/app/models/__init__.py

key-decisions:
  - "TriggerMatcher cached per session_id with 5-min TTL to avoid regex recompilation on every message"
  - "Screening wrapped in try/except in WebSocket handlers for graceful degradation"
  - "Safety resources merged from both safety_resources_json and escalation_actions_json.immediate_resources"
  - "Question transparency applied at screening time (text_transparent vs text field selection)"

patterns-established:
  - "Per-message screening: screen_message_fast before message storage, never blocking"
  - "Priority interrupt model: critical=immediate WS alert, elevated=DB queue, advisory=exploration fold"
  - "Screening audit: ScreeningEvent per triggered protocol with action_taken classification"

requirements-completed: [EXPLORE-04, EXPLORE-09, EXPLORE-10]

# Metrics
duration: 11min
completed: 2026-04-04
---

# Phase 5 Plan 03: Continuous Safety Screening Middleware Summary

**Per-message screening middleware with <50ms TriggerMatcher, three-tier priority dispatch (critical/elevated/advisory), WebSocket safety alerts, and ScreeningEvent audit trail**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-04T17:17:02Z
- **Completed:** 2026-04-04T17:28:58Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- screen_message_fast function that screens every consumer message against active protocol triggers in <50ms, using a session-level TriggerMatcher cache with 5-minute TTL
- Three-tier priority dispatch exactly matching D-10: critical triggers send immediate WebSocket safety_alert with resources and mandatory questions, elevated triggers persist queued ScreeningEvent for next pause, advisory triggers fold into the exploration queue
- Screening wired into both _handle_text_message and _handle_transcript_approve, ensuring voice transcripts get the same safety screening as text (D-08)
- ScreeningEvent audit records persisted for every triggered protocol with action_taken classification
- 25 tests covering middleware logic, priority dispatch, persistence, WebSocket integration, and performance benchmark

## Task Commits

Each task was committed atomically:

1. **Task 1: Screening middleware function with priority dispatch and ScreeningEvent persistence**
   - `b9d4368` (test: failing tests -- TDD RED)
   - `f33d1aa` (feat: implementation -- TDD GREEN)

2. **Task 2: WebSocket integration -- wire screening into _handle_text_message and voice/transcript handlers**
   - `cd9ba9e` (test: failing tests -- TDD RED)
   - `f77afc9` (feat: implementation -- TDD GREEN)

## Files Created/Modified

- `backend/app/services/screening/middleware.py` -- screen_message_fast, build_safety_alert_message, persist_screening_event, queue_elevated_screening, add_to_exploration_queue, session-level matcher cache
- `backend/tests/test_screening_middleware.py` -- 25 tests (16 unit + 9 integration) covering all priority tiers, question transparency, persistence, WebSocket dispatch, and performance
- `backend/app/routers/intake.py` -- Added screening imports, wired screen_message_fast into _handle_text_message and _handle_transcript_approve with try/except graceful degradation
- `backend/app/models/__init__.py` -- Added screening model re-exports (ScreeningProtocol, ProtocolVersion, OrgProtocolActivation, ScreeningEvent)

## Decisions Made

- **TriggerMatcher cached per session_id:** Avoids recompiling regex and reloading protocols from DB on every message. 5-minute TTL balances performance with protocol activation change detection.
- **Screening wrapped in try/except:** Per D-09, screening is a separate system from message handling. If screening fails (DB error, protocol loading), message processing continues normally with a warning log.
- **Safety resources merged from two sources:** Both `safety_resources_json` and `escalation_actions_json.immediate_resources` are merged with deduplication by name, ensuring comprehensive resource delivery.
- **Question transparency at screening time:** The `question_transparency` parameter selects `text_transparent` (with rationale framing) or plain `text` at screen time, so the ScreeningResult already has the correct question variant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Copied Plan 05-01 dependency files to worktree**
- **Found during:** Task 1 (before test execution)
- **Issue:** Plan 05-01 files (screening models, services, trigger_matcher, schemas) only exist in the main repo, not in this worktree
- **Fix:** Copied all screening module files, exploration schemas, analysis schemas, and models/__init__.py updates from main repo
- **Files modified:** 11 dependency files
- **Verification:** All tests pass with copied files

**2. [Rule 3 - Blocking] Copied Phase 3 dependency files to worktree**
- **Found during:** Task 2 (intake.py requires audio, document, intake models)
- **Issue:** Phase 3 code (intake.py, models, services) only exists in main repo
- **Fix:** Copied intake.py and all Phase 3 model/service files from main repo before modification
- **Files modified:** intake.py, models (audio, document, intake), services (asr, document, intake)
- **Verification:** All 25 tests pass

---

**Total deviations:** 2 auto-fixed (both blocking -- worktree dependency files)
**Impact on plan:** Standard worktree setup for parallel execution. No scope creep. All plan objectives met exactly.

## Issues Encountered

None -- plan executed cleanly after dependency resolution.

## User Setup Required

None -- no external service configuration required.

## Known Stubs

None -- all screening middleware functions are fully wired and functional. No placeholder data or empty returns.

## Next Phase Readiness

- Plan 02 (exploration engine) can use screen_message_fast results to trigger deep exploration scans
- Plan 08 (frontend) can handle safety_alert WebSocket messages to display safety resources and mandatory questions
- ScreeningEvent records available for admin review and compliance reporting
- TriggerMatcher cache ready for production load

## Self-Check: PASSED

All 4 key files verified present. All 4 commit hashes verified in git log.

---
*Phase: 05-pre-research-exploration-safety*
*Completed: 2026-04-04*
