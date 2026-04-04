# Phase 6: Legal Research & Verification - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Pluggable legal research tool system that queries external sources for authorities supporting identified claims, verifies all citations against known databases, integrates with the full ALEA Institute ecosystem (folio-insights, folio-enrich, folio-mcp, and others), and provides org-specific knowledge bases with RAG. Replaces the Phase 4 research_stub.py with a real ResearchStage.

</domain>

<decisions>
## Implementation Decisions

### Research Tool Adapter Architecture
- **D-01:** Dual-mode adapters: MCP + HTTP with unified ResearchToolAdapter ABC. `query()` method returns common ResearchResult schema. MCPAdapter wraps folio-mcp tool calls. HTTPAdapter wraps direct HTTP calls to CourtListener, Westlaw, etc. Both return the same schema.
- **D-02:** Platform-level tool registry AND org-level tool activation. Platform admin defines available tools globally with pre-registered adapters. Orgs bring their own tools by providing credentials via admin API. Free/open tools (CourtListener, Google Scholar) work out of the box. Commercial tools (Westlaw, Clio Library, Midpage, Descrybe) require org-provided API keys.
- **D-03:** All mentioned tools ship as adapter stubs in platform registry: CourtListener, Google Scholar (free, pre-configured), Westlaw, Clio Library, Midpage, Descrybe (require org credentials). Org admins can add any research database by providing adapter type + endpoint + credentials.
- **D-04:** ResearchStage replaces research_stub.py in the analysis orchestrator. Queries all org-configured tools in parallel (asyncio.gather), merges results, runs citation verification, stores ResearchAuthority records. Research results feed back into gap analysis for re-iteration — research-discovered gaps generate new questions.

### Citation Verification Pipeline
- **D-05:** Multi-source verification with confidence. Every authority citation checked against: (1) CourtListener/RECAP (case law), (2) congress.gov/state legislature sites (statutes), (3) folio-insights citation index if available. Multiple verifications increase confidence. Unverifiable citations flagged but included with "unverified — could not confirm via [sources checked]" warning.
- **D-06:** Local citation cache (ResearchAuthority DB table) with live refresh. Store verified citations with: citation string, verification_status, verification_source, verified_at, jurisdiction, authority_type. Reuse across intakes. Cache returns immediate results; live API query runs in parallel for freshness. New/different results merged in.

### FOLIO Ecosystem Integration
- **D-07:** Researcher must survey ALL repos at github.com/alea-institute/ to identify integration opportunities for Phase 6. Known integrations: folio-insights (practical/secondary knowledge), folio-enrich (document annotation pipeline), folio-mcp (LLM agent tool), folio-api (REST API), folio-python (library). Other tools integrated as applicable.
- **D-08:** Research tools (cases, statutes, regulations) are PRIMARY authority for legal elements. folio-insights provides SECONDARY/PRACTICAL knowledge (advocacy tips, best practices, pitfalls, "don't speak when the judge is speaking"). Hierarchy: primary sources > secondary sources.
- **D-09:** folio-enrich pipeline reused (not just called as API) with two modes: (1) end-user-facing: backend pipeline only, annotations improve user experience invisibly; (2) org-facing: UI-visible annotations for precision/recall validation by org admins.
- **D-10:** folio-mcp integrated as LLM agent tool in the analysis orchestrator. LLM calls include folio-mcp tools in tool schema. When LLM needs ontology info (e.g., "elements of negligence in California"), it makes MCP tool calls to folio-mcp. Used during issue-spotting, exploration, and research stages.

### Knowledge Base & RAG
- **D-11:** Dual-backend RAG reusing Phase 2 EmbeddingService (FAISS/pgvector). Per-org vector index for tenant isolation. Upload → extract → chunk → FOLIO-tag → embed → index.
- **D-12:** Extended format support: PDF, DOCX, images (reuse Phase 3 extractors) + HTML and plain text.
- **D-13:** Semantic chunking with overlap (~500 tokens, 50-token overlap). Respect section boundaries (headings, paragraphs). FOLIO concept tagging on chunk headings — headings containing FOLIO-tagged terms (e.g., "Complaint", "Lease", "Arrest") create strong retrieval signals. Dual retrieval: vector similarity + FOLIO IRI matching for ontology-grounded boosting.
- **D-14:** Full document lifecycle: upload → extract → chunk → FOLIO-tag → embed → index. On update: re-extract, re-chunk, re-embed (incremental if possible). On delete: remove chunks from index + DB. Bulk import via ZIP/folder. Version tracking per document.

