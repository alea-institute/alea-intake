# Requirements: ALEA Intake

**Defined:** 2026-03-22
**Core Value:** When a person describes a legal situation, the system must correctly identify all relevant legal issues — including ones the person doesn't know to mention — and produce a structured analysis mapping their facts to claims, elements, and authorities across applicable jurisdictions.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Input & Narrative Capture

- [x] **INGEST-01**: Consumer can submit narrative text via conversational chat interface
- [x] **INGEST-02**: Consumer can record voice input that is transcribed via pluggable ASR (local Whisper or cloud providers)
- [x] **INGEST-03**: Consumer can upload documents (PDF, DOCX, images) for text extraction and analysis
- [x] **INGEST-04**: Professional can enter notes on behalf of a consumer
- [x] **INGEST-05**: System normalizes all input modalities into a common text representation for analysis
- [x] **INGEST-06**: System extracts atomic factual assertions from narrative (parties, dates, locations, amounts, events)

### FOLIO Ontology Integration

- [x] **FOLIO-01**: System loads FOLIO ontology via folio-python and uses IRIs as canonical identifiers for all legal concepts
- [x] **FOLIO-02**: System maps consumer facts to FOLIO Objectives (Claims, Defenses) via LLM + ontology matching
- [x] **FOLIO-03**: System identifies applicable Areas of Law from FOLIO taxonomy
- [x] **FOLIO-04**: System identifies applicable Legal Authorities types from FOLIO taxonomy
- [x] **FOLIO-05**: System determines applicable Jurisdictions from FOLIO Location branch
- [x] **FOLIO-06**: System gracefully handles concepts not in FOLIO (flags as "unmapped" rather than dropping)
- [x] **FOLIO-07**: System uses FOLIO ontology relationships (OWL object properties) to discover adjacent legal concepts

### Pre-Research Exploration & Safety

- [x] **EXPLORE-01**: System performs pre-research exploration between issue-spotting and research phases
- [x] **EXPLORE-02**: Exploration uses three layers: FOLIO ontology relationships, curated screening protocols, and LLM reasoning
- [x] **EXPLORE-03**: Organizations can define mandatory safety screening protocols that run before analysis proceeds
- [ ] **EXPLORE-04**: Safety screening is continuous throughout the conversation, not just at intake start
- [x] **EXPLORE-05**: Exploration depth is configurable per organization (1 round to "until stable")
- [x] **EXPLORE-06**: System explains why it's asking exploration questions (configurable transparency per org)
- [x] **EXPLORE-07**: Open screening protocol library allows community-contributed protocols across organizations
- [x] **EXPLORE-08**: Organizations can create private screening protocols not shared with the library
- [x] **EXPLORE-09**: Default DV screening protocol ships with the system for family law matters
- [x] **EXPLORE-10**: Exploration can surface entirely new legal issues not in the initial issue-spotting (e.g., DV in custody cases)

### Legal Research & Verification

- [x] **RESEARCH-01**: System queries pluggable legal research tools via MCP tool registry and HTTP adapters
- [x] **RESEARCH-02**: Organizations configure which research tools they have access to (CourtListener, Westlaw, Clio Library, Midpage, Descrybe)
- [x] **RESEARCH-03**: System integrates with folio-insights for advocacy knowledge (elements, best practices, pitfalls)
- [x] **RESEARCH-04**: System integrates with folio-enrich for document annotation and concept extraction
- [x] **RESEARCH-05**: For each identified claim, system researches required legal elements per jurisdiction
- [x] **RESEARCH-06**: System finds relevant case law, statutes, regulations, and constitutional provisions
- [x] **RESEARCH-07**: Ground truth verification: LLM suggestions verified against known databases before presentation
- [x] **RESEARCH-08**: Each authority gets a verified/unverified flag with verification source
- [x] **RESEARCH-09**: Admin-configurable knowledge base with RAG over curated legal documents
- [x] **RESEARCH-10**: Organizations can upload custom documents to their knowledge base

### Analysis Engine

- [x] **ANALYSIS-01**: System performs iterative analysis loop: issue-spot → research → fact-map → gap-analyze → question → loop
- [x] **ANALYSIS-02**: System maps facts to claims and elements in a many-to-many relationship with confidence scores
- [x] **ANALYSIS-03**: System identifies gaps: unsupported elements, unexplored claims, weak mappings, procedural requirements
- [x] **ANALYSIS-04**: System generates prioritized, consumer-friendly follow-up questions to fill gaps
- [x] **ANALYSIS-05**: Questions are grouped by topic to reduce consumer fatigue
- [x] **ANALYSIS-06**: Multi-signal loop termination: coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps
- [x] **ANALYSIS-07**: Termination weights and thresholds are configurable per organization
- [x] **ANALYSIS-08**: System performs parallel multi-jurisdictional analysis when facts span jurisdictions
- [x] **ANALYSIS-09**: Analysis state is checkpointed after every stage for pause/resume across sessions
- [x] **ANALYSIS-10**: Full audit trail: every stage records what was analyzed, what sources were consulted, what confidence was assigned

### Output & Export

