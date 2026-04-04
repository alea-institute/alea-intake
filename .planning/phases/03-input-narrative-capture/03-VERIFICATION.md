---
phase: 03-input-narrative-capture
verified: 2026-04-03T00:00:00Z
status: gaps_found
score: 5/6 requirements verified
gaps:
  - truth: "System extracts atomic factual assertions from narrative text via dedicated LLM call with Pydantic structured output"
    status: failed
    reason: "_call_llm_extraction in fact_extraction.py builds the LLM prompt but never sends it -- always returns empty result with comment 'In a real implementation, this would call the LLM API'"
    artifacts:
      - path: "backend/app/services/extraction/fact_extraction.py"
        issue: "Lines 107-110: config = self._llm.get_client_config() is called but the actual LLM chat call is missing; method returns {\"facts\": [], \"entities\": []} unconditionally"
    missing:
      - "Replace the stub body in _call_llm_extraction with an actual LLM chat call using self._llm (or alea-llm-client) to send messages and receive structured JSON output"
      - "Parse the LLM response string as JSON before passing to ExtractionResultSchema.model_validate"
      - "Handle LLM API errors gracefully with the existing empty-result fallback"
  - truth: "REQUIREMENTS.md reflects completed status for INGEST-03 and INGEST-04"
    status: failed
    reason: "REQUIREMENTS.md marks INGEST-03 and INGEST-04 as [ ] pending and their traceability table rows as 'Pending', but both are fully implemented and tested"
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Line 14: INGEST-03 checkbox is [ ] but document upload is fully implemented (DocumentService, extractors, REST endpoint, pipeline integration). Line 15: INGEST-04 checkbox is [ ] but professional intake router is fully implemented. Lines 160-161: traceability rows still show 'Pending'."
    missing:
      - "Mark INGEST-03 as [x] complete in REQUIREMENTS.md"
      - "Mark INGEST-04 as [x] complete in REQUIREMENTS.md"
      - "Update traceability table rows for INGEST-03 and INGEST-04 to 'Complete'"
human_verification:
  - test: "Confirm LLM follow-up questions are contextually relevant to consumer input"
    expected: "When a consumer sends 'My landlord locked me out last Tuesday', the system reply should ask a clarifying follow-up about the situation, not a generic question"
    why_human: "ConversationService static fallback returns a fixed question; whether the LLM path (when configured) produces contextually relevant questions cannot be verified programmatically"
  - test: "Confirm voice transcript display and edit flow works in the browser"
    expected: "After recording audio, consumer sees transcript text, can edit it before submission, and the edited text becomes the session message"
    why_human: "Voice upload uses base64 encoding over WebSocket -- the browser-side recording and display cannot be tested programmatically"
---

# Phase 3: Input Narrative Capture Verification Report

**Phase Goal:** Consumers and professionals can provide information through any supported modality (text, voice, documents, professional notes), and the system normalizes all input into a common representation with extracted factual assertions
**Verified:** 2026-04-03
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Consumer can type a message via WebSocket and receive acknowledgment with message_id and sequence_number | VERIFIED | `_handle_text_message` in intake.py stores message, sends `message_ack` with `message_id` and `sequence_number`; 14 passing tests in test_intake_chat.py |
| 2 | System LLM-generated question is sent back through the same WebSocket connection | VERIFIED | ConversationService.generate_response called after text_message; `system_message` sent back; static fallback when LLM not configured |
| 3 | All chat messages are normalized into a common NormalizedContent representation with source spans | VERIFIED | message_pipeline.py has normalize_text, normalize_professional_note, normalize_voice_transcript, document delegation; all return NormalizedContent with SourceSpan |
| 4 | Voice audio submitted to ASR service returns transcript text with segments and confidence | VERIFIED | ASRService with WhisperProvider/DeepgramProvider/AssemblyAIProvider; voice_upload -> transcript_ready flow; 17 ASR tests pass |
| 5 | Consumer can upload a document via REST endpoint and extracted content enters the session stream | VERIFIED | POST /{intake_id}/document creates Message(modality=document) + UploadedDocument + DocumentExtraction; 12 document intake tests pass |
| 6 | Professional can enter notes on behalf of a consumer through a role-gated endpoint | VERIFIED | intake_professional.py router with `require_role(Role.PROFESSIONAL, Role.ADMIN)`; note stores Message(sender_type=professional, modality=professional_note) with attribution metadata; 6 professional intake tests pass |
| 7 | System extracts atomic factual assertions from narrative via LLM call with Pydantic structured output | FAILED | FactExtractionService, ExtractedFactSchema, ExtractionResultSchema all exist and are correct; but _call_llm_extraction always returns empty facts -- LLM is never called |
| 8 | Extracted facts are persisted as ExtractedFact + FactSourceSpan records | VERIFIED (conditional) | extract_and_persist creates ExtractedFact and FactSourceSpan records correctly; logic is correct but never executes with real facts because extract_facts always returns empty |
| 9 | Intake is accessible at /api/v1/intake after application startup | VERIFIED | main.py includes intake_router (prefix=/api/v1/intake), intake_ws_router (/api/ws/intake), intake_professional_router (/api/v1/intake/professional) |

