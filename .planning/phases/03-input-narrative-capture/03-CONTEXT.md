# Phase 3: Input & Narrative Capture - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Consumers and professionals can provide information through any supported modality (text, voice, documents, professional notes), and the system normalizes all input into a common representation with extracted factual assertions. This phase delivers the intake layer that feeds Phase 4's analysis pipeline.

</domain>

<decisions>
## Implementation Decisions

### Chat Interaction Model
- Default to conversational turns with LLM-generated guiding questions, but allow consumer to provide free-form narrative submission if they prefer
- LLM-driven question generation by default; orgs can define predefined intake question templates that the LLM pulls from when relevant (LLM acts as orchestrator, deciding which predefined questions are appropriate for the consumer's situation)
- Seamless multi-modal mixing within a session: any message can be text, voice recording, or document upload — all normalized into the same stream
- Session model is org-configurable: single-session (legal aid kiosk) or multi-session with pause/resume (law firm ongoing clients)
- Store both raw message history (full chat transcript) AND normalized output — legal context demands full traceability
- Append-only correction model: new messages override old facts, system tracks both original and corrected assertions with timestamps, audit trail preserved
- Multi-party intakes supported: an intake can have multiple contributing consumers
- Conflicting facts between parties: track per-party assertions with source attribution, both preserved, analysis sees all versions, professionals resolve conflicts
- Professional mode: professionals can choose conversational interface (for complex narratives) or structured form (for straightforward intakes), per-case decision

### Voice/ASR Integration
- Pluggable ASR provider interface mirroring LLMService pattern: per-org provider config in Organization.settings with provider class map, API key management, training opt-out enforcement
- Both streaming and record-then-transcribe modes, org-configurable: streaming for cloud ASR providers that support it (Deepgram, AssemblyAI); record-then-transcribe as fallback for local Whisper or providers without streaming
- Default to storing both encrypted original audio AND transcript; org-configurable (store both, transcript-only, or ephemeral with auto-delete)
- Consumer reviews and edits transcript before it enters the analysis pipeline — critical for legal accuracy (misheard names/dates)
- Broad audio format support: browser-native recording (WebM/Opus, MP4/AAC) plus uploaded files (MP3, WAV, M4A, OGG, WebM). Server-side conversion for ASR providers that need specific formats
- Speaker diarization when ASR provider supports it — maps to per-party assertion tracking for multi-party intakes
- Org-configurable maximum recording duration (sensible default, e.g., 10-15 min per recording). Long narratives split across multiple recordings

### Claude's Discretion (Voice/ASR)
- Local Whisper deployment model (sidecar service vs in-process)

### Document Processing
- Structured text extraction preserving document structure: headings, paragraphs, tables, lists, numbered sections. Legal documents have meaningful structure (exhibits, signatures, numbered paragraphs)
- Store both encrypted original files AND structured extracted text — matches voice/audio storage pattern. Org-configurable retention
- Org-configurable file size and page limits with sensible defaults (e.g., 50MB per file, 200 pages per doc)
- Supported formats: PDF, DOCX, images (with OCR)

### Claude's Discretion (Document Processing)
- Text extraction approach: library-based (PyMuPDF, python-docx, Tesseract), service-based (folio-enrich pipeline), or hybrid — determined during research
- OCR engine choice and configuration
- Document chunking strategy for multi-page documents

### Fact Extraction
- Per-message incremental extraction: facts extracted after each message/upload in conversation. LLM guiding the conversation uses already-extracted facts to ask better follow-up questions
- Legal-domain entity types: standard NER (people, dates, locations, amounts, organizations) PLUS legal-specific entities: party relationships (employer/employee, landlord/tenant), legal events (filing, service, injury), document references (contracts, leases), time periods (statute of limitations), claimed damages
- Leverage folio-enrich pipeline where useful for entity extraction and concept tagging
- Atomic decomposition: break narrative into smallest meaningful units (party relationship, event, amount, date, sequence, conditions) — each fact independently trackable for element mapping
- Source span tracking: every extracted fact links to its source with precise location — message ID + character offsets for chat, timestamp range for voice transcripts, page/paragraph for documents. Essential for Phase 9's narrative-anchored view
- Immediate concept resolution: as facts are extracted, they're passed to Phase 2's ConceptResolver for FOLIO IRI matching in real-time. Conversation LLM sees both raw facts AND matched FOLIO concepts for smarter follow-ups
- Dedicated LLM call for extraction: separate from conversation generation, specialized extraction prompt, can use cheaper/faster model, tunable independently
- Confidence scores on extracted facts with downstream impact: low-confidence facts enter pipeline but weighted lower in claim mapping, flagged for follow-up. Phase 4's gap analysis uses confidence
- Fact visibility: default to internal (professional review only), org-configurable for consumer-facing transparency
- Same-party conflict handling: latest version becomes active fact (append-only model), both preserved with timestamps. LLM can optionally ask for clarification on high-impact contradictions (dates, amounts) when the discrepancy matters for analysis

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — Project vision, FOLIO ecosystem context, tech stack constraints, all-modalities-from-day-one decision
- `.planning/REQUIREMENTS.md` — INGEST-01 through INGEST-06 requirements
- `.planning/ROADMAP.md` — Phase 3 success criteria and dependencies

### Prior phase context
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — Auth modes (including kiosk), tenant isolation, encryption, consent, per-org config patterns
- `.planning/phases/02-folio-ontology-integration/02-CONTEXT.md` — FOLIO integration patterns, concept resolution, adjacency (Phase 3 feeds into these)

### Existing codebase (Phase 1 + 2 foundation)
- `backend/app/services/llm_service.py` — LLMService with per-org config (reuse pattern for ASR provider config)
- `backend/app/models/shared.py` — Organization model with settings JSON field (use for intake config)
- `backend/app/services/folio/concept_resolver.py` — Concept resolution pipeline (downstream consumer of extracted facts, called in real-time per-message)
- `backend/app/config.py` — Application settings pattern

### FOLIO ecosystem (document/entity processing reference)
- `../folio-enrich/` — Document annotation engine with multi-format ingestion, entity extraction, and FOLIO concept tagging. Evaluate for reuse in document processing and fact extraction pipelines

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMService` (backend/app/services/llm_service.py): Per-org LLM provider/model config — reuse pattern for ASRService and fact extraction model config
- `Organization.settings` JSON field: Per-org config for intake settings (session mode, predefined questions, ASR provider, recording limits, document limits, fact visibility)
- `ConceptResolver` (backend/app/services/folio/concept_resolver.py): Multi-stage resolution pipeline — call in real-time as facts are extracted
- Tenant schema management: All intake data goes in tenant schemas
- Field-level PII encryption: Already built for narrative text, document contents, voice transcripts
- AuditMiddleware: Automatically logs intake actions

### Established Patterns
- Singleton services with lifespan integration (FOLIOService, EmbeddingService)
- Per-org configuration via Organization.settings
- FastAPI routers with role-based access control
- Async service layer with sync fallbacks via run_in_executor
- Provider class map pattern (_PROVIDER_MODEL_MAP in LLMService — replicate for ASR)

### Integration Points
- FastAPI lifespan: Add intake service initialization
- ConceptResolver: Downstream consumer — takes normalized text, returns FOLIO IRIs. Called per-message during extraction
- Existing routers: New intake router alongside auth, admin, folio_admin
- Tenant DB: New tables for intakes, sessions, messages, documents, audio recordings, extracted facts, source spans

</code_context>

<specifics>
## Specific Ideas

- LLM acts as orchestrator for intake questions — not just generating questions but deciding when org-defined predefined templates are appropriate for the consumer's situation
- Multi-party intakes with per-party fact attribution — critical for family law (custody disputes), business disputes, etc.
- Seamless modality mixing reflects real-world intake: someone types, then uploads a letter, then voice-describes events
- ASRService mirrors LLMService architecture — consistent per-org config pattern across all AI services
- Speaker diarization ties into multi-party tracking: voice recordings can identify different speakers, which maps to the per-party assertion model
- folio-enrich's entity extraction pipeline should be evaluated during research — it already handles multi-format ingestion and FOLIO concept tagging, may save significant implementation effort
- Atomic fact decomposition with source spans enables Phase 9's narrative-anchored view: every fact traces back to the exact words the consumer used

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-input-narrative-capture*
*Context gathered: 2026-03-24*
