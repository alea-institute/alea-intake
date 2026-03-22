# Project Research Summary

**Project:** ALEA Intake
**Domain:** Legal intake system with iterative LLM analysis, ontology integration, and multi-modal input
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

ALEA Intake is an AI-powered legal intake and analysis system that transforms unstructured consumer narratives into structured, ontology-grounded legal analysis. The product occupies a unique market position -- no competitor connects intake, ontology-grounded issue identification, iterative research, and structured fact-to-claim mapping in a single pipeline. The recommended approach builds on the proven FOLIO ecosystem (folio-python, folio-enrich, folio-mapper) using their established technology patterns: FastAPI + SQLAlchemy on the backend, React 19 + Vite + Zustand on the frontend, with alea-llm-client as the multi-provider LLM abstraction. The stack is high-confidence -- every library is verified, versioned, and battle-tested within the ecosystem.

The core engineering challenge is the iterative analysis pipeline: ingest -> issue-spot -> explore -> [research -> fact-map -> gap-analyze -> question -> termination-check] (loop) -> output. This pipeline is architecturally novel compared to folio-enrich's linear pipeline. It requires a state machine orchestrator with checkpointing (analysis sessions span hours or days when awaiting user responses), multi-signal convergence detection (five weighted signals prevent both premature stopping and infinite loops), and real-time streaming of progress to the frontend via WebSocket. The pipeline must also support parallel multi-jurisdictional research fan-out and three-layer issue exploration (FOLIO ontology edges + screening protocols + LLM reasoning).

The key risks are legal, not technical. LLM hallucination of citations (30-45% rate in general LLMs, 17-33% even in specialized tools) demands a hard-gated citation verification pipeline built alongside -- never after -- the analysis integration. Attorney-client privilege waiver through cloud architecture requires treating every data element as potentially privileged from day one, with field-level encryption, tenant isolation beyond RLS alone, and contractual LLM provider guarantees. Unauthorized Practice of Law liability (the Nippon Life v. OpenAI case in March 2026 is the first major UPL action against AI) requires deployment-mode-aware output framing that is enforced architecturally, not just disclaimed. Safety screening for domestic violence, suicidal ideation, and other urgent situations is the most ethically critical feature and must be mandatory, continuous (not just at intake start), and multi-layered. These risks are manageable with the right architecture, but they must be addressed in the foundation phase, not retrofitted.

## Key Findings

### Recommended Stack

The stack is fully aligned with the FOLIO ecosystem. Every major library is already proven in folio-python, folio-enrich, or folio-mapper. There are no risky or unproven dependencies.

**Core backend technologies:**
- **Python >=3.12 + uv:** Runtime and package management matching folio-python requirements; uv provides deterministic lockfiles
- **FastAPI >=0.115.0 + uvicorn[standard]:** ASGI web framework with native SSE (0.135+) and WebSocket support; proven in folio-enrich
- **SQLAlchemy >=2.0.48 + Alembic:** Async ORM with dialect abstraction for dual PostgreSQL/SQLite backends; industry standard
- **alea-llm-client >=0.3.0:** Mandated multi-provider LLM abstraction (OpenAI, Anthropic, Google, xAI, VLLM); only 2 dependencies (httpx + pydantic)
- **folio-python >=0.2.1:** FOLIO ontology client for taxonomy navigation, concept search, semantic matching; 18,300+ legal concepts
- **pgvector >=0.4.2 + faiss-cpu >=1.8:** Dual vector search backends for PostgreSQL (pgvector) and SQLite (FAISS) deployments
- **faster-whisper >=3.8.0:** Local ASR default (4x faster than OpenAI Whisper, CPU-compatible); pluggable with Deepgram/AssemblyAI cloud alternatives
- **cryptography >=44.0.0 (Fernet):** Field-level PII encryption at rest with authenticated encryption and key rotation
- **sse-starlette >=2.0.0:** Server-Sent Events for LLM streaming and progress updates; proven in folio-enrich