**Score:** 8/9 truths verified (INGEST-06 partially failed due to LLM stub)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/intake.py` | Intake, IntakeParty, IntakeSession, Message models | VERIFIED | All 4 classes present with correct TenantBase inheritance and column types |
| `backend/app/models/audio.py` | AudioRecording, Transcript models | VERIFIED | Both classes with correct column types |
| `backend/app/models/document.py` | UploadedDocument, DocumentExtraction models | VERIFIED | Both classes with correct column types |
| `backend/app/models/fact.py` | ExtractedFact, FactSourceSpan models | VERIFIED | Both classes with correct column types including is_active, superseded_by_id |
| `backend/app/models/__init__.py` | All 10 new model imports | VERIFIED | All 10 models imported and in __all__ |
| `backend/app/services/intake/message_pipeline.py` | NormalizedContent, process_message | VERIFIED | NormalizedContent, TextElement, SourceSpan dataclasses; process_message routes all 4 modalities |
| `backend/app/services/intake/session_service.py` | IntakeSessionService | VERIFIED | create_intake, store_message, pause_session, get_next_sequence, resume_session, list_intakes, get_messages all implemented |
| `backend/app/services/intake/conversation.py` | ConversationService | VERIFIED | generate_response, generate_welcome_message, INTAKE_SYSTEM_PROMPT present |
| `backend/app/routers/intake.py` | WebSocket + REST intake endpoints | VERIFIED | IntakeConnectionManager, intake_websocket, REST CRUD endpoints, voice handlers, document_upload endpoint |
| `backend/app/services/asr/asr_service.py` | ASRService with _ASR_PROVIDER_MAP | VERIFIED | _ASR_PROVIDER_MAP with whisper/deepgram/assemblyai; ASRService; convert_audio_format |
| `backend/app/services/asr/providers/base.py` | ASRProviderBase ABC + TranscriptionResult | VERIFIED | Both present with correct interface |
| `backend/app/services/asr/providers/whisper_provider.py` | WhisperProvider | VERIFIED | httpx.AsyncClient with 120s timeout, POST to /transcribe |
| `backend/app/services/document/document_service.py` | DocumentService | VERIFIED | _MIME_EXTRACTOR_MAP, save_upload, process_document, get_supported_mime_types |
| `backend/app/services/document/extractors/pdf_extractor.py` | extract_pdf | VERIFIED | PyMuPDF-based extraction with heading classification |
| `backend/app/services/document/extractors/docx_extractor.py` | extract_docx | VERIFIED | python-docx extraction preserving headings/tables |
| `backend/app/services/document/extractors/ocr_extractor.py` | extract_image_ocr | VERIFIED | pytesseract+Pillow OCR (skipped in tests when tesseract binary absent) |
| `backend/app/routers/intake_professional.py` | Professional intake router | VERIFIED | role-gated router, POST /, POST /{id}/note, POST /{id}/structured-form, GET /{id}/summary |
| `backend/app/services/extraction/schemas.py` | Pydantic extraction schemas | VERIFIED | ExtractedEntitySchema, ExtractedFactSchema, ExtractionResultSchema with Field constraints |
| `backend/app/services/extraction/fact_extraction.py` | FactExtractionService | STUB | Class exists with correct structure; _call_llm_extraction always returns empty facts |
| `backend/app/main.py` | Router registration + upload dir creation | VERIFIED | All 3 intake routers registered; upload directory created in lifespan |
| `backend/app/config.py` | Intake, ASR, file storage settings | VERIFIED | intake_upload_dir, intake_max_file_size_mb, asr_default_provider, whisper_endpoint, intake_fact_visibility present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `intake.py` (router) | `session_service.py` | IntakeSessionService | WIRED | `svc = IntakeSessionService(session)` in every REST handler |
| `intake.py` (router) | `message_pipeline.py` | normalize_text, process_message | WIRED | normalize_text imported and called in _handle_text_message; process_message called in transcript handlers |
| `session_service.py` | `intake.py` models | Intake, IntakeSession, Message | WIRED | All 4 intake models imported and used in session_service.py |
| `intake.py` (router) | `asr_service.py` | ASRService.transcribe | WIRED | `asr_service = ASRService(); asr_result = await asr_service.transcribe(...)` in _handle_voice_upload |
| `asr_service.py` | `providers/base.py` | _ASR_PROVIDER_MAP | WIRED | `_ASR_PROVIDER_MAP = {"whisper": WhisperProvider, ...}` resolves at init |
| `intake.py` (router) | `document_service.py` | DocumentService.process_document | WIRED | `doc_service = DocumentService(); normalized = await doc_service.process_document(...)` in document_upload |
| `message_pipeline.py` | `document_service.py` | DocumentService delegation for "document" modality | WIRED | `from app.services.document import DocumentService; return await doc_service.process_document(...)` |
| `intake_professional.py` | `session_service.py` | IntakeSessionService | WIRED | `svc = IntakeSessionService(session)` used in all professional endpoints |
| `fact_extraction.py` | `llm_service.py` | LLMService for extraction calls | PARTIAL | LLMService imported and `self._llm.get_client_config()` called, but extracted result is hardcoded empty -- LLM chat call not made |
| `fact_extraction.py` | `concept_resolver.py` | resolve_concepts per-fact | WIRED | `resolve_concepts(fact_schema.assertion, self._folio, self._embedding_service)` called in extract_and_persist when folio is not None |
| `main.py` | `intake.py` (router) | app.include_router | WIRED | `app.include_router(intake_router)` and `app.include_router(intake_ws_router)` present |
| `main.py` | `intake_professional.py` | app.include_router | WIRED | `app.include_router(intake_professional_router)` present |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `intake.py` WebSocket text_message | message (Message model) | `svc.store_message(...)` -> DB write | Yes | FLOWING |
| `intake.py` WebSocket voice_upload | asr_result (TranscriptionResult) | `asr_service.transcribe(audio_bytes, format)` | Yes (via mocked provider in tests; real provider at runtime) | FLOWING |
| `document_service.py` process_document | text, elements | `extract_pdf(file_path)` / `extract_docx(file_path)` | Yes -- real PyMuPDF / python-docx extraction | FLOWING |
| `fact_extraction.py` extract_facts | result (ExtractionResultSchema) | `_call_llm_extraction(text, session_facts)` | No -- always returns `{"facts": [], "entities": []}` | DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 3 test suite passes | `.venv/bin/python -m pytest tests/test_message_pipeline.py tests/test_intake_chat.py tests/test_asr_service.py tests/test_voice_intake.py tests/test_document_service.py tests/test_document_intake.py tests/test_professional_intake.py tests/test_fact_extraction.py` | 118 passed, 3 skipped (OCR requires tesseract binary) | PASS |
| Intake router importable | `python -c "from app.routers.intake import router, ws_router; print(router.prefix)"` | `/api/v1/intake` | PASS |
| Professional router role-gated | `grep "require_role" backend/app/routers/intake_professional.py` | `dependencies=[Depends(require_role(Role.PROFESSIONAL, Role.ADMIN))]` | PASS |
| fact_extraction LLM call stub | `grep "_call_llm_extraction" backend/app/services/extraction/fact_extraction.py` | `return {"facts": [], "entities": []}` unconditional | FAIL -- blocker |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| INGEST-01 | Plan 03-01 | Consumer can submit narrative text via conversational chat interface | SATISFIED | WebSocket text_message handler + message_ack + system_message + 14 tests pass |
| INGEST-02 | Plan 03-02 | Consumer can record voice input transcribed via pluggable ASR | SATISFIED | ASRService + 3 providers + voice_upload WebSocket flow + 3 voice tests + 17 ASR tests pass |
| INGEST-03 | Plan 03-03 | Consumer can upload documents (PDF, DOCX, images) for text extraction | SATISFIED | DocumentService + 3 extractors + REST endpoint + 28 tests pass. Note: REQUIREMENTS.md checkbox not updated (still `[ ]`) |
| INGEST-04 | Plan 03-04 | Professional can enter notes on behalf of a consumer | SATISFIED | intake_professional.py router + role enforcement + 6 tests pass. Note: REQUIREMENTS.md checkbox not updated (still `[ ]`) |
| INGEST-05 | Plan 03-01 | System normalizes all input modalities into common representation | SATISFIED | NormalizedContent pipeline handles text/voice/document/professional_note; process_message routes all modalities |
| INGEST-06 | Plan 03-04 | System extracts atomic factual assertions from narrative | BLOCKED | FactExtractionService structure complete; Pydantic schemas correct; persistence logic correct; but _call_llm_extraction always returns empty facts -- the LLM is never invoked |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/services/extraction/fact_extraction.py` | 108-110 | `# In a real implementation, this would call the LLM API` followed by `return {"facts": [], "entities": []}` | BLOCKER | Fact extraction never produces any facts; INGEST-06 is not achieved |

