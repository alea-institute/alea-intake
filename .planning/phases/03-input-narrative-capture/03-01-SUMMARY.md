---
phase: 03-input-narrative-capture
plan: 01
subsystem: api, database
tags: [websocket, sqlalchemy, fastapi, jwt, llm, chat, intake, normalization]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: TenantBase, SharedBase, auth system, encryption primitives, LLM service
  - phase: 02-folio-ontology-integration
    provides: FOLIO concept models (intake_id FK placeholder)
provides:
  - 10 intake DB models (Intake, IntakeParty, IntakeSession, Message, AudioRecording, Transcript, UploadedDocument, DocumentExtraction, ExtractedFact, FactSourceSpan)
  - Message normalization pipeline (NormalizedContent, normalize_text, normalize_professional_note, process_message)
  - IntakeSessionService for session lifecycle management
  - ConversationService for LLM-guided follow-up questions
  - WebSocket chat endpoint with JWT auth and real-time messaging
  - REST endpoints for intake CRUD and message history
  - Config settings for intake uploads, ASR, and audio storage
affects: [03-02-PLAN, 03-03-PLAN, 03-04-PLAN, 08-frontend-application]

# Tech tracking
tech-stack:
  added: []
  patterns: [WebSocket ConnectionManager per session, JWT auth via query param for WS, sequence-numbered messages, NormalizedContent dataclass pipeline]

key-files:
  created:
    - backend/app/models/intake.py
    - backend/app/models/audio.py
    - backend/app/models/document.py
    - backend/app/models/fact.py
    - backend/app/services/intake/__init__.py
    - backend/app/services/intake/session_service.py
    - backend/app/services/intake/conversation.py
    - backend/app/services/intake/message_pipeline.py
    - backend/app/routers/intake.py
    - backend/tests/test_message_pipeline.py
    - backend/tests/test_intake_chat.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/config.py
    - backend/app/main.py

key-decisions:
  - "ConversationService falls back to static follow-up when LLM unavailable -- avoids hard dependency on LLM config during early development"
  - "WebSocket JWT auth via query param (?token=) rather than header -- standard browser WebSocket API does not support custom headers"
  - "WebSocket endpoint uses separate ws_router (no /api/v1/intake prefix) to avoid conflict with REST router prefix"
  - "Content stored as bytes in content_encrypted (plaintext encoding) -- actual EncryptionContext integration deferred to encryption phase"

patterns-established:
  - "IntakeConnectionManager: per-session WebSocket connection tracking with send_to_session and send_to_others"
  - "NormalizedContent pipeline: dataclass-based normalization with TextElement and SourceSpan for provenance"
  - "Consent-gated intake endpoints: REST intake endpoints require AI processing consent via ConsentMiddleware"

requirements-completed: [INGEST-01, INGEST-05]

# Metrics
duration: 8min
completed: 2026-04-04
---

# Phase 3 Plan 01: Intake Models, Message Pipeline, and WebSocket Chat Summary

**10 intake DB models, NormalizedContent message pipeline, and WebSocket chat with JWT auth, sequence-numbered messages, and LLM-guided follow-up questions**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-04T01:43:23Z
- **Completed:** 2026-04-04T01:52:22Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- All 10 Phase 3 DB models created (Intake, IntakeParty, IntakeSession, Message, AudioRecording, Transcript, UploadedDocument, DocumentExtraction, ExtractedFact, FactSourceSpan) with correct column types and TenantBase inheritance
- Unified message normalization pipeline with NormalizedContent dataclass, TextElement and SourceSpan for provenance tracking, supporting text and professional_note modalities (voice/document deferred to Plan 02)
- WebSocket chat endpoint at /api/ws/intake/{session_id} with JWT auth (close code 4001 for invalid tokens), text_message handling with message_ack + system_message, session_pause, and typing_indicator broadcast
- REST endpoints for intake CRUD (POST/GET /api/v1/intake), message history (GET /{id}/messages), party management, and session creation
- ConversationService with INTAKE_SYSTEM_PROMPT, consumer/professional welcome messages, and LLM response generation with static fallback

## Task Commits

Each task was committed atomically (TDD: test, then feat):

1. **Task 1: Intake DB models, config settings, and message normalization pipeline**
   - `936a99f` (test: failing tests for models, config, pipeline)
   - `154cf10` (feat: implement all 10 models, config settings, message pipeline)
