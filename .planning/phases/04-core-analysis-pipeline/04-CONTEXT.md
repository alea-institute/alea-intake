# Phase 4: Core Analysis Pipeline - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

The iterative analysis engine that takes extracted facts (from Phase 3) and FOLIO concept resolution (from Phase 2), maps them to legal claims and their elements across jurisdictions, identifies gaps, generates consumer-friendly follow-up questions, and loops until multi-signal convergence. Produces a complete mapping of consumer facts → legal claims → elements → gaps → authorities.

</domain>

<decisions>
## Implementation Decisions

### Analysis Loop Architecture
- **D-01:** Single LLM orchestrator per iteration — one LLM call decides which stage to run next (agent-loop pattern). Stages: issue-spot → research → fact-map → gap-analyze → question. Orchestrator can skip irrelevant stages or re-run stages as needed.
- **D-02:** Hybrid execution model — initial issue-spotting runs inline for fast feedback, then deeper analysis (research, mapping, gap analysis) runs as an async background job. WebSocket pushes stage-by-stage progress updates. Consumer can continue chatting while analysis proceeds.
- **D-03:** DB-persisted stage snapshots for checkpointing — after each stage completes, save the full analysis state (current iteration, stage results, mappings, gaps) to dedicated DB models. Resume by loading the latest snapshot. Clean audit trail per ANALYSIS-09/ANALYSIS-10.
- **D-04:** Dual trigger model — auto-triggers when N new facts accumulate since last analysis (threshold configurable per org), plus manual trigger available to consumer/professional at any time. Auto-trigger can be disabled per org.

### Fact-to-Claim Mapping
- **D-05:** Multi-factor composite confidence scoring — combine: (1) LLM mapping confidence, (2) FOLIO ConceptResolver match strength, (3) source fact confidence. Weighted composite with org-configurable weights.
- **D-06:** Parallel per-jurisdiction analysis — when facts span jurisdictions, run separate analysis branches in parallel. Each jurisdiction gets its own claim/element/authority mappings. Results merged in output with jurisdiction labels.
- **D-07:** Dedicated mapping tables — AnalysisClaim, ClaimElement, FactClaimMapping DB models with many-to-many relationships, confidence scores, jurisdiction metadata, and iteration tracking. Matches existing model pattern (ExtractedFact, FactSourceSpan).
- **D-08:** Discovered claims surfaced as "potential claims" with explanation — claims the system discovers that weren't in the consumer's narrative are shown separately with a clear rationale. Consumer/professional decides whether to pursue. Aligns with the pre-research exploration philosophy.

### Gap Analysis & Follow-Up Questions
- **D-09:** Four gap types detected — unsupported elements (claim elements with no fact), unexplored claims (discovered but not investigated), weak mappings (low confidence), and procedural requirements (deadlines, filing requirements).
- **D-10:** LLM generates consumer-friendly questions grouped by topic — LLM takes gap list + consumer context and generates natural-language questions grouped by topic area (e.g., "about the timeline", "about your employment"). Questions ranked by priority (highest-impact gaps first).
- **D-11:** All gaps presented as questions per iteration — consumer answers what they can, skips what they can't. Remaining gaps carry to next iteration. No artificial cap on question count.
- **D-12:** Question rationale is configurable per org — transparency setting controls whether questions include explanations of why they're being asked ("We're asking because your employment claim requires proving termination date") or stay conversational.

### Convergence & Termination
- **D-13:** All five convergence signals, weighted — coverage % (elements with facts), confidence plateau (scores stop improving), iteration count (hard cap), user fatigue (skip rate, response time), diminishing gaps (fewer new gaps per iteration). Weighted combination with org-configurable thresholds.
- **D-14:** Default iteration hard cap: 10 iterations — most cases converge in 3-5. Configurable per org.
- **D-15:** Progressive confidence indicator + summary at termination — real-time progress indicator during iterations, comprehensive summary when convergence reached. Consumer always knows where things stand.
- **D-16:** Consumer and professional can override termination — after convergence, consumer can say "I have more to add" or "keep digging." Resets some convergence signals and continues. Professional can also override.

### Claude's Discretion
- Specific DB schema details for analysis state models (builds on existing patterns)
- LLM prompt design for the orchestrator, gap analysis, and question generation
- Convergence signal weight defaults and fatigue detection heuristics
- Stage-to-stage data flow serialization format
- Background job framework choice (existing async patterns vs. task queue)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/03-input-narrative-capture/03-CONTEXT.md` — Fact extraction decisions, NormalizedContent pipeline, append-only correction model
- `.planning/phases/02-folio-ontology-integration/02-CONTEXT.md` — ConceptResolver pipeline, FOLIO loading, adjacency discovery
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — Auth, encryption, audit patterns, DB engine

### Existing Code
- `backend/app/services/extraction/fact_extraction.py` — FactExtractionService with LLM call and ConceptResolver wiring
- `backend/app/services/folio/concept_resolver.py` — resolve_concepts() for FOLIO IRI matching
- `backend/app/services/folio/adjacency.py` — Graph-based adjacency discovery
- `backend/app/services/llm_service.py` — LLMService with per-org config and training opt-out
- `backend/app/services/intake/session_service.py` — IntakeSessionService for message/session management
- `backend/app/models/fact.py` — ExtractedFact, FactSourceSpan models
- `backend/app/routers/intake.py` — WebSocket endpoint with manager for real-time updates

### Requirements
- `.planning/REQUIREMENTS.md` §Analysis Engine — ANALYSIS-01 through ANALYSIS-10

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FactExtractionService** (`extraction/fact_extraction.py`): Already extracts atomic facts with LLM calls and ConceptResolver wiring — analysis pipeline consumes these facts
- **ConceptResolver** (`folio/concept_resolver.py`): Three-stage resolution (embedding, label, LLM) with confidence scores — reuse for claim-to-FOLIO mapping
- **LLMService** (`llm_service.py`): Per-org provider config with alea-llm-client — use for orchestrator and gap analysis LLM calls
- **IntakeConnectionManager** (`routers/intake.py`): WebSocket manager with send_to_session — use for pushing analysis progress updates
- **IntakeSessionService** (`intake/session_service.py`): Message storage with sequence numbers — use for storing follow-up questions

### Established Patterns
- **DB models**: SQLAlchemy declarative with LargeBinary encrypted fields, JSON columns for metadata
- **Service pattern**: Stateless service classes initialized with DB session and optional config
- **Async**: All DB operations via async SQLAlchemy sessions
- **Testing**: pytest-asyncio with aiosqlite in-memory, mocked LLM calls

### Integration Points
- Analysis pipeline triggers from fact extraction output (post-message or manual trigger)
- WebSocket sends progress updates via existing IntakeConnectionManager
- Follow-up questions stored as Messages with sender_type="system" in existing intake router
- Analysis results consumed by Phase 5 (pre-research exploration) and Phase 7 (output/export)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches based on the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-core-analysis-pipeline*
*Context gathered: 2026-04-03*