**Core frontend technologies:**
- **React 19 + TypeScript 5.7 + Vite 6:** UI framework matching folio-mapper; fast HMR, native ESM
- **Zustand 5 + TanStack Query 5:** Client state (UI/session) + server state (API data, caching, streaming)
- **@xyflow/react 12 + elkjs:** Graph visualization already used in folio-mapper; perfect for fact-claim-element graph view
- **Tailwind CSS v3.4 (NOT v4):** Ecosystem consistency with folio-mapper; v4 has major breaking changes to defer

**Critical version note:** Use Tailwind v3.4 to match folio-mapper. Tailwind v4 fundamentally changes configuration (JS -> CSS @theme), renames utility classes, and moves the PostCSS plugin. Upgrade later as a coordinated effort across the ecosystem.

### Expected Features

**Must have (table stakes) -- users expect these:**
- Text-based narrative capture with conversational chat interface
- FOLIO ontology-grounded issue identification (the core analytical capability)
- Pre-research exploration with FOLIO relationship traversal for adjacent issue discovery
- Safety screening (hardcoded DV protocol as proof of concept)
- Single research tool integration (CourtListener or Google Scholar to validate the adapter pattern)
- Basic fact-to-claim mapping (matrix view for completeness checking)
- Gap analysis and follow-up question generation (single iteration first)
- Structured case memo output
- Role-based authentication (admin, attorney, consumer)
- Field-level encryption + audit logging + consent capture
- Mobile-responsive interface

**Should have (differentiators) -- the reasons someone chooses ALEA Intake:**
- FOLIO ontology-grounded issue spotting (no competitor uses a structured legal ontology; all rely on pure LLM reasoning)
- Three-layer pre-research exploration (FOLIO edges + screening protocols + LLM reasoning)
- Iterative analysis loop with multi-signal convergence detection
- Three fact-mapping views (graph exploration, matrix completeness, narrative-anchored comprehension)
- Parallel multi-jurisdictional analysis
- Pluggable legal research tools via MCP + HTTP adapters
- Ground truth citation verification against known databases
- Configurable autonomy levels (chatbot, professional, agent)
- Voice input with pluggable ASR backends
- Shared screening protocol library (community + private)

**Defer to v2+:**
- Admin-configurable knowledge base with RAG
- Configurable persistence modes (ephemeral, persistent, CMS-integrated)
- Hybrid cloud + self-hosted deployment
- Configurable database backend (build on PostgreSQL first, abstract later)
- Full protocol library governance (versioning, review workflows, quality scoring)

**Anti-features (explicitly NOT building):**
- Legal advice generation (UPL liability)
- Autonomous case filing (malpractice liability)
- Real-time collaborative editing (CRDT complexity for minimal value at intake stage)
- Predictive case outcome analysis (unreliable, creates false confidence)
- Payment processing / billing (CMS handles this)
- Marketing automation / lead scoring (not aligned with access-to-justice mission)

### Architecture Approach

The system is a five-layer architecture: Presentation (React/Vite/Zustand), API Gateway (FastAPI with auth/consent/audit middleware), Orchestration (IntakeOrchestrator state machine with iterative loop), Services (LLM, FOLIO, research tools, ASR, protocols, documents), and Persistence (session store + vector store + graph store, dual PostgreSQL/SQLite backends). The architectural differentiator is the iterative pipeline orchestrator -- unlike folio-enrich's linear pipeline, this orchestrator implements a state machine with a feedback loop that supports checkpointing across hours or days of user interaction.

**Major components:**
1. **IntakeOrchestrator** -- State machine with three phases: initial linear stages (ingest, issue-spot, explore), iterative analysis loop (research, fact-map, gap-analysis, question, termination-check), and final output formatting. Checkpoints after every stage for pause/resume.
2. **ConvergenceDetector** -- Weighted scoring across five signals (coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps) with configurable threshold. Prevents both premature termination and infinite loops.
3. **ResearchToolRegistry** -- Dual-mechanism tool discovery: MCP servers for MCP-native tools (folio-mcp) + HTTP adapters for REST APIs (CourtListener, Westlaw). Per-organization tool configuration. Parallel fan-out across jurisdictions.
4. **FactClaimGraph** -- Many-to-many mapping between facts, claims (FOLIO Objectives IRIs), and elements. Stored as relational adjacency tables (not a graph DB). Serializes to three visualization formats: D3-compatible graph JSON, claims-x-elements matrix, and narrative-anchored text spans.
5. **Tenant-Isolated Configuration** -- TenantContext injected into every request, scoping database queries, cache keys, LLM calls, and background jobs. Same codebase serves multi-tenant cloud and single-tenant self-hosted without forks.