2. **Task 2: WebSocket chat system with session lifecycle and LLM conversation**
   - `be02f0c` (test: failing tests for WS chat, session, conversation)
   - `de16c50` (feat: implement WS chat, session service, conversation, REST endpoints)

## Files Created/Modified
- `backend/app/models/intake.py` - Intake, IntakeParty, IntakeSession, Message models
- `backend/app/models/audio.py` - AudioRecording, Transcript models
- `backend/app/models/document.py` - UploadedDocument, DocumentExtraction models
- `backend/app/models/fact.py` - ExtractedFact, FactSourceSpan models
- `backend/app/models/__init__.py` - Re-exports all 10 new model classes
- `backend/app/config.py` - Intake upload, ASR, and audio storage settings
- `backend/app/services/intake/__init__.py` - Package init
- `backend/app/services/intake/session_service.py` - IntakeSessionService with full session lifecycle
- `backend/app/services/intake/conversation.py` - ConversationService with LLM integration and welcome messages
- `backend/app/services/intake/message_pipeline.py` - NormalizedContent, TextElement, SourceSpan, normalization functions
- `backend/app/routers/intake.py` - REST + WebSocket endpoints with IntakeConnectionManager
- `backend/app/main.py` - Router registration for intake and intake-ws
- `backend/tests/test_message_pipeline.py` - 33 tests for models, config, and pipeline
- `backend/tests/test_intake_chat.py` - 17 tests for session service, conversation, REST, and WebSocket

## Decisions Made
- **ConversationService static fallback:** When LLM is not configured, returns a sensible default follow-up question rather than failing. This avoids hard-coding LLM dependency during development.
- **WebSocket JWT via query param:** Browser WebSocket API does not support custom Authorization headers, so token is passed as ?token= query parameter -- standard pattern.
- **Separate ws_router for WebSocket:** WebSocket endpoint lives at /api/ws/intake/{session_id} via a separate router to avoid prefix conflict with the REST /api/v1/intake router.
- **Plaintext bytes for content_encrypted:** Content is encoded as UTF-8 bytes but not yet encrypted. EncryptionContext integration will be wired when that service is extended for intake models.
- **Lightweight WS test app:** WebSocket tests use a minimal FastAPI app without the FOLIO lifespan to avoid heavy OWL/embedding initialization in unit tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added consent granting to REST endpoint tests**
- **Found during:** Task 2 (REST endpoint tests)
- **Issue:** ConsentMiddleware blocks /api/v1/intake/* endpoints for users without AI processing consent
- **Fix:** Added _setup_authed_user helper that registers, logs in, and grants AI processing consent before hitting intake endpoints
- **Files modified:** backend/tests/test_intake_chat.py
- **Verification:** All 3 REST endpoint tests pass with 201/200 status codes
- **Committed in:** de16c50 (Task 2 commit)

**2. [Rule 3 - Blocking] Used lightweight FastAPI app for WebSocket tests**
- **Found during:** Task 2 (WebSocket tests)
- **Issue:** Starlette TestClient(app) triggers the full FOLIO lifespan (OWL load, embedding build) which fails in the test environment
- **Fix:** Created _make_ws_test_app() that builds a minimal FastAPI with only the ws_router, avoiding FOLIO lifespan
- **Files modified:** backend/tests/test_intake_chat.py
- **Verification:** Both WebSocket auth rejection tests pass
- **Committed in:** de16c50 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None. All models are fully defined with correct column types. The ConversationService returns static LLM responses (by design -- LLM integration is functional but returns default text when no LLM is configured). Voice and document normalization raise NotImplementedError (by design -- wired in Plan 02).

## Next Phase Readiness
- All 10 DB models ready for Plan 02 (voice/ASR, document processing) and Plan 03 (fact extraction, professional mode)
- Message normalization pipeline extensible for voice and document modalities
- WebSocket infrastructure ready for voice_upload and document_upload message types
- IntakeSessionService provides session lifecycle for all downstream plans

## Self-Check: PASSED

All 12 created files verified present on disk. All 4 task commits (936a99f, 154cf10, be02f0c, de16c50) verified in git log. Full test suite: 226 passed, 0 failed.

---
*Phase: 03-input-narrative-capture*
*Completed: 2026-04-04*
