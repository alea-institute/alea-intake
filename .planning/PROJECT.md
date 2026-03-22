# ALEA Intake

## What This Is

A configurable legal intake tool that transforms unstructured consumer narratives into structured legal analysis. The system captures a consumer's story (via text, voice, or documents), identifies legal issues using the FOLIO ontology, explores adjacent issues through safety screening and triage questioning, researches claims and their elements across jurisdictions, maps facts to legal claims, identifies gaps, and iteratively questions the consumer until diminishing returns. Deployable by law firms, courts, legal aid organizations, in-house counsel, and direct-to-consumer access-to-justice applications — each with configurable autonomy, privacy, output formats, and research tool integrations.

## Core Value

When a person describes a legal situation, the system must correctly identify all relevant legal issues — including ones the person doesn't know to mention — and produce a structured analysis mapping their facts to claims, elements, and authorities across applicable jurisdictions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Configurable per-org user modes: consumer-facing, professional-facing, or both
- [ ] All input modalities: text, voice/transcription, document upload, professional notes
- [ ] Flexible output per deployment: structured case memos, triage/routing, action items
- [ ] FOLIO ontology integration for issue-spotting (Objectives, Legal Authorities, Jurisdictions, Areas of Law)
- [ ] Pre-research exploration phase: safety screening, issue adjacency discovery, triage questioning
- [ ] Configurable mandatory safety screening protocols per organization
- [ ] Screening protocol library: open community-contributed protocols plus private org-specific protocols
- [ ] Three-layer issue exploration: FOLIO ontology relationships, curated screening protocols, LLM reasoning
- [ ] Configurable exploration depth (1 round to "until stable")
- [ ] Configurable transparency for exploration questions (explain rationale vs. conversational)
- [ ] Iterative analysis loop: issue-spot, research, fact-map, gap-analyze, question, loop
- [ ] Parallel multi-jurisdictional analysis
- [ ] Three fact-mapping views: graph (exploration), matrix (completeness), narrative-anchored (consumer understanding)
- [ ] Multi-signal loop termination: coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps
- [ ] Configurable autonomy: chatbot (fully autonomous), professional (human-guided), agent (AI with checkpoints)
- [ ] Pluggable legal research tools via MCP registry and HTTP adapters
- [ ] Ground truth verification: LLM suggestions verified against known databases before presentation
- [ ] Admin-configurable knowledge base with default RAG over curated legal documents
- [ ] Pluggable ASR: local (Whisper/faster-whisper) and cloud (Deepgram, AssemblyAI, etc.)
- [ ] Configurable persistence: ephemeral (privacy-first), persistent (case tracking), CMS-integrated
- [ ] CMS sync connectors: Clio, MyCase, Legal Server
- [ ] Maximum security: attorney-client privilege awareness, encryption at rest/in transit, field-level PII encryption, audit logs, consent flows, right-to-delete, no LLM training on case data
- [ ] Hybrid deployment: multi-tenant cloud AND single-tenant self-hosted
- [ ] Configurable database backend: PostgreSQL+pgvector (default), SQLite+FAISS (lightweight)

### Out of Scope

- Building the FOLIO ontology itself — that's the `folio` project
- Building legal research APIs (Westlaw, Lexis, CourtListener) — we consume them as pluggable services
- Replacing case management systems — we integrate with them, not replace them
- Providing legal advice — the system assists legal professionals and aids access to justice, but does not constitute legal advice

## Context

**FOLIO Ecosystem:** This project sits within the ALEA Institute's FOLIO (Federated Open Legal Information Ontology) ecosystem:
- **folio** — Core OWL ontology with 18,300+ standardized legal concepts across 22 taxonomic branches
- **folio-python** (v0.2.1) — Python client library with search, taxonomy navigation, LLM-powered semantic matching
- **folio-api** (v0.3.1) — Public REST API at folio.openlegalstandard.org
- **folio-insights** — Extracts advocacy knowledge (best practices, elements, pitfalls) from legal textbooks, mapped to FOLIO
- **folio-enrich** — Document annotation engine with multi-format ingestion and FOLIO concept tagging
- **folio-mapper** — Taxonomy mapping tool (React + FastAPI)
- **folio-mcp** — MCP server for FOLIO ontology tool-use by LLMs

