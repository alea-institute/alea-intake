# Phase 3: Input & Narrative Capture - Context

**Gathered:** 2026-03-24
**Status:** In progress — Chat interaction model discussed, 3 areas remaining

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
- (Not yet discussed)

### Document Processing
- (Not yet discussed)

### Fact Extraction
- (Not yet discussed)

### Claude's Discretion
- (To be determined after remaining areas discussed)

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
- `backend/app/services/folio/concept_resolver.py` — Concept resolution pipeline (downstream consumer of extracted facts)
- `backend/app/config.py` — Application settings pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMService` (backend/app/services/llm_service.py): Per-org LLM provider/model config — reuse pattern for ASR and question generation
- `Organization.settings` JSON field: Per-org config for intake settings (session mode, predefined questions, ASR provider)
- Tenant schema management: All intake data goes in tenant schemas
- Field-level PII encryption: Already built for narrative text, document contents, voice transcripts
- AuditMiddleware: Automatically logs intake actions

### Established Patterns
- Singleton services with lifespan integration (FOLIOService, EmbeddingService)
- Per-org configuration via Organization.settings
- FastAPI routers with role-based access control
- Async service layer with sync fallbacks via run_in_executor

### Integration Points
- FastAPI lifespan: Add intake service initialization
- ConceptResolver: Downstream consumer — takes normalized text, returns FOLIO IRIs
- Existing routers: New intake router alongside auth, admin, folio_admin
- Tenant DB: New tables for intakes, messages, documents, facts

</code_context>

<specifics>
## Specific Ideas

- LLM acts as orchestrator for intake questions — not just generating questions but deciding when org-defined predefined templates are appropriate for the consumer's situation
- Multi-party intakes with per-party fact attribution — critical for family law (custody disputes), business disputes, etc.
- Seamless modality mixing reflects real-world intake: someone types, then uploads a letter, then voice-describes events

</specifics>

<deferred>
## Deferred Ideas

None yet — discussion still in progress

</deferred>

---

*Phase: 03-input-narrative-capture*
*Context gathered: 2026-03-24 (in progress — 3 areas remaining: Voice/ASR, Document processing, Fact extraction)*