### Research Result Ranking & Deduplication
- **D-15:** Multi-signal relevance scoring. Deduplicate by citation string normalization. Score by: (1) relevance to claim elements, (2) recency (newer authorities weighted higher), (3) jurisdictional match (same jurisdiction > persuasive), (4) court level (Supreme > Appeals > Trial), (5) verification confidence. LLM re-ranks final list for presentation.

### Authority Type Taxonomy
- **D-16:** FOLIO Legal Authority branch as canonical taxonomy: Case Law, Statutes, Regulations, Constitutional Provisions, Administrative Rulings, Court Rules, Executive Orders, Treaties, Model Codes, Restatements, Secondary Sources. Each type gets default weight (binding > persuasive > secondary). Jurisdiction + court level further refine weight.
- **D-17:** Output groups authorities by type (statutes first, then case law, then secondary). Each shows: binding vs persuasive for the relevant jurisdiction, verification status, relevance score. Binding authorities from correct jurisdiction highlighted.

### Rate Limiting & Cost Control
- **D-18:** Per-org usage tracking with configurable budget caps. Track API call counts and estimated costs per org per tool. Monthly budget caps per tool — when reached, tool disabled for remainder of period. Free tools exempt. Usage visible in admin dashboard.
- **D-19:** TTL cache per (query_hash, tool_name, jurisdiction) — default 24h for case law, 7d for statutes. Cache returns immediate results; live API query runs in parallel for freshness. New/different results from live query merged in.

### Claude's Discretion
- Specific adapter implementation details for each research tool
- Citation string normalization algorithm (Bluebook format parsing)
- folio-enrich pipeline reuse architecture details
- KB chunk size tuning and overlap optimization
- MCP client implementation for folio-mcp tool calls
- Rate limiting implementation (token bucket, sliding window, etc.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — Analysis orchestrator, stage architecture, research_stub.py to replace
- `.planning/phases/05-pre-research-exploration-safety/05-CONTEXT.md` — Exploration engine, screening protocols
- `.planning/phases/02-folio-ontology-integration/02-CONTEXT.md` — ConceptResolver, FOLIO loading, EmbeddingService

### ALEA Institute Ecosystem (researcher MUST survey)
- `https://github.com/alea-institute/` — All ALEA Institute repos for integration opportunities
- Known repos: folio, folio-python, folio-api, folio-insights, folio-enrich, folio-mcp, folio-mapper, alea-llm-client

### Existing Code
- `backend/app/services/analysis/stages/research_stub.py` — Stub to be replaced by real ResearchStage
- `backend/app/services/analysis/orchestrator.py` — Analysis orchestrator (integration point)
- `backend/app/services/embedding/service.py` — EmbeddingService for KB RAG
- `backend/app/services/document/document_service.py` — Document extraction pipeline (reuse for KB)
- `backend/app/services/llm_service.py` — LLMService for LLM calls
- `backend/app/services/folio/concept_resolver.py` — ConceptResolver for FOLIO IRI matching

### Requirements
- `.planning/REQUIREMENTS.md` §Legal Research & Verification — RESEARCH-01 through RESEARCH-10, INTEGRATE-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **EmbeddingService** (`embedding/service.py`): Dual FAISS/pgvector backend — reuse for KB embeddings
- **DocumentService** (`document/document_service.py`): PDF/DOCX/OCR extraction — reuse for KB document processing
- **ConceptResolver** (`folio/concept_resolver.py`): FOLIO IRI matching — use for chunk FOLIO-tagging
- **research_stub.py**: Placeholder stage — replace with real ResearchStage following same interface
- **LLMService**: Multi-provider LLM — use for citation verification and result re-ranking
- **AnalysisOrchestrator**: Stage loop with STAGES list — add real research stage

### Established Patterns
- Stage classes with `execute()` method, Pydantic schema I/O
- Org-configurable settings via Organization.settings JSON
- Admin API routers following folio_admin/screening_admin pattern
- AsyncSession for DB operations, asyncio.gather for parallelism

### Integration Points
- ResearchStage replaces research_stub in orchestrator's STAGES list
- KB admin endpoints follow existing admin router pattern
- Citation verification hooks into the research result pipeline
- folio-mcp client integrated into orchestrator's LLM tool schema

</code_context>

<specifics>
## Specific Ideas

- Research tools are PRIMARY authority; folio-insights is SECONDARY/PRACTICAL (advocacy tips, not legal elements)
- FOLIO concept tagging on KB chunk headings creates dual-signal retrieval (vector + ontology)
- folio-enrich pipeline reused with two modes: invisible backend (end-user) and visible UI annotations (org admin)
- Cache + live refresh pattern: cached results shown immediately, live query runs in parallel for freshness
- Researcher must survey ALL alea-institute repos, not just known tools

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-legal-research-verification*
*Context gathered: 2026-04-04*