- [x] **OUTPUT-01**: System generates structured case memos mapping facts → claims → elements → authorities → jurisdictions
- [x] **OUTPUT-02**: System generates triage/routing recommendations (which practice area, which attorney, which program)
- [x] **OUTPUT-03**: System generates action items (documents to gather, follow-up steps, referrals)
- [x] **OUTPUT-04**: Output format is configurable per deployment (law firms get memos, legal aid gets triage, courts get self-help routing)
- [x] **OUTPUT-05**: Output includes gap analysis showing what evidence is missing and what questions remain

### Frontend Visualization

- [x] **FRONTEND-01**: React frontend with conversational chat interface for intake
- [x] **FRONTEND-02**: Real-time analysis progress via WebSocket/SSE streaming
- [x] **FRONTEND-03**: Graph fact-mapping view: force-directed visualization of facts, claims, elements, and their relationships
- [x] **FRONTEND-04**: Matrix fact-mapping view: fact × element completeness matrix showing coverage
- [x] **FRONTEND-05**: Narrative-anchored fact-mapping view: consumer's original narrative with overlaid analysis annotations
- [x] **FRONTEND-06**: Intake dashboard listing all intakes with status and progress
- [x] **FRONTEND-07**: Output display with export capabilities
- [x] **FRONTEND-08**: Admin configuration interface for org settings, research tools, KB management, screening protocols
- [x] **FRONTEND-09**: Mobile-responsive design
- [x] **FRONTEND-10**: Voice recording UI component for voice input

### Autonomy & Configuration

- [x] **AUTONOMY-01**: Chatbot mode: AI runs all steps autonomously, presents questions directly to consumer
- [x] **AUTONOMY-02**: Professional mode: AI suggests at each stage, human professional approves before proceeding
- [x] **AUTONOMY-03**: Agent mode: AI orchestrates autonomously, pauses at configurable checkpoints for human review
- [x] **AUTONOMY-04**: Autonomy level is configurable per organization
- [x] **AUTONOMY-05**: Per-org configuration of which analysis stages require human approval in agent mode

### Security & Privacy

- [x] **SECURITY-01**: JWT authentication with refresh tokens
- [x] **SECURITY-02**: Role-based access control: admin, professional (attorney/paralegal), consumer
- [x] **SECURITY-03**: AES-256 encryption at rest, TLS 1.3 in transit
- [x] **SECURITY-04**: Field-level encryption for PII data
- [x] **SECURITY-05**: Immutable audit log of all actions, AI decisions, human overrides, and data access
- [x] **SECURITY-06**: Attorney-client privilege awareness: all data treated as potentially privileged
- [x] **SECURITY-07**: Consent capture before AI processing begins, with granular consent options
- [x] **SECURITY-08**: Right-to-delete with cascade deletion and anonymized audit trail preservation
- [x] **SECURITY-09**: No case data sent to LLM training endpoints; configurable data residency
- [x] **SECURITY-10**: Multi-tenant data isolation (beyond RLS alone)

### Deployment & Infrastructure

- [x] **DEPLOY-01**: Configurable database backend: PostgreSQL+pgvector (default) and SQLite+FAISS (lightweight)
- [ ] **DEPLOY-02**: Multi-tenant cloud deployment with org-scoped data isolation
- [ ] **DEPLOY-03**: Single-tenant self-hosted deployment option
- [x] **DEPLOY-04**: Docker containers for backend and frontend
- [ ] **DEPLOY-05**: Configurable persistence: ephemeral (privacy-first), persistent (case tracking), CMS-integrated
- [x] **DEPLOY-06**: Health check and monitoring endpoints

### Integration

- [x] **INTEGRATE-01**: CMS sync connector for Clio
- [x] **INTEGRATE-02**: CMS sync connector for MyCase
- [x] **INTEGRATE-03**: CMS sync connector for Legal Server
- [x] **INTEGRATE-04**: LLM integration via alea-llm-client supporting multiple providers
- [x] **INTEGRATE-05**: folio-mcp integration for LLM agent tool-use during analysis
- [x] **INTEGRATE-06**: Export formats: PDF, DOCX, JSON

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended Features

- **LANG-01**: Multi-language support (Spanish first, then extensible)
- **LANG-02**: Multilingual ASR configuration
- **GOV-01**: Full protocol library governance (versioning, review workflows, quality scoring)
- **PREDICT-01**: Strength-of-claim scoring based on element coverage and authority support

## Out of Scope

