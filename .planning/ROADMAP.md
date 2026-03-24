# Roadmap: ALEA Intake

## Overview

ALEA Intake transforms unstructured consumer narratives into structured, ontology-grounded legal analysis. The roadmap builds from security and data foundations upward through FOLIO ontology integration, multi-modal input capture, the iterative analysis pipeline, pre-research exploration with safety screening, pluggable legal research with citation verification, structured output generation, a full React frontend with three specialized visualization modes, configurable autonomy orchestration, and finally CMS integrations with production deployment. Each phase delivers a coherent, verifiable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & Security** - Data models, auth, encryption, tenant isolation, audit logging, and infrastructure scaffolding
- [ ] **Phase 2: FOLIO Ontology Integration** - Ontology loading, concept resolution, IRI matching, adjacency discovery, and graceful degradation
- [ ] **Phase 3: Input & Narrative Capture** - Text chat, voice/ASR, document upload, professional notes, normalization, and fact extraction
- [ ] **Phase 4: Core Analysis Pipeline** - Iterative analysis loop, fact-to-claim mapping, gap analysis, convergence detection, and checkpointing
- [ ] **Phase 5: Pre-Research Exploration & Safety** - Three-layer exploration, screening protocols, DV default protocol, continuous safety screening
- [ ] **Phase 6: Legal Research & Verification** - Pluggable research tools, MCP + HTTP adapters, citation verification, knowledge base
- [ ] **Phase 7: Output & Export** - Case memos, triage/routing, action items, configurable formats, and export
- [ ] **Phase 8: Frontend Application** - Chat interface, streaming progress, dashboard, admin config, mobile responsive, voice recording UI
- [ ] **Phase 9: Frontend Visualization** - Graph fact-mapping view, matrix completeness view, narrative-anchored annotation view
- [ ] **Phase 10: Autonomy & Orchestration Modes** - Chatbot, professional, and agent modes with per-org configuration
- [ ] **Phase 11: Integration & Production Deployment** - CMS connectors, multi-tenant cloud, self-hosted deployment, persistence modes

## Phase Details

### Phase 1: Foundation & Security
**Goal**: The system has a secure, tenant-isolated data layer with authentication, encryption, audit logging, and consent management -- providing the trusted foundation every subsequent feature builds on
**Depends on**: Nothing (first phase)
**Requirements**: SECURITY-01, SECURITY-02, SECURITY-03, SECURITY-04, SECURITY-05, SECURITY-06, SECURITY-07, SECURITY-08, SECURITY-09, SECURITY-10, DEPLOY-01, DEPLOY-04, INTEGRATE-04
**Success Criteria** (what must be TRUE):
  1. A user can register, log in with JWT, and access only resources permitted by their role (admin, professional, consumer)
  2. All PII fields are encrypted at rest with AES-256 field-level encryption, and all API traffic uses TLS
  3. Every action (login, data access, AI decision) is recorded in an immutable audit log that administrators can review
  4. A consumer completes a granular consent flow before any AI processing begins, and can exercise right-to-delete with full cascade
  5. Multi-tenant data isolation prevents any cross-tenant data leakage, and no case data is sent to LLM training endpoints
**Plans:** 4/5 plans executed

Plans:
- [ ] 01-01-PLAN.md — Project scaffolding, config, DB engine, models, tenant isolation, and test harness
- [ ] 01-02-PLAN.md — JWT authentication with refresh tokens and role-based access control
- [ ] 01-03-PLAN.md — AES-256-GCM envelope encryption and field-level PII encryption
- [ ] 01-04-PLAN.md — Audit logging, consent management, and right-to-delete cascade
- [ ] 01-05-PLAN.md — LLM service integration, organization endpoints, Docker, and frontend scaffold

### Phase 2: FOLIO Ontology Integration
**Goal**: The system can load the FOLIO ontology, resolve consumer facts to canonical FOLIO concept IRIs, traverse ontology relationships for adjacency discovery, and gracefully handle unmapped concepts
**Depends on**: Phase 1
**Requirements**: FOLIO-01, FOLIO-02, FOLIO-03, FOLIO-04, FOLIO-05, FOLIO-06, FOLIO-07
**Success Criteria** (what must be TRUE):
  1. The system loads the FOLIO ontology at startup via folio-python and uses IRIs as the canonical identifier for every legal concept in the data model
  2. Given a consumer's factual description, the system identifies applicable FOLIO Objectives (claims/defenses), Areas of Law, Legal Authority types, and Jurisdictions
  3. The system traverses FOLIO OWL object properties to discover adjacent legal concepts related to an identified issue
  4. When the system encounters a legal concept not in FOLIO, it flags it as "unmapped" and continues analysis rather than dropping it
**Plans:** 1/3 plans executed

Plans:
- [ ] 02-01-PLAN.md — FOLIO singleton loader, OWL cache with ETag freshness, OWL update manager, DB models, term expansions, and lifespan integration
- [ ] 02-02-PLAN.md — Embedding service (dual pgvector/FAISS backend) and multi-stage concept resolution pipeline
- [ ] 02-03-PLAN.md — Unmapped concept handling, adjacency discovery with graph persistence, and FOLIO admin API