**Key architectural patterns:**
- Repository pattern with abstract interfaces and factory-selected backends (PostgreSQL or SQLite)
- Vector search abstraction separate from ORM (pgvector is SQL-level; FAISS is Python library-level)
- Protocol-based adapter patterns for ASR, research tools, and CMS connectors
- Screening protocols as structured data (YAML/JSON) interpreted by a runtime engine, not hardcoded logic
- LLM calls routed through alea-llm-client with per-task model selection (cheaper models for classification, expensive for reasoning)

### Critical Pitfalls

1. **LLM hallucination of legal citations** -- General LLMs hallucinate citations 30-45% of the time; even specialized legal AI tools hallucinate 17-33%. Over 700 court cases involve AI-generated hallucinations. Prevention: build a hard-gated citation extraction + verification pipeline that queries legal databases (CourtListener, Westlaw) before any citation reaches users. Use structured generation where the LLM selects from retrieved authorities rather than generating citations from scratch. This must be built alongside the LLM integration, never after.

2. **Attorney-client privilege waiver through cloud architecture** -- Sending privileged data to LLM providers, missing tenant isolation in caches or background jobs, or inadequate logging controls can permanently waive privilege. Prevention: treat every data element as potentially privileged; require contractual ZDR guarantees from LLM providers; implement field-level encryption; use database-level tenant isolation beyond RLS alone (PostgreSQL RLS has had data-leaking CVEs); propagate tenant context through every async worker and background job.

3. **Unauthorized Practice of Law (UPL) liability** -- The Nippon Life v. OpenAI lawsuit (March 2026, $10M+ in damages) is the first major UPL case against AI. The line between "legal information" and "legal advice" is blurry and jurisdiction-dependent. Prevention: deployment-mode-aware output framing enforced architecturally (consumer-facing = "information to discuss with an attorney"; professional-facing = more direct); attorney checkpoint gates at critical decision points; prominent non-dismissable disclaimers; track per-jurisdiction regulatory landscape.

4. **Bias in issue-spotting that systematically disadvantages populations** -- Consumers who use legal vocabulary get better issue-spotting than those who describe the same situation informally. LLMs and ontologies may encode profession-level biases. Prevention: narrative normalization before issue-spotting; three-layer exploration as defense-in-depth; testing with diverse narrative styles (20 scenario pairs measuring identification parity); ensuring screening protocols cover issues affecting underserved populations.

5. **Iterative analysis loop that never converges or converges prematurely** -- Three failure modes: same-tool retry loops, oscillation between issues, and re-planning loops. Premature termination misses critical gaps. Prevention: hard iteration limits as safety net; external objective criteria (not LLM self-assessment) for convergence; cycle detection for near-duplicate questions; oscillation detection that freezes the issue set; configurable termination per deployment type; expose loop state to users for transparency.

6. **Safety screening that misses urgent situations** -- Consumers minimize, code, or indirectly disclose danger. The system may detect danger but respond inadequately. Prevention: mandatory screening before analysis proceeds (enforced architecturally); continuous screening on every message (not just initial narrative); multi-layer detection (keyword + LLM inference + structured questions); defined escalation protocols with specific actions; DV-specific features (quick exit button, no unsolicited notifications).

7. **FOLIO ontology coupling creating rigidity** -- Tight coupling to FOLIO's current structure fails when concepts are missing, the taxonomy changes between versions, or jurisdictional concepts do not map cleanly. Prevention: graceful degradation for unmapped concepts (flag as "emerging" rather than drop); IRI indirection layer in the data model (local concept ID -> FOLIO IRI mapping); FOLIO version migration strategy; allow LLM reasoning layer to identify issues outside FOLIO coverage.

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Foundation and Data Layer
**Rationale:** Security, encryption, tenant isolation, and database patterns affect every subsequent layer. Retrofitting these is extremely expensive (PITFALLS: privilege waiver, over-engineering configuration). The dual-database abstraction (PostgreSQL vs SQLite) must be designed before any code writes data.
**Delivers:** Data models (session, analysis, graph, protocol, organization, job), storage abstraction (repository interfaces), SQLite implementation (for rapid development), config system with tenant context, pipeline stage ABC, field-level PII encryption, audit logging infrastructure, consent flow skeleton, deployment profiles (Legal Aid, Law Firm, Court, Direct-to-Consumer) with opinionated defaults.
**Addresses features:** Authentication + authorization, encryption + audit logging, consent management.
**Avoids pitfalls:** Database lock-in (Pitfall from STACK), privilege waiver through architecture (Pitfall 2), over-engineering configuration (Pitfall 7 -- build profiles, not 40 independent options).