**Key FOLIO Branches Used:**
- **Objectives** — Claims, defenses, counterclaims (what the consumer might pursue or face)
- **Legal Authorities** — Cases, statutes, regulations, rules, constitutional provisions
- **Location** — Jurisdictions (states, federal circuits, countries)
- **Area of Law** — Practice areas (family, employment, housing, consumer, etc.)
- **Forums and Venues** — Where cases can be filed

**Integration Pattern:** Hybrid approach — folio-python as direct library import for ontology queries, folio-enrich and folio-insights as HTTP services for heavy processing, folio-mcp for LLM agent tool-use during analysis, alea-llm-client for multi-provider LLM abstraction.

**Legal Research Tools:** The system integrates with both open (CourtListener, Google Scholar) and commercial (Westlaw, Clio Library, Midpage, Descrybe) legal research APIs via a pluggable adapter pattern and MCP tool registry. Organizations configure which tools they have access to.

**The Pre-Research Exploration Phase:** A distinctive feature of this system is a triage/exploration phase between initial issue-spotting and deep research. When the system identifies an issue (e.g., child custody), it uses three layers — FOLIO ontology relationships, curated screening protocols, and LLM reasoning — to explore adjacent issues the consumer may not know to mention (e.g., domestic violence, protective orders). This phase includes configurable mandatory safety screening and an open protocol library for sharing screening protocols across organizations.

## Constraints

- **Tech Stack**: FastAPI (backend) + React/Vite/Zustand/TypeScript/Tailwind (frontend) — consistent with FOLIO ecosystem patterns
- **LLM Provider**: Via alea-llm-client library — must support multiple providers without hard-coding any single one
- **Privacy**: All consumer data must be treated as potentially attorney-client privileged; no data may be sent to LLM training endpoints
- **Ontology**: Must use FOLIO IRIs as the canonical identifier for legal concepts — no parallel taxonomy
- **Deployment**: Must support both multi-tenant cloud and single-tenant self-hosted without codebase forks
- **Database**: Must abstract the storage layer to support both PostgreSQL+pgvector and SQLite+FAISS

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI + React (not SvelteKit) | Consistent with folio-mapper; broader React ecosystem for complex interactive views (graph, matrix) | — Pending |
| Hybrid integration (library + services + MCP) | folio-python is lightweight enough to embed; enrich/insights are heavy services; MCP enables LLM tool-use | — Pending |
| Pre-research exploration phase | Consumers don't know their legal issues; issue-spotting alone misses adjacent/urgent issues like DV in custody cases | — Pending |
| Three-layer exploration (FOLIO + protocols + LLM) | FOLIO edges provide ontological connections; curated protocols capture professional knowledge; LLM catches what both miss | — Pending |
| Open protocol library + private protocols | Community benefit of shared screening protocols (like FOLIO itself) while respecting org-specific practices | — Pending |
| Configurable autonomy per org | Law firms need professional control; legal aid needs consumer self-service; corporate needs agent efficiency | — Pending |
| All modalities from day one | Access to justice requires voice (not all consumers can type); document upload is table stakes for legal intake | — Pending |
| Multi-signal termination | Single thresholds fail; weighted combination of coverage, confidence, iterations, fatigue, and gap analysis is more robust | — Pending |
| Parallel jurisdictional research | Consumer situations routinely span jurisdictions; sequential analysis would be unacceptably slow | — Pending |
| Maximum security posture | Legal data is among the most sensitive; privilege awareness and encryption are non-negotiable, not nice-to-have | — Pending |
| Research all issues equally (no urgency gating) | Urgency affects output presentation and routing, but shouldn't prevent thorough analysis of any identified issue | — Pending |

---
*Last updated: 2026-03-22 after initialization*