| Feature | Reason |
|---------|--------|
| Legal advice generation | UPL liability; system provides legal information and analysis, not advice |
| Autonomous case filing | Malpractice liability; procedural errors have severe consequences |
| Real-time collaborative editing | CRDT/OT complexity for minimal value at intake stage |
| Predictive case outcome analysis | Unreliable, creates false confidence |
| Video conferencing | Commoditized (Zoom/Teams); support transcript import instead |
| Payment processing / billing | CMS handles billing; adds PCI compliance burden |
| Marketing automation / lead scoring | Not aligned with access-to-justice mission |
| Social media / public records scraping | Privacy law violations, ethical concerns |
| Replacing case management systems | Integrate with CMS, never replace |
| Urgency-gated research depth | Research all issues equally; urgency affects output, not thoroughness |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 3 | Complete |
| INGEST-02 | Phase 3 | Complete |
| INGEST-03 | Phase 3 | Complete |
| INGEST-04 | Phase 3 | Complete |
| INGEST-05 | Phase 3 | Complete |
| INGEST-06 | Phase 3 | Complete |
| FOLIO-01 | Phase 2 | Complete |
| FOLIO-02 | Phase 2 | Complete |
| FOLIO-03 | Phase 2 | Complete |
| FOLIO-04 | Phase 2 | Complete |
| FOLIO-05 | Phase 2 | Complete |
| FOLIO-06 | Phase 2 | Complete |
| FOLIO-07 | Phase 2 | Complete |
| EXPLORE-01 | Phase 5 | Complete |
| EXPLORE-02 | Phase 5 | Complete |
| EXPLORE-03 | Phase 5 | Complete |
| EXPLORE-04 | Phase 5 | Pending |
| EXPLORE-05 | Phase 5 | Complete |
| EXPLORE-06 | Phase 5 | Complete |
| EXPLORE-07 | Phase 5 | Complete |
| EXPLORE-08 | Phase 5 | Complete |
| EXPLORE-09 | Phase 5 | Complete |
| EXPLORE-10 | Phase 5 | Complete |
| RESEARCH-01 | Phase 6 | Complete |
| RESEARCH-02 | Phase 6 | Complete |
| RESEARCH-03 | Phase 6 | Complete |
| RESEARCH-04 | Phase 6 | Complete |
| RESEARCH-05 | Phase 6 | Complete |
| RESEARCH-06 | Phase 6 | Complete |
| RESEARCH-07 | Phase 6 | Complete |
| RESEARCH-08 | Phase 6 | Complete |
| RESEARCH-09 | Phase 6 | Complete |
| RESEARCH-10 | Phase 6 | Complete |
| ANALYSIS-01 | Phase 4 | Complete |
| ANALYSIS-02 | Phase 4 | Complete |
| ANALYSIS-03 | Phase 4 | Complete |
| ANALYSIS-04 | Phase 4 | Complete |
| ANALYSIS-05 | Phase 4 | Complete |
| ANALYSIS-06 | Phase 4 | Complete |
| ANALYSIS-07 | Phase 4 | Complete |
| ANALYSIS-08 | Phase 4 | Complete |
| ANALYSIS-09 | Phase 4 | Complete |
| ANALYSIS-10 | Phase 4 | Complete |
| OUTPUT-01 | Phase 7 | Complete |
| OUTPUT-02 | Phase 7 | Complete |
| OUTPUT-03 | Phase 7 | Complete |
| OUTPUT-04 | Phase 7 | Complete |
| OUTPUT-05 | Phase 7 | Complete |
| FRONTEND-01 | Phase 8 | Complete |
| FRONTEND-02 | Phase 8 | Complete |
| FRONTEND-03 | Phase 9 | Complete |
| FRONTEND-04 | Phase 9 | Complete |
| FRONTEND-05 | Phase 9 | Complete |
| FRONTEND-06 | Phase 8 | Complete |
| FRONTEND-07 | Phase 8 | Complete |
| FRONTEND-08 | Phase 8 | Complete |
| FRONTEND-09 | Phase 8 | Complete |
| FRONTEND-10 | Phase 8 | Complete |
| AUTONOMY-01 | Phase 10 | Complete |
| AUTONOMY-02 | Phase 10 | Complete |
| AUTONOMY-03 | Phase 10 | Complete |
| AUTONOMY-04 | Phase 10 | Complete |
| AUTONOMY-05 | Phase 10 | Complete |
| SECURITY-01 | Phase 1 | Complete |
| SECURITY-02 | Phase 1 | Complete |
| SECURITY-03 | Phase 1 | Complete |
| SECURITY-04 | Phase 1 | Complete |
| SECURITY-05 | Phase 1 | Complete |
| SECURITY-06 | Phase 1 | Complete |
| SECURITY-07 | Phase 1 | Complete |
| SECURITY-08 | Phase 1 | Complete |
| SECURITY-09 | Phase 1 | Complete |
| SECURITY-10 | Phase 1 | Complete |
| DEPLOY-01 | Phase 1 | Complete |
| DEPLOY-02 | Phase 11 | Pending |
| DEPLOY-03 | Phase 11 | Pending |
| DEPLOY-04 | Phase 1 | Complete |
| DEPLOY-05 | Phase 11 | Pending |
| DEPLOY-06 | Phase 11 | Complete |
| INTEGRATE-01 | Phase 11 | Complete |
| INTEGRATE-02 | Phase 11 | Complete |
| INTEGRATE-03 | Phase 11 | Complete |
| INTEGRATE-04 | Phase 1 | Complete |
| INTEGRATE-05 | Phase 6 | Complete |
| INTEGRATE-06 | Phase 7 | Complete |

**Coverage:**
- v1 requirements: 85 total
- Mapped to phases: 85
- Unmapped: 0

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after roadmap creation*