### Phase 2: FOLIO Ontology Integration
**Rationale:** Issue identification is grounded in FOLIO concepts (IRIs). Every downstream feature (exploration, research, fact-mapping) depends on FOLIO integration. Must include graceful degradation for unmapped concepts from day one.
**Delivers:** folio-python wrapper with caching (initialize once at startup, reuse), concept resolution pipeline (user narrative -> LLM extraction -> semantic matching -> verified IRI or "unmapped" flag), FOLIO edge traversal for adjacency discovery, IRI indirection layer in data model.
**Addresses features:** FOLIO ontology integration (P1 table stake).
**Avoids pitfalls:** FOLIO ontology coupling (Pitfall 8 -- graceful degradation, IRI indirection, version migration strategy).

### Phase 3: Core Analysis Pipeline
**Rationale:** The pipeline is the product's core value. Build it with text input first (no ASR/document complexity), test in isolation, then layer modalities on top. The LLM integration, streaming, and iterative loop are the most architecturally novel components.
**Delivers:** LLM service wrapper (alea-llm-client with per-task model routing), ingest stage (text passthrough), issue-spot stage (LLM + FOLIO IRI matching), IntakeOrchestrator (linear mode first, then iterative loop), FactClaimGraph model, fact-map stage, gap analysis stage, question stage, convergence detector (multi-signal), termination stage, SSE/WebSocket streaming of pipeline progress.
**Addresses features:** Basic issue identification (P1), basic fact-to-claim mapping (P1), gap analysis + follow-up questioning (P1), structured output (P1).
**Avoids pitfalls:** Loop convergence failure (Pitfall 5 -- build termination criteria before analysis pipeline), LLM provider coupling (Anti-Pattern 4 -- all calls through alea-llm-client), synchronous pipeline blocking (Anti-Pattern 1 -- async from the start).

### Phase 4: Exploration and Research
**Rationale:** Extends the analysis loop with the three-layer exploration (the primary differentiator) and pluggable research tools. Safety screening must be built here with extreme care -- it is the most ethically critical feature.
**Delivers:** Three-layer exploration (FOLIO edges + screening protocols + LLM reasoning), screening protocol data model + runtime engine (YAML/JSON, not hardcoded), hardcoded DV screening protocol as proof of concept, research adapter ABC + first adapter (CourtListener), research tool registry (HTTP adapters first, MCP later), parallel research fan-out, citation extraction + verification pipeline (hard-gated).
**Addresses features:** Pre-research exploration (P1), safety screening (P1), single research tool integration (P1), ground truth verification (P2).
**Avoids pitfalls:** Safety screening misses (Pitfall 6 -- mandatory, continuous, multi-layer), LLM citation hallucination (Pitfall 1 -- verification pipeline built alongside research, never after), monolithic screening protocol format (Anti-Pattern 3 -- structured data, not code).

### Phase 5: Frontend Application
**Rationale:** Build UI after backend APIs stabilize to avoid throwaway work. The three visualization modes are the frontend's most complex components.
**Delivers:** React 19 + Vite + TypeScript app, Zustand stores (session, analysis, UI), intake text input UI, analysis dashboard with real-time progress, three fact-mapping views (graph via @xyflow/react, matrix grid, narrative-anchored text), WebSocket integration for live updates, admin configuration views, mobile-responsive layout.
**Addresses features:** Text narrative capture (P1), mobile-responsive interface, structured output display.
**Avoids pitfalls:** UPL liability (Pitfall 3 -- deployment-mode-aware output framing in the UI), consumer UX pitfalls (legal jargon, confidence score display, question overload), bias in presentation (visual hierarchy for issues).

