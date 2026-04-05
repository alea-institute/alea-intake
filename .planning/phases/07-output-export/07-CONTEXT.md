# Phase 7: Output & Export - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Structured output generation from the analysis pipeline — CIRAC-format case memos, multi-factor triage/routing recommendations, prioritized action items — with deployment-type profiles controlling content/language, gap analysis both inline and as appendix, and export to PDF/DOCX/JSON via a Markdown rendering pipeline.

</domain>

<decisions>
## Implementation Decisions

### Output Document Structure
- **D-01:** Case memo in CIRAC format — Conclusion (executive summary) first, then per-claim sections: Issue → Rule (authorities with binding/persuasive indicators) → Application (fact-to-element mapping with confidence) → Conclusion. Structured like a traditional legal brief. Grouped by jurisdiction for multi-jurisdiction cases.
- **D-02:** Multi-factor triage/routing with ranked recommendations. Score destinations by: (1) practice area match from FOLIO taxonomy, (2) jurisdiction match, (3) complexity/urgency assessment, (4) org-specific routing rules. Ranked list with scores and rationale.
- **D-03:** Prioritized action item checklist grouped by category: (1) Documents to gather, (2) Follow-up steps with deadlines, (3) Referrals. Each item has priority (urgent/important/helpful), deadline if applicable, and the claim/element it supports.

### Deployment-Type Configuration
- **D-04:** Template profiles with section visibility rules. Three built-in profiles:
  - **law_firm**: Full CIRAC memo + all authorities + detailed action items + professional legal language
  - **legal_aid**: Triage routing + simplified memo + referrals + accessible language with legal terms explained
  - **court_self_help**: Plain-language guidance (~8th grade reading level) + forms checklist + next steps
  Org selects profile + can customize section visibility.
- **D-05:** LLM adapts language complexity per profile. Law firm = professional legal language with citations. Legal aid = accessible with terms explained. Court self-help = plain language at ~8th grade level.
- **D-06:** A single matter can generate multiple output profiles simultaneously. E.g., lawyer gets full CIRAC memo AND consumer gets plain-language version of the same analysis. Multiple profiles are first-class, not a workaround.

### Gap Analysis in Output
- **D-07:** Actionable gap summary per claim (inline) AND a consolidated Gap Report Appendix. Within each claim's CIRAC section: "Gaps & Open Questions" subsection lists unsupported elements, unanswered questions, weak mappings — each linking to an action item. Appendix consolidates all gaps for easy review/remedy. Executive summary includes overall completeness score.

### Export Formats & Rendering
- **D-08:** Markdown → rendering pipeline. Generate output as structured Markdown (canonical format). Render to: PDF via WeasyPrint (CSS-styled HTML→PDF), DOCX via python-docx (already installed), JSON as structured data matching internal schema. Markdown is single source of truth; renderers are output adapters.
- **D-09:** Professional legal formatting. PDF/DOCX follow legal document conventions: numbered paragraphs, Bluebook citation formatting, table of contents for long documents, headers/footers with matter info. Configurable org branding (logo, colors) via org settings.

### Claude's Discretion
- Specific CIRAC section templates and Markdown structure
- Triage scoring algorithm weights and defaults
- WeasyPrint CSS stylesheet design
- TOC generation logic for long documents
- Org branding configuration schema

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — Analysis models: AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap, FollowUpQuestion
- `.planning/phases/06-legal-research-verification/06-CONTEXT.md` — ResearchAuthority, citation verification, FOLIO Legal Authority taxonomy (D-16/D-17)

### Existing Code
- `backend/app/models/analysis.py` — Analysis DB models (claims, elements, mappings, gaps, questions)
- `backend/app/models/research.py` — ResearchAuthority, CitationVerification models
- `backend/app/services/analysis/orchestrator.py` — AnalysisOrchestrator (source of analysis results)
- `backend/app/services/research/result_ranker.py` — ResultRanker for authority ordering
- `backend/app/services/llm_service.py` — LLMService for language adaptation
- `backend/app/services/document/document_service.py` — DocumentService (python-docx already available)

### Requirements
- `.planning/REQUIREMENTS.md` §Output & Export — OUTPUT-01 through OUTPUT-05, INTEGRATE-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **python-docx**: Already installed (Phase 3 document extraction) — reuse for DOCX export
- **LLMService**: Multi-provider LLM — use for language adaptation per output profile
- **ResultRanker**: Multi-signal authority ranking — reuse for ordering authorities in memo
- **Analysis models**: Full claim/element/fact/gap/question graph available via SQLAlchemy queries

### Established Patterns
- Service classes with dependency injection
- Pydantic schemas for structured data contracts
- Admin API routers for org configuration
- Per-org settings on Organization model

### Integration Points
- Output generation triggered after analysis convergence (orchestrator completion)
- Output stored as DB records (OutputDocument model) with rendered content
- Export endpoints on existing or new router
- Multiple profiles generated simultaneously per matter

</code_context>

<specifics>
## Specific Ideas

- CIRAC format mirrors traditional legal briefs — familiar to attorneys
- Multiple output profiles per matter is first-class (lawyer + consumer versions)
- Gap Report Appendix consolidates all gaps from inline sections for easy review
- Overall completeness score in executive summary gives at-a-glance assessment

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-output-export*
*Context gathered: 2026-04-04*