### Phase 3: Input & Narrative Capture
**Goal**: Consumers and professionals can provide information through any supported modality (text, voice, documents, professional notes), and the system normalizes all input into a common representation with extracted factual assertions
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria** (what must be TRUE):
  1. A consumer can type their story in a conversational chat interface and receive acknowledgment that their narrative was captured
  2. A consumer can record voice input that is transcribed via a pluggable ASR provider (local Whisper or cloud), with the transcript available for review
  3. A consumer can upload PDF, DOCX, or image documents that are processed for text extraction
  4. A professional can enter notes on behalf of a consumer, and those notes enter the same analysis pipeline as consumer-provided input
  5. All input modalities produce a common normalized text representation from which atomic factual assertions (parties, dates, locations, amounts, events) are extracted
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Core Analysis Pipeline
**Goal**: The system performs iterative analysis -- issue-spotting, fact-to-claim mapping, gap analysis, follow-up questioning, and convergence detection -- producing a complete mapping of consumer facts to legal claims, elements, and identified gaps
**Depends on**: Phase 2, Phase 3
**Requirements**: ANALYSIS-01, ANALYSIS-02, ANALYSIS-03, ANALYSIS-04, ANALYSIS-05, ANALYSIS-06, ANALYSIS-07, ANALYSIS-08, ANALYSIS-09, ANALYSIS-10
**Success Criteria** (what must be TRUE):
  1. The system executes the full iterative loop (issue-spot, research, fact-map, gap-analyze, question, loop) and the loop terminates based on multi-signal convergence (coverage %, confidence plateau, iteration count, fatigue, diminishing gaps)
  2. Facts are mapped to claims and elements in many-to-many relationships with confidence scores, and the user can see which facts support which claim elements
  3. The system identifies gaps (unsupported elements, unexplored claims, weak mappings) and generates prioritized, consumer-friendly follow-up questions grouped by topic
  4. Analysis state is checkpointed after every stage, allowing pause/resume across sessions without loss of progress
  5. A complete audit trail records every analysis stage, sources consulted, and confidence scores assigned
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD
- [ ] 04-04: TBD
- [ ] 04-05: TBD

### Phase 5: Pre-Research Exploration & Safety
**Goal**: The system performs pre-research exploration using three layers (FOLIO relationships, curated screening protocols, LLM reasoning) to discover adjacent legal issues and ensure continuous safety screening throughout every conversation
**Depends on**: Phase 2, Phase 4
**Requirements**: EXPLORE-01, EXPLORE-02, EXPLORE-03, EXPLORE-04, EXPLORE-05, EXPLORE-06, EXPLORE-07, EXPLORE-08, EXPLORE-09, EXPLORE-10
**Success Criteria** (what must be TRUE):
  1. Between initial issue-spotting and research, the system performs exploration using all three layers (FOLIO ontology relationships, curated screening protocols, LLM reasoning) and surfaces new legal issues the consumer did not mention
  2. Safety screening runs continuously on every consumer message throughout the conversation, not just at intake start
  3. Organizations can define mandatory safety screening protocols, and a default DV screening protocol ships with the system for family law matters
  4. Organizations can create both community-shared and private screening protocols, with configurable exploration depth and question transparency
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD
- [ ] 05-04: TBD

### Phase 6: Legal Research & Verification
**Goal**: The system queries pluggable legal research tools to find authorities for each identified claim, verifies all citations against known databases before presentation, and supports organization-specific knowledge bases
**Depends on**: Phase 4, Phase 5
**Requirements**: RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-09, RESEARCH-10, INTEGRATE-05
**Success Criteria** (what must be TRUE):
  1. The system queries at least one legal research tool (CourtListener) via the pluggable adapter pattern and returns relevant case law, statutes, and regulations for identified claims
  2. Organizations can configure which research tools they have access to, and the system discovers tools via both MCP registry (folio-mcp) and HTTP adapters
  3. Every LLM-suggested citation is verified against a known database before presentation, and each authority displays a verified/unverified flag with verification source
  4. For each identified claim, the system researches required legal elements per jurisdiction, integrating with folio-insights for advocacy knowledge and folio-enrich for document analysis
  5. Administrators can configure a knowledge base with RAG over curated legal documents, and organizations can upload custom documents to their KB
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD
- [ ] 06-04: TBD
- [ ] 06-05: TBD