### Phase 6: Multi-Modal Input and Extended Features
**Rationale:** Voice input and document upload are critical for access-to-justice but should be added after the core pipeline works with text. Multi-jurisdictional analysis extends the research stage. Additional research tools expand coverage.
**Delivers:** ASR adapter pattern + faster-whisper implementation, transcript review/correction UX, document upload + extraction (folio-enrich bridge), voice input UI (WebSocket streaming), parallel multi-jurisdictional research, additional research tool adapters (Westlaw, MCP tools), configurable autonomy levels, iterative analysis loop (full multi-pass with convergence).
**Addresses features:** Voice input (P2), document upload (P2), multi-jurisdictional analysis (P2), configurable autonomy (P2), iterative analysis loop (P2).
**Avoids pitfalls:** Voice transcription errors (Pitfall 9 -- transcript review step, legal term normalization, custom vocabulary), multi-jurisdictional contradictions (Pitfall 10 -- comparative presentation, jurisdiction determination as explicit step, recency metadata).

### Phase 7: Integration and Production Hardening
**Rationale:** CMS connectors, PostgreSQL backend, screening protocol library, and deployment packaging require stable APIs to connect to. Multi-tenant cloud and self-hosted packaging are deployment concerns that should not slow core development.
**Delivers:** CMS sync connectors (Clio, MyCase, LegalServer), PostgreSQL storage implementation, MCP tool registry integration, screening protocol library (community sharing), Docker multi-tenant and self-hosted configurations, performance optimization (caching, rate limiting, vector index optimization), multi-language support (English + Spanish).
**Addresses features:** CMS integration (P2), graph fact-mapping view (P2), narrative-anchored view (P2), screening protocol library (P2), multi-language support (P2).
**Avoids pitfalls:** Over-engineering configuration (Pitfall 7 -- expand based on demand, not hypothesis), CMS integration pitfalls (bidirectional sync, not one-way).

### Phase Ordering Rationale

- **Foundation before everything** because security, encryption, and database patterns are cross-cutting concerns that every feature depends on. Retrofitting tenant isolation or encryption is extremely expensive and error-prone.
- **FOLIO before LLM pipeline** because issue identification grounds LLM output in ontology concepts. Without FOLIO integration, issue-spotting degrades to generic LLM guessing with no structured representation.
- **Core pipeline before exploration/research** because exploration and research extend the analysis loop -- they cannot be tested without a functioning pipeline.
- **Citation verification built alongside research** (Phase 4, not a later phase) because every unverified citation is legally dangerous. The verification pipeline is not optional or deferrable.
- **Frontend after backend APIs** to avoid throwaway UI work during API instability.
- **Multi-modal input after text-only pipeline** because text exercises the full pipeline without ASR/document complexity, and voice/document are additive input channels feeding the same analysis engine.
- **Integration and deployment last** because CMS connectors and deployment packaging require stable APIs, and premature infrastructure work slows core feature development.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** SQLAlchemy dual-dialect patterns and Alembic multi-database migration strategies; Fernet key rotation design for field-level encryption
- **Phase 3:** alea-llm-client streaming API specifics (async generator support for SSE); token budget management strategies; convergence detector weight calibration
- **Phase 4:** CourtListener API rate limits, query patterns, and response schemas; citation extraction NLP patterns; FOLIO relationship graph depth for exploration
- **Phase 6:** faster-whisper memory footprint and CPU requirements for self-hosted; legal term custom vocabulary configuration for ASR providers; choice-of-law analysis patterns

Phases with standard patterns (skip phase research):
- **Phase 2:** folio-python usage patterns are well-documented in the codebase; standard library wrapping
- **Phase 5:** Standard React 19 + Vite + Zustand patterns; @xyflow/react usage proven in folio-mapper; WebSocket integration is well-documented
- **Phase 7:** CMS API documentation is available from each vendor; Docker packaging is standard

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every library verified against PyPI/npm with current versions; ecosystem patterns proven in folio-mapper and folio-enrich; no risky or unproven dependencies |
| Features | HIGH | Core features well-defined against competitor landscape; differentiators clearly identified; MVP scoped appropriately; anti-features explicitly excluded |
| Architecture | HIGH | Dual-database pattern well-documented in SQLAlchemy; pipeline orchestrator pattern proven in folio-enrich/folio-insights; iterative loop adds complexity but patterns exist in the literature |
| Pitfalls | HIGH | All 10 pitfalls sourced from authoritative references (Stanford CodeX, ABA, active litigation, peer-reviewed research); prevention strategies are specific and actionable |

