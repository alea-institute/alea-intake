---
phase: 03-input-narrative-capture
plan: 04
subsystem: api, extraction
tags: [fastapi, pydantic, llm, folio, concept-resolution, fact-extraction]

requires:
  - phase: 01-foundation-security
    provides: "Auth, RBAC, TenantBase models, LLMService, encryption"
  - phase: 02-folio-ontology-integration
    provides: "ConceptResolver, EmbeddingService, FOLIO singleton"
provides:
  - "Professional intake router with on-behalf-of note entry and structured forms"
  - "FactExtractionService with LLM structured output and ConceptResolver wiring"
  - "ExtractionResultSchema, ExtractedFactSchema, ExtractedEntitySchema Pydantic models"
  - "Intake data models (Intake, IntakeParty, IntakeSession, Message, ExtractedFact, FactSourceSpan)"
  - "Message normalization pipeline (NormalizedContent, normalize_text, normalize_professional_note)"
  - "IntakeSessionService for session lifecycle and message storage"
  - "main.py registration of intake and intake_professional routers"
affects: [04-analysis-pipeline, 09-narrative-anchored-views]

tech-stack:
  added: []
  patterns:
    - "Professional intake router with role-gated endpoints (PROFESSIONAL + ADMIN)"
    - "LLM structured output extraction via Pydantic schema validation"
    - "Per-fact ConceptResolver wiring with graceful degradation (folio=None)"
    - "Same-party fact supersession with is_active/superseded_by_id tracking"
    - "Structured form to narrative text conversion with section markers"

key-files:
  created:
    - "backend/app/routers/intake_professional.py"
    - "backend/app/routers/intake.py"
    - "backend/app/services/extraction/__init__.py"
    - "backend/app/services/extraction/schemas.py"
    - "backend/app/services/extraction/fact_extraction.py"
    - "backend/app/services/intake/__init__.py"
    - "backend/app/services/intake/session_service.py"
    - "backend/app/services/intake/message_pipeline.py"
    - "backend/app/models/intake.py"
    - "backend/app/models/fact.py"
    - "backend/app/models/audio.py"
    - "backend/app/models/document.py"
    - "backend/tests/test_professional_intake.py"
    - "backend/tests/test_fact_extraction.py"
  modified:
    - "backend/app/main.py"
    - "backend/app/config.py"
    - "backend/app/models/__init__.py"

key-decisions:
  - "Created prerequisite models/services from Plan 01 spec as Plan 04 dependency (Plan 01 executes in parallel worktree)"
  - "ConsentRecord seeding required in test fixtures for intake endpoints (consent middleware blocks /api/v1/intake/* routes)"
  - "EXTRACTION_SYSTEM_PROMPT uses all 10 legal-domain entity types from 03-RESEARCH.md"
  - "_call_llm_extraction method separated for easy test mocking without real LLM calls"
  - "Structured form conversion uses section markers [PARTY INFO], [INCIDENT], [TIMELINE], [DAMAGES], [NOTES]"

patterns-established:
  - "Role-gated router pattern: dependencies=[Depends(require_role(Role.PROFESSIONAL, Role.ADMIN))]"
  - "Fact extraction with ConceptResolver graceful degradation: folio=None skips resolution, stores empty resolved_concepts"
  - "Same-party supersession: old fact.is_active=False, superseded_by_id=new_fact.id"
  - "Source span validation: facts with out-of-bounds offsets are silently dropped"

requirements-completed: [INGEST-04, INGEST-06]

duration: 10min
completed: 2026-04-04
---

# Phase 3 Plan 04: Professional Intake and Fact Extraction Summary

**Professional intake router with on-behalf-of notes, structured forms, and LLM-driven fact extraction with ConceptResolver wiring and source span tracking**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-04T01:57:17Z
- **Completed:** 2026-04-04T02:07:56Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Professional intake router at /api/v1/intake/professional with role enforcement (PROFESSIONAL + ADMIN), note submission with party attribution, structured form to narrative conversion, and intake summary endpoint
- FactExtractionService with LLM structured output via Pydantic schemas, all 10 legal-domain entity types, source span validation, same-party supersession, and ConceptResolver integration for FOLIO IRI matching
- All Phase 3 routers registered in main.py with upload directory creation in lifespan
- Full prerequisite infrastructure (intake models, session service, message pipeline, config settings) created as dependency for parallel execution