### Phase 7: Output & Export
**Goal**: The system generates configurable output -- structured case memos, triage/routing recommendations, and action items -- in formats appropriate for each deployment type, with export to PDF, DOCX, and JSON
**Depends on**: Phase 4, Phase 6
**Requirements**: OUTPUT-01, OUTPUT-02, OUTPUT-03, OUTPUT-04, OUTPUT-05, INTEGRATE-06
**Success Criteria** (what must be TRUE):
  1. The system generates a structured case memo mapping facts to claims to elements to authorities to jurisdictions
  2. The system generates triage/routing recommendations (practice area, attorney, program) and actionable next steps (documents to gather, follow-up actions, referrals)
  3. Output format is configurable per deployment: law firms receive detailed memos, legal aid receives triage routing, courts receive self-help guidance
  4. Output includes gap analysis showing what evidence is missing and what questions remain unanswered
  5. Users can export output in PDF, DOCX, and JSON formats
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Frontend Application
**Goal**: Users interact with the system through a responsive React frontend featuring conversational chat, real-time analysis progress, an intake dashboard, admin configuration, and voice recording
**Depends on**: Phase 1, Phase 3, Phase 4
**Requirements**: FRONTEND-01, FRONTEND-02, FRONTEND-06, FRONTEND-07, FRONTEND-08, FRONTEND-09, FRONTEND-10
**Success Criteria** (what must be TRUE):
  1. A consumer can conduct an intake conversation through a chat interface that sends and receives messages in real time
  2. Analysis progress streams to the frontend via WebSocket/SSE, showing the user what stage the system is currently processing
  3. An intake dashboard lists all intakes with their status and progress, and users can click into any intake to view its output
  4. Administrators can configure organization settings, research tools, knowledge base documents, and screening protocols through a dedicated admin interface
  5. The interface is mobile-responsive and includes a voice recording component for voice input
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD
- [ ] 08-04: TBD

### Phase 9: Frontend Visualization
**Goal**: Users can explore the relationship between facts, claims, and elements through three specialized views -- a force-directed graph for exploration, a matrix for completeness checking, and narrative-anchored annotations for comprehension
**Depends on**: Phase 8
**Requirements**: FRONTEND-03, FRONTEND-04, FRONTEND-05
**Success Criteria** (what must be TRUE):
  1. The graph view renders a force-directed visualization of facts, claims, elements, and their relationships that users can pan, zoom, and click to explore
  2. The matrix view displays a fact-by-element completeness grid showing coverage with color-coded confidence indicators
  3. The narrative-anchored view overlays analysis annotations on the consumer's original narrative text, linking highlighted spans to the claims and elements they support
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD
- [ ] 09-03: TBD

### Phase 10: Autonomy & Orchestration Modes
**Goal**: The system supports three configurable autonomy levels -- chatbot (fully autonomous), professional (human-guided), and agent (AI with checkpoints) -- each enforcing the appropriate level of human oversight per organization
**Depends on**: Phase 4, Phase 5, Phase 6
**Requirements**: AUTONOMY-01, AUTONOMY-02, AUTONOMY-03, AUTONOMY-04, AUTONOMY-05
**Success Criteria** (what must be TRUE):
  1. In chatbot mode, the system runs all analysis steps autonomously and presents questions directly to the consumer without professional intervention
  2. In professional mode, the system suggests actions at each stage and waits for a human professional to approve before proceeding
  3. In agent mode, the system orchestrates autonomously but pauses at configurable checkpoints for human review, with per-org configuration of which stages require approval
  4. Organizations can select and switch between autonomy levels through admin configuration
**Plans**: TBD

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD
- [ ] 10-03: TBD

### Phase 11: Integration & Production Deployment
**Goal**: The system integrates with external case management systems, supports both multi-tenant cloud and single-tenant self-hosted deployment, and provides configurable persistence modes with production monitoring
**Depends on**: Phase 1, Phase 7, Phase 8
**Requirements**: INTEGRATE-01, INTEGRATE-02, INTEGRATE-03, DEPLOY-02, DEPLOY-03, DEPLOY-05, DEPLOY-06
**Success Criteria** (what must be TRUE):
  1. Intake data syncs bidirectionally with at least one CMS (Clio), with MyCase and Legal Server connectors also available
  2. The system deploys as a multi-tenant cloud instance with org-scoped data isolation, and as a single-tenant self-hosted instance from the same codebase
  3. Persistence mode is configurable per organization: ephemeral (data deleted after session), persistent (full case tracking), or CMS-integrated (synced to external system)
  4. Health check and monitoring endpoints report system status, and operators can observe system health in production
**Plans**: TBD

Plans:
- [ ] 11-01: TBD
- [ ] 11-02: TBD
- [ ] 11-03: TBD
- [ ] 11-04: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11

Note: Phases 2 and 3 can execute in parallel (both depend only on Phase 1). Phase 4 depends on both 2 and 3.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Security | 4/5 | In Progress|  |
| 2. FOLIO Ontology Integration | 1/3 | In Progress|  |
| 3. Input & Narrative Capture | 0/3 | Not started | - |
| 4. Core Analysis Pipeline | 0/5 | Not started | - |
| 5. Pre-Research Exploration & Safety | 0/4 | Not started | - |
| 6. Legal Research & Verification | 0/5 | Not started | - |
| 7. Output & Export | 0/3 | Not started | - |
| 8. Frontend Application | 0/4 | Not started | - |
| 9. Frontend Visualization | 0/3 | Not started | - |
| 10. Autonomy & Orchestration Modes | 0/3 | Not started | - |
| 11. Integration & Production Deployment | 0/4 | Not started | - |