**Overall confidence:** HIGH

### Gaps to Address

- **alea-llm-client streaming API:** Need to verify async generator support for SSE integration during Phase 3 planning. The library supports sync and async variants but streaming behavior with SSE needs hands-on validation.
- **folio-python relationship traversal depth:** Can folio-python provide the full adjacency graph needed for three-layer exploration, or is direct SPARQL via rdflib required for deep traversal? Needs investigation during Phase 2.
- **Convergence detector calibration:** The five-signal weighted scoring function needs real data to calibrate. Initial weights will be educated guesses; must plan for A/B testing and tuning with production usage data.
- **CMS API specifics:** Clio, MyCase, and LegalServer API documentation needs phase-specific research when Phase 7 begins. Do not research prematurely.
- **MCP registry integration:** folio-mcp exists but the pluggable tool registry pattern for discovering and invoking arbitrary MCP-compatible legal research tools needs design during Phase 4.
- **Bias testing methodology:** The 20-scenario-pair approach for bias testing needs careful scenario design by people with legal domain expertise and diverse community input. Cannot be fully validated by engineers alone.
- **Multi-jurisdictional choice-of-law patterns:** Determining which jurisdiction's law applies is itself a complex legal question. The system's approach to this needs legal domain expert input during Phase 6.

## Sources

### Primary (HIGH confidence)
- folio-python, folio-enrich, folio-mapper, folio-insights local codebases -- technology patterns, dependency versions, architectural patterns
- [alea-llm-client on PyPI](https://pypi.org/project/alea-llm-client/) -- v0.3.0, multi-provider abstraction
- [FOLIO - Federated Open Legal Information Ontology](https://openlegalstandard.org/) -- 18,300+ concepts, 22 branches
- [Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools](https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413) -- Stanford CodeX, 2025
- [Stanford Justice Innovation - Legal Aid Intake & Screening AI](https://justiceinnovation.law.stanford.edu/legal-aid-intake-screening-ai/) -- academic research
- [Nippon Life v. OpenAI -- UPL Lawsuit](https://law.stanford.edu/2026/03/07/designed-to-cross-why-nippon-life-v-openai-is-a-product-liability-case/) -- Stanford Law CodeX, March 2026
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- tool registry and agent patterns
- [Azure OpenAI Data Privacy](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy) -- data retention and ZDR policies
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- v0.135.1, native SSE support
- [pgvector-python GitHub](https://github.com/pgvector/pgvector-python) -- v0.4.2, SQLAlchemy integration
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- v3.8.2, CTranslate2-based

### Secondary (MEDIUM confidence)
- [IMPROVE: Iterative Model Pipeline Refinement](https://arxiv.org/html/2502.18530v1) -- iterative LLM pipeline convergence patterns
- [Multi-Tenant Architecture Guide (WorkOS)](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture) -- tenant isolation patterns
- [AI and Racial Bias in Legal Decision-Making](https://clp.law.harvard.edu/knowledge-hub/insights/ai-and-racial-bias-in-legal-decision-making-a-student-fellow-project/) -- Harvard Law School
- [Multi-Jurisdictional Legal Research Challenges](https://www.regology.com/blog/understanding-the-challenges-of-multi-jurisdictional-legal-research) -- Regology
- [Clio Grow - Client Intake Best Practices 2026](https://www.clio.com/blog/client-intake-law-firms/) -- competitor features
- [AI Hallucination Cases Database](https://www.damiencharlotin.com/hallucinations/) -- 700+ cases tracked

### Tertiary (LOW confidence)
- [Best Intake Software for Lawyers 2026](https://inoriseo.com/law-firm-software/best-intake-software-for-lawyers-2026/) -- SEO content, feature comparison only

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