## Task Commits

Each task was committed atomically:

1. **Task 1: Professional intake router with on-behalf-of note entry** - `9f7acd4` (feat)
2. **Task 2: Fact extraction service with LLM structured output, ConceptResolver wiring, and main.py registration** - `3cd58a5` (feat)

## Files Created/Modified
- `backend/app/routers/intake_professional.py` - Professional intake REST endpoints (POST /, note, structured-form, GET summary)
- `backend/app/routers/intake.py` - Consumer intake REST endpoints (POST /, GET /)
- `backend/app/services/extraction/schemas.py` - Pydantic models: ExtractedEntitySchema, ExtractedFactSchema, ExtractionResultSchema
- `backend/app/services/extraction/fact_extraction.py` - FactExtractionService with EXTRACTION_SYSTEM_PROMPT, extract_facts, extract_and_persist, get_session_facts
- `backend/app/services/extraction/__init__.py` - Package exports
- `backend/app/services/intake/session_service.py` - IntakeSessionService for session lifecycle and message storage
- `backend/app/services/intake/message_pipeline.py` - NormalizedContent, normalize_text, normalize_professional_note, process_message
- `backend/app/services/intake/__init__.py` - Package init
- `backend/app/models/intake.py` - Intake, IntakeParty, IntakeSession, Message models
- `backend/app/models/fact.py` - ExtractedFact, FactSourceSpan models
- `backend/app/models/audio.py` - AudioRecording, Transcript models
- `backend/app/models/document.py` - UploadedDocument, DocumentExtraction models
- `backend/app/models/__init__.py` - Updated with all 10 new model imports
- `backend/app/config.py` - Added intake, ASR, and upload settings
- `backend/app/main.py` - Registered intake + intake_professional routers, added upload dir creation
- `backend/tests/test_professional_intake.py` - 6 tests for professional intake endpoints
- `backend/tests/test_fact_extraction.py` - 14 tests for extraction schemas, service, and persistence

## Decisions Made
- **Prerequisite creation as deviation:** Plan 04 depends on Plan 01 which runs in a separate parallel worktree. Created all prerequisite models, services, and config as part of this execution (Rule 3: auto-fix blocking issues). These files will be reconciled during merge.
- **ConsentRecord seeding:** Consent middleware blocks /api/v1/intake/* routes, requiring consent records in test fixtures.
- **_call_llm_extraction separation:** Extracted LLM call into a dedicated method for clean test mocking without requiring real API calls.
- **Section markers in structured form conversion:** Used [PARTY INFO], [INCIDENT], [TIMELINE], [DAMAGES], [NOTES] markers to preserve structure when converting form data to narrative text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created prerequisite models and services from Plan 01**
- **Found during:** Task 1 (Professional intake router)
- **Issue:** Plan 04 depends on Plan 01 (intake models, session service, message pipeline) which is executing in a parallel worktree and not yet available
- **Fix:** Created all prerequisite files (intake.py, fact.py, audio.py, document.py models; session_service.py, message_pipeline.py, config settings, models/__init__.py updates) from Plan 01 specification
- **Files modified:** 10 prerequisite files
- **Verification:** All 196 tests pass including full regression suite
- **Committed in:** 9f7acd4 (Task 1 commit)

**2. [Rule 1 - Bug] Added consent records to test fixtures**
- **Found during:** Task 1 (Professional intake router)
- **Issue:** Consent middleware blocks /api/v1/intake/* endpoints without active consent records, causing 403 in tests
- **Fix:** Seeded ConsentRecord with ai_processing=True for both professional and consumer test users
- **Files modified:** backend/tests/test_professional_intake.py
- **Verification:** All professional intake tests pass with consent records
- **Committed in:** 9f7acd4 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correct execution in parallel worktree environment. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Professional intake and fact extraction infrastructure complete
- FactExtractionService ready for Phase 4 analysis pipeline integration
- Source spans enable Phase 9 narrative-anchored views
- ConceptResolver wiring provides FOLIO IRI matching for downstream analysis

---
## Self-Check: PASSED

All 15 key files verified present. Both commit hashes (9f7acd4, 3cd58a5) confirmed in git log. 196/196 tests pass.

---
*Phase: 03-input-narrative-capture*
*Completed: 2026-04-04*