### Human Verification Required

#### 1. LLM Conversation Quality

**Test:** Send a consumer intake message describing a legal situation (e.g., "My employer fired me after I told them I was pregnant") via the WebSocket chat endpoint
**Expected:** The system_message reply should ask a contextually relevant follow-up question about the situation (e.g., asking about the timeline or documentation), not a generic response
**Why human:** ConversationService has a static fallback that returns a fixed question when LLM is not configured; contextual quality of the LLM path cannot be verified programmatically

#### 2. Voice Transcript Edit Flow

**Test:** Use a browser client to record a voice message, review the auto-generated transcript, edit it, and submit the edited version
**Expected:** The edited text should appear as the session message; the original recording should not be modified
**Why human:** The voice upload flow uses base64 binary over WebSocket -- the full browser-side recording, display, and edit UX cannot be tested with grep-level verification

### Gaps Summary

**One blocker gap prevents full goal achievement:**

The `_call_llm_extraction` method in `backend/app/services/extraction/fact_extraction.py` (lines 107-110) is a stub. It constructs the correct LLM prompt and calls `self._llm.get_client_config()` to inspect the LLM configuration, but then returns an empty result without making the actual LLM API call. The comment explicitly acknowledges this: "In a real implementation, this would call the LLM API". As a result, `extract_facts` always returns `ExtractionResultSchema(facts=[], entities=[])`, and `extract_and_persist` never creates any `ExtractedFact` or `FactSourceSpan` records from real input.

The rest of the FactExtractionService implementation is correct and production-ready: Pydantic schemas validate correctly, source span bounds-checking works, ConceptResolver integration is wired with graceful degradation, same-party supersession logic is implemented, and all 14 fact_extraction tests pass (by mocking the `_call_llm_extraction` method to return fake facts).

**Two informational gaps (not blockers):**

REQUIREMENTS.md checkboxes for INGEST-03 and INGEST-04 remain unchecked (`[ ]`) and their traceability rows still show "Pending", even though both requirements are fully implemented and tested. This is a documentation inconsistency, not a code defect. The underlying implementations are complete and passing.

---

_Verified: 2026-04-03_
_Verifier: Claude (gsd-verifier)_
