# Architecture Research

**Domain:** Legal intake system with iterative LLM analysis, ontology integration, and multi-modal input
**Researched:** 2026-03-22
**Confidence:** HIGH

## System Overview

```
                              PRESENTATION LAYER
 +---------------------------------------------------------------------------+
 |  React/Vite/Zustand/TypeScript/Tailwind                                   |
 |  +------------------+  +------------------+  +------------------------+   |
 |  | Intake UI        |  | Analysis         |  | Visualization          |   |
 |  | (text/voice/doc) |  | Dashboard        |  | (graph/matrix/narr.)   |   |
 |  +--------+---------+  +--------+---------+  +-----------+------------+   |
 |           |                      |                        |               |
 |           +----------+-----------+----------+-------------+               |
 |                      | WebSocket + REST                                   |
 +---------------------------------------------------------------------------+
                        |
                        v
                              API GATEWAY LAYER
 +---------------------------------------------------------------------------+
 |  FastAPI                                                                  |
 |  +------------------+  +------------------+  +------------------------+   |
 |  | Intake API       |  | Session API      |  | Admin / Config API     |   |
 |  | (upload, stream) |  | (WS, state)      |  | (org, protocols)       |   |
 |  +--------+---------+  +--------+---------+  +-----------+------------+   |
 |           |                      |                        |               |
 |  +--------+----------------------+------------------------+------------+  |
 |  | Auth / Tenant Middleware | Consent | Audit | Rate Limit             |  |
 |  +-------------------------+--------+--------+------------------------+  |
 +---------------------------------------------------------------------------+
                        |
                        v
                              ORCHESTRATION LAYER
 +---------------------------------------------------------------------------+
 |  +------------------------------------------------------------------+    |
 |  |                    IntakeOrchestrator                              |    |
 |  |  (pipeline state machine, loop control, convergence detection)    |    |
 |  +-----+------+------+------+------+------+------+------+------+----+    |
 |        |      |      |      |      |      |      |      |      |        |
 |        v      v      v      v      v      v      v      v      v        |
 |  +--------+ +-----+ +----+ +----+ +----+ +----+ +----+ +----+ +------+  |
 |  |Ingest  | |Issue| |Expl| |Rese| |Fact| |Gap | |Ques| |Term| |Output|  |
 |  |Stage   | |Spot | |ore | |arch| |Map | |Anal| |tion| |inat| |Format|  |
 |  +--------+ +-----+ +----+ +----+ +----+ +----+ +----+ +----+ +------+  |
 +---------------------------------------------------------------------------+
                        |
                        v
                              SERVICE LAYER
 +---------------------------------------------------------------------------+
 |  +-------------+  +-------------+  +---------------+  +--------------+   |
 |  | LLM Service |  | FOLIO       |  | Research Tool |  | ASR Service  |   |
 |  | (alea-llm-  |  | Service     |  | Registry      |  | (Whisper/    |   |
 |  |  client)    |  | (folio-py)  |  | (MCP + HTTP)  |  |  Deepgram)   |   |
 |  +------+------+  +------+------+  +-------+-------+  +------+-------+   |
 |         |                |                  |                 |           |
 |  +------+------+  +------+------+  +-------+-------+                     |
 |  | Protocol    |  | Screening   |  | Document      |                     |
 |  | Library     |  | Protocol    |  | Processor     |                     |
 |  | Service     |  | Engine      |  | (folio-enrich)|                     |
 |  +-------------+  +-------------+  +---------------+                     |
 +---------------------------------------------------------------------------+
                        |
                        v
                              PERSISTENCE LAYER
 +---------------------------------------------------------------------------+
 |  +-------------------+  +------------------+  +------------------------+  |
 |  | Session Store     |  | Vector Store     |  | Graph Store            |  |
 |  | (case state,      |  | (embeddings,     |  | (fact-claim-element    |  |
 |  |  conversation)    |  |  similarity)     |  |  mappings)             |  |
 |  +-------------------+  +------------------+  +------------------------+  |
 |                                                                           |
 |  PostgreSQL+pgvector (production) | SQLite+FAISS (dev/self-hosted lite)   |
 +---------------------------------------------------------------------------+
```

## Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Intake UI** | Multi-modal input capture: text entry, voice recording/streaming, document upload, professional notes | React components with Web Audio API for voice, drag-drop for docs |
| **Analysis Dashboard** | Real-time pipeline progress, iteration status, human-in-the-loop checkpoints, question display | Zustand store + WebSocket subscription for live updates |
| **Visualization Engine** | Three view modes: graph (exploration), matrix (completeness), narrative-anchored (consumer) | React with D3/force-graph, custom matrix grid, annotated text view |
| **Intake API** | HTTP endpoints for file upload, text submission, session creation | FastAPI routers with multipart upload, streaming responses |
| **Session API** | WebSocket connections for real-time bidirectional communication during analysis loop | FastAPI WebSocket endpoints with per-session state |
| **Admin/Config API** | Organization setup, screening protocol management, tool configuration, user management | CRUD endpoints with tenant-scoped authorization |
| **Auth/Tenant Middleware** | JWT validation, tenant isolation, role-based access, consent tracking | FastAPI middleware stack; tenant ID in every request context |
| **IntakeOrchestrator** | Pipeline state machine: sequences stages, manages iteration loop, detects convergence, handles checkpoints | Async Python class following folio-enrich/folio-insights orchestrator pattern |
| **Ingest Stage** | Normalizes multi-modal input into canonical text segments with metadata | Delegates to ASR for voice, folio-enrich bridge for documents, direct passthrough for text |
| **Issue Spot Stage** | LLM-powered identification of legal issues against FOLIO Objectives taxonomy | Structured LLM output matched to FOLIO IRIs via folio-python search |
| **Explore Stage** | Pre-research exploration: FOLIO edge traversal, screening protocol execution, LLM-driven adjacency discovery | Three-layer expansion: ontology relationships, curated protocols, LLM reasoning |
| **Research Stage** | Parallel multi-jurisdictional legal research via pluggable tools | Fan-out to configured research adapters (CourtListener, Westlaw, etc.) per jurisdiction |
| **Fact Map Stage** | Maps extracted facts to claims and their elements in a many-to-many graph | Creates/updates edges in the fact-claim-element graph with confidence scores |
| **Gap Analysis Stage** | Identifies unmet elements, missing jurisdictions, weak confidence areas | Traverses fact-claim-element graph to find uncovered or low-confidence nodes |
| **Question Stage** | Generates targeted follow-up questions based on gaps, prioritized by impact | LLM-generated questions with rationale; waits for consumer/professional response |
| **Termination Stage** | Multi-signal convergence check: coverage %, confidence plateau, iteration count, user fatigue, diminishing gaps | Weighted scoring function across five signals; returns CONTINUE or COMPLETE |
| **Output Format Stage** | Produces final deliverables: structured memo, triage routing, action items per org config | Template-based rendering with org-specific format preferences |
| **LLM Service** | Multi-provider LLM abstraction with task-specific model routing | alea-llm-client BaseAIModel; per-task provider selection (following folio-enrich TaskLLMs pattern) |
| **FOLIO Service** | Ontology queries: class lookup, edge traversal, semantic search, branch navigation | folio-python FOLIO class as embedded library; taxonomy navigation, LLM-powered matching |
| **Research Tool Registry** | Pluggable legal research tool discovery and invocation | MCP registry for MCP-compatible tools + HTTP adapter pattern for REST APIs |
| **ASR Service** | Speech-to-text with pluggable backends | Adapter pattern: local (faster-whisper) or cloud (Deepgram, AssemblyAI) |
| **Protocol Library Service** | CRUD for screening protocols; community-shared + org-private | Protocol definitions as structured YAML/JSON; version-controlled; org-scoped access |
| **Screening Protocol Engine** | Executes screening protocols against current issue set | Rule engine evaluating protocol conditions, generating exploration questions |
| **Document Processor** | Multi-format document ingestion and text extraction | Bridge to folio-enrich HTTP API for heavy processing |
| **Session Store** | Case/session state, conversation history, iteration state | Repository pattern over configurable backend (Postgres or SQLite) |
| **Vector Store** | Semantic similarity for fact matching, ontology search augmentation | pgvector (production) or FAISS (lightweight); shared abstraction interface |
| **Graph Store** | Fact-to-claim-to-element many-to-many mapping with confidence edges | Adjacency lists in relational tables (not a separate graph DB); JSON graph for small cases |

## Recommended Project Structure

```
alea-intake/
+-- backend/
|   +-- app/
|   |   +-- __init__.py
|   |   +-- main.py                    # FastAPI app factory
|   |   +-- config.py                  # Settings with env var loading
|   |   +-- api/
|   |   |   +-- __init__.py
|   |   |   +-- routes/
|   |   |   |   +-- intake.py          # Upload, text submission endpoints
|   |   |   |   +-- session.py         # WebSocket session management
|   |   |   |   +-- admin.py           # Org config, protocol management
|   |   |   |   +-- analysis.py        # Analysis results, visualization data
|   |   |   +-- middleware/
|   |   |       +-- auth.py            # JWT + tenant isolation
|   |   |       +-- consent.py         # Consent tracking
|   |   |       +-- audit.py           # Audit logging
|   |   +-- models/
|   |   |   +-- __init__.py
|   |   |   +-- session.py             # IntakeSession, ConversationTurn
|   |   |   +-- analysis.py            # Issue, Claim, Element, Fact
|   |   |   +-- graph.py               # FactClaimEdge, ElementMapping
|   |   |   +-- protocol.py            # ScreeningProtocol, ProtocolRule
|   |   |   +-- organization.py        # Organization, OrgConfig
|   |   |   +-- job.py                 # IntakeJob, JobStatus
|   |   +-- pipeline/
|   |   |   +-- __init__.py
|   |   |   +-- orchestrator.py        # IntakeOrchestrator (state machine + loop)
|   |   |   +-- stages/
|   |   |   |   +-- base.py            # IntakePipelineStage ABC + IntakeJob
|   |   |   |   +-- ingest.py          # Multi-modal ingestion
|   |   |   |   +-- issue_spot.py      # FOLIO-backed issue identification
|   |   |   |   +-- explore.py         # Three-layer exploration
|   |   |   |   +-- research.py        # Parallel multi-jurisdiction research
|   |   |   |   +-- fact_map.py        # Fact-to-claim-element mapping
|   |   |   |   +-- gap_analysis.py    # Coverage and confidence gap detection
|   |   |   |   +-- question.py        # Follow-up question generation
|   |   |   |   +-- termination.py     # Multi-signal convergence check
|   |   |   |   +-- output.py          # Final deliverable formatting
|   |   |   +-- convergence.py         # ConvergenceDetector (multi-signal scoring)
|   |   +-- services/
|   |   |   +-- __init__.py
|   |   |   +-- llm/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- client.py          # alea-llm-client wrapper + task routing
|   |   |   |   +-- prompts/           # Structured prompt templates per stage
|   |   |   +-- folio/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- ontology.py        # folio-python FOLIO wrapper + caching
|   |   |   |   +-- traversal.py       # Edge traversal for adjacency discovery
|   |   |   +-- research/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- registry.py        # Tool registry (MCP + HTTP adapters)
|   |   |   |   +-- adapters/
|   |   |   |   |   +-- base.py        # ResearchAdapter ABC
|   |   |   |   |   +-- courtlistener.py
|   |   |   |   |   +-- google_scholar.py
|   |   |   |   |   +-- westlaw.py     # Commercial adapter stub
|   |   |   |   |   +-- mcp_adapter.py # Generic MCP tool adapter
|   |   |   +-- asr/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- base.py            # ASR adapter ABC
|   |   |   |   +-- whisper.py         # Local faster-whisper
|   |   |   |   +-- deepgram.py        # Cloud Deepgram
|   |   |   +-- protocols/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- library.py         # Protocol CRUD + community/private scoping
|   |   |   |   +-- engine.py          # Protocol execution engine
|   |   |   +-- documents/
|   |   |       +-- __init__.py
|   |   |       +-- processor.py       # folio-enrich bridge for doc processing
|   |   +-- storage/
|   |   |   +-- __init__.py
|   |   |   +-- base.py               # Abstract repository interfaces
|   |   |   +-- postgres/
|   |   |   |   +-- __init__.py
|   |   |   |   +-- session_repo.py
|   |   |   |   +-- analysis_repo.py
|   |   |   |   +-- vector_store.py    # pgvector implementation
|   |   |   |   +-- migrations/       # Alembic migrations
|   |   |   +-- sqlite/
|   |   |       +-- __init__.py
|   |   |       +-- session_repo.py
|   |   |       +-- analysis_repo.py
|   |   |       +-- vector_store.py    # FAISS implementation
|   |   +-- security/
|   |       +-- __init__.py
|   |       +-- encryption.py         # Field-level PII encryption
|   |       +-- privilege.py          # Attorney-client privilege markers
|   |       +-- consent.py            # Consent flow management
|   |       +-- audit.py              # Audit trail logging
+-- frontend/
|   +-- src/
|   |   +-- App.tsx
|   |   +-- main.tsx
|   |   +-- stores/
|   |   |   +-- sessionStore.ts       # Zustand: session state
|   |   |   +-- analysisStore.ts      # Zustand: analysis/graph state
|   |   |   +-- uiStore.ts            # Zustand: view mode, preferences
|   |   +-- components/
|   |   |   +-- intake/
|   |   |   |   +-- TextInput.tsx
|   |   |   |   +-- VoiceRecorder.tsx
|   |   |   |   +-- DocumentUpload.tsx
|   |   |   |   +-- QuestionPanel.tsx  # Follow-up question display/response
|   |   |   +-- analysis/
|   |   |   |   +-- ProgressTracker.tsx
|   |   |   |   +-- IterationIndicator.tsx
|   |   |   |   +-- IssueList.tsx
|   |   |   +-- visualization/
|   |   |   |   +-- GraphView.tsx      # D3 force-directed graph
|   |   |   |   +-- MatrixView.tsx     # Claims x Elements completeness matrix
|   |   |   |   +-- NarrativeView.tsx  # Annotated narrative with linked claims
|   |   |   |   +-- ViewSwitcher.tsx
|   |   |   +-- admin/
|   |   |       +-- OrgConfig.tsx
|   |   |       +-- ProtocolEditor.tsx
|   |   |       +-- ToolConfig.tsx
|   |   +-- hooks/
|   |   |   +-- useWebSocket.ts        # WebSocket connection + reconnect
|   |   |   +-- useAnalysis.ts         # Analysis state subscription
|   |   +-- api/
|   |       +-- client.ts              # HTTP + WS client
|   +-- index.html
|   +-- vite.config.ts
|   +-- tailwind.config.ts
+-- protocols/                          # Community screening protocol library
|   +-- safety/
|   |   +-- domestic_violence.yaml
|   |   +-- child_abuse.yaml
|   |   +-- suicide_risk.yaml
|   +-- adjacency/
|       +-- custody_to_dv.yaml
|       +-- employment_to_discrimination.yaml
+-- docker/
|   +-- Dockerfile
|   +-- docker-compose.yml              # Multi-tenant cloud
|   +-- docker-compose.selfhosted.yml   # Single-tenant self-hosted
+-- tests/
    +-- backend/
    +-- frontend/
```

### Structure Rationale

- **`backend/app/pipeline/`:** Mirrors the proven folio-enrich and folio-insights pattern -- abstract stage base class, orchestrator that sequences stages, job model carrying state. This is the core differentiator from those projects: here the pipeline is iterative (loops back) rather than linear.
- **`backend/app/services/`:** Clean separation of external integrations (LLM, FOLIO, research tools, ASR) from pipeline logic. Each service has an adapter ABC so implementations are swappable without touching pipeline code.
- **`backend/app/storage/`:** Dual-backend abstraction is essential for the PostgreSQL/SQLite requirement. Abstract repository interfaces in `base.py` with concrete implementations in `postgres/` and `sqlite/` subdirectories. Factory function selects backend at startup based on config.
- **`backend/app/security/`:** Dedicated security module because legal data requires field-level encryption, privilege-awareness, and consent flows -- these cut across all layers.
- **`frontend/src/visualization/`:** The three view modes are complex enough to warrant dedicated components. Each view subscribes to the same underlying graph data but renders it differently.
- **`protocols/`:** Top-level directory (not buried in backend) because screening protocols are a shared community asset, versioned independently, and potentially distributed as a separate package.

## Architectural Patterns

### Pattern 1: Iterative Pipeline Orchestrator (State Machine)

**What:** Unlike the linear pipelines in folio-enrich and folio-insights, this orchestrator implements a state machine with a feedback loop. After the initial linear sequence (ingest -> issue-spot -> explore), it enters an iterative cycle (research -> fact-map -> gap-analyze -> question -> termination-check) that loops until convergence.

**When to use:** When the pipeline outcome depends on incremental refinement through user interaction and diminishing-returns detection.

**Trade-offs:** More complex state management than a linear pipeline, but essential for the core product value. Checkpointing becomes critical because iterations can span hours or days (waiting for consumer responses).

```python
class IntakeOrchestrator:
    """State machine orchestrator with iterative analysis loop.

    Follows the folio-enrich PipelineOrchestrator pattern but adds
    loop control and convergence detection for the analysis cycle.
    """

    INITIAL_STAGES = ["ingest", "issue_spot", "explore"]
    LOOP_STAGES = ["research", "fact_map", "gap_analysis", "question"]
    FINAL_STAGES = ["output_format"]

    async def run(self, job: IntakeJob) -> IntakeJob:
        # Phase 1: Linear initial stages
        for stage_name in self.INITIAL_STAGES:
            job = await self._run_stage(stage_name, job)
            await self._checkpoint(job)

        # Phase 2: Iterative analysis loop
        while not self._convergence_detector.should_stop(job):
            job.iteration += 1
            for stage_name in self.LOOP_STAGES:
                job = await self._run_stage(stage_name, job)
                await self._checkpoint(job)

                # Question stage may pause for user response
                if stage_name == "question" and job.pending_questions:
                    job.status = JobStatus.AWAITING_RESPONSE
                    await self._save(job)
                    return job  # Resume when user responds

        # Phase 3: Final output
        for stage_name in self.FINAL_STAGES:
            job = await self._run_stage(stage_name, job)

        job.status = JobStatus.COMPLETED
        return job
```

### Pattern 2: Multi-Signal Convergence Detector

**What:** A weighted scoring function across five signals that determines when the iterative analysis loop should terminate. Each signal produces a 0.0-1.0 score; the weighted sum is compared against a configurable threshold.

**When to use:** When single stopping criteria (e.g., "3 iterations") are too crude. Legal analysis requires thoroughness but must avoid wasting resources on marginal improvements.

**Trade-offs:** More configuration surface area, but prevents both premature termination (missing issues) and infinite loops (wasting LLM tokens). Research on iterative AI systems confirms that multi-signal detection outperforms single-metric approaches.

```python
class ConvergenceDetector:
    """Multi-signal convergence detection for the analysis loop.

    Signals:
    - coverage_pct: fraction of claim elements with supporting facts
    - confidence_plateau: whether confidence scores stopped improving
    - iteration_count: hard cap relative to issue complexity
    - user_fatigue: response time and engagement degradation
    - diminishing_gaps: rate of new gaps discovered per iteration
    """

    def __init__(self, weights: ConvergenceWeights, threshold: float = 0.8):
        self.weights = weights
        self.threshold = threshold

    def should_stop(self, job: IntakeJob) -> bool:
        scores = {
            "coverage": self._score_coverage(job),
            "plateau": self._score_confidence_plateau(job),
            "iterations": self._score_iteration_count(job),
            "fatigue": self._score_user_fatigue(job),
            "diminishing": self._score_diminishing_gaps(job),
        }
        weighted = sum(
            getattr(self.weights, signal) * score
            for signal, score in scores.items()
        )
        return weighted >= self.threshold
```

### Pattern 3: Pluggable Research Tool Registry

**What:** A registry that discovers and manages legal research tools through two mechanisms: MCP servers (via the Model Context Protocol registry) and HTTP adapters (for REST APIs that predate MCP). Tools are registered per organization based on their subscriptions.

**When to use:** When the system must work with an open-ended set of research tools that vary by organization and evolve independently.

**Trade-offs:** The dual MCP+HTTP approach adds complexity but is necessary because many legal research APIs (Westlaw, CourtListener) predate MCP and won't adopt it immediately, while newer tools (folio-mcp) are MCP-native. The MCP 2026 roadmap's registry and server-as-agent capabilities will simplify this over time.

```python
class ResearchToolRegistry:
    """Discovers and manages research tools from MCP + HTTP sources."""

    def __init__(self, org_config: OrgConfig):
        self._mcp_tools: dict[str, MCPToolAdapter] = {}
        self._http_tools: dict[str, ResearchAdapter] = {}
        self._load_org_tools(org_config)

    async def research(
        self, query: ResearchQuery, jurisdictions: list[str]
    ) -> list[ResearchResult]:
        """Fan out to all configured tools in parallel, per jurisdiction."""
        tasks = []
        for jurisdiction in jurisdictions:
            for tool in self._get_tools_for_jurisdiction(jurisdiction):
                tasks.append(tool.search(query, jurisdiction))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._merge_and_deduplicate(results)
```

### Pattern 4: Fact-Claim-Element Graph (Relational, Not Graph DB)

**What:** A many-to-many mapping between facts (extracted from consumer narrative), claims (legal causes of action from FOLIO Objectives), and elements (required components of each claim). Stored as relational adjacency tables with confidence scores on each edge, not in a separate graph database.

**When to use:** When the graph is bounded in size (tens to hundreds of nodes per case, not millions) and the primary operations are traversal for gap analysis and rendering for visualization.

**Trade-offs:** A dedicated graph database (Neo4j) would provide richer traversal queries but adds operational complexity. For per-case graphs of this size, relational adjacency tables with JSON serialization perform well and keep the deployment simple. The three visualization modes (graph, matrix, narrative-anchored) all read from the same underlying data structure.

```python
class FactClaimGraph:
    """Many-to-many fact-claim-element mapping with confidence edges.

    Stored as relational tables but exposed as a traversable graph.
    Each edge carries: confidence score, source stage, iteration number,
    and supporting evidence references.
    """

    facts: list[Fact]              # Extracted from consumer narrative
    claims: list[Claim]            # FOLIO Objectives (IRIs)
    elements: list[Element]        # Required components per claim
    fact_claim_edges: list[Edge]   # Fact supports Claim (many-to-many)
    fact_element_edges: list[Edge] # Fact satisfies Element (many-to-many)

    def coverage_matrix(self) -> dict[str, dict[str, float]]:
        """Claims x Elements matrix with coverage percentages."""

    def uncovered_elements(self) -> list[Element]:
        """Elements with no supporting facts -- drives gap analysis."""

    def to_graph_json(self) -> dict:
        """D3-compatible node/link format for graph visualization."""

    def to_matrix_json(self) -> dict:
        """Row/column format for matrix visualization."""

    def to_narrative_anchors(self) -> list[NarrativeAnchor]:
        """Text spans linked to claims/elements for narrative view."""
```

### Pattern 5: Tenant-Isolated Configuration

**What:** Every request carries a tenant context that scopes database queries, feature flags, tool configurations, and LLM provider selection. The same codebase serves multi-tenant cloud (shared infra, row-level isolation) and single-tenant self-hosted (dedicated infra, single tenant).

**When to use:** When the same application must deploy in both SaaS and on-premises environments without codebase forks.

**Trade-offs:** Adds a TenantContext to every service call, which is boilerplate. But it prevents the most dangerous class of multi-tenant bugs (data leakage between tenants) and makes the single-tenant case trivial (one tenant, no isolation logic needed).

```python
@dataclass
class TenantContext:
    """Injected into every request via FastAPI dependency."""
    tenant_id: str
    org_config: OrgConfig       # Autonomy mode, tools, protocols, output format
    db_session: AsyncSession     # Tenant-scoped database session
    encryption_key: bytes        # Tenant-specific PII encryption key

    @property
    def is_single_tenant(self) -> bool:
        return self.org_config.deployment_mode == "self-hosted"
```

## Data Flow

### Primary Analysis Flow

```
Consumer Input (text/voice/doc)
    |
    v
[Ingest Stage]
    | Canonical text segments + metadata
    v
[Issue Spot Stage]
    | List of FOLIO Objective IRIs with confidence
    v
[Explore Stage] (3 layers: FOLIO edges + protocols + LLM)
    | Expanded issue set + safety flags + exploration questions
    v
+============================+
| ITERATIVE ANALYSIS LOOP    |  <-- loops until convergence
|                            |
| [Research Stage]           |  Fan-out to research tools per jurisdiction
|     | Authorities, statutes, case law per claim
|     v                      |
| [Fact Map Stage]           |  Map facts to claims/elements (graph edges)
|     | Updated fact-claim-element graph
|     v                      |
| [Gap Analysis Stage]       |  Find uncovered elements, weak confidence
|     | Prioritized gap list
|     v                      |
| [Question Stage]           |  Generate follow-up questions from gaps
|     | Questions -> consumer/professional -> answers
|     v                      |
| [Termination Check]        |  Multi-signal convergence scoring
|     | CONTINUE or COMPLETE
+============================+
    |
    v
[Output Format Stage]
    | Structured memo, triage routing, action items
    v
Delivery (CMS sync, download, display)
```

### Real-Time Communication Flow

```
Frontend (React)                    Backend (FastAPI)
     |                                    |
     |--- POST /sessions (create) ------->|
     |<-- session_id + WS URL ------------|
     |                                    |
     |=== WebSocket connect =============>|
     |                                    |
     |--- intake_submit (text/voice) ---->|
     |<-- stage_progress (ingest) --------|
     |<-- stage_progress (issue_spot) ----|
     |<-- issues_identified --------------|
     |<-- stage_progress (explore) -------|
     |<-- exploration_questions ----------|
     |--- exploration_responses --------->|
     |                                    |
     |<-- iteration_start (n=1) ---------|
     |<-- research_progress -------------|
     |<-- graph_update (partial) --------|
     |<-- gap_analysis_result -----------|
     |<-- follow_up_questions -----------|
     |--- user_answers ----------------->|
     |                                    |
     |<-- iteration_start (n=2) ---------|
     |<-- ... (loop continues) ----------|
     |                                    |
     |<-- analysis_complete -------------|
     |<-- final_output -----------------|
     |                                    |
     |=== WebSocket close ===============>|
```

### State Management

```
Backend (IntakeJob):                     Frontend (Zustand Stores):

IntakeJob                                sessionStore
  +-- id: UUID                             +-- sessionId
  +-- tenant_id: str                       +-- status
  +-- status: JobStatus                    +-- currentStage
  +-- iteration: int                       +-- iteration
  +-- segments: list[TextSegment]
  +-- issues: list[Issue]                analysisStore
  +-- graph: FactClaimGraph                +-- issues: Issue[]
  +-- gap_history: list[GapSnapshot]       +-- graph: GraphData
  +-- questions: list[Question]            +-- gaps: Gap[]
  +-- convergence_scores: list[Score]      +-- questions: Question[]
  +-- lineage: list[StageEvent]            +-- convergenceProgress: number
  +-- metadata: dict
                                         uiStore
                                           +-- viewMode: graph|matrix|narrative
                                           +-- selectedClaim: string|null
                                           +-- filterJurisdiction: string|null
```

### Key Data Flows

1. **Multi-modal ingestion:** Voice audio is streamed to ASR service (faster-whisper or Deepgram), transcribed text is segmented, documents are sent to folio-enrich bridge for extraction. All paths converge on canonical `TextSegment` objects with source attribution.

2. **Three-layer exploration:** FOLIO ontology edges provide structural connections (child custody -> family law -> domestic relations), screening protocols provide domain-expert knowledge (custody intake -> always screen for DV), and LLM reasoning provides open-ended discovery (narrative mentions "he controls the money" -> financial abuse). Results are merged and deduplicated by FOLIO IRI.

3. **Parallel research fan-out:** For each identified issue and each applicable jurisdiction, the research tool registry dispatches parallel requests. Results are normalized to a common `ResearchResult` schema with authority type, citation, relevance score, and source tool. The fact-map stage then integrates these into the graph.

4. **Graph-to-visualization pipeline:** The `FactClaimGraph` model is the single source of truth. The graph view serializes to D3-compatible JSON (nodes + links). The matrix view pivots to claims-as-rows, elements-as-columns with coverage cells. The narrative view maps back to original text spans with claim/element annotations.

5. **Convergence feedback loop:** Each iteration's gap analysis snapshot is compared to previous iterations. The convergence detector computes a weighted score. The score and contributing signals are sent to the frontend via WebSocket so the user can see progress toward completion. When the score crosses the threshold, the loop exits.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 concurrent sessions | Monolith is fine. Single FastAPI process handles WebSocket connections, pipeline execution, and API. SQLite+FAISS sufficient. Research tool fan-out provides natural concurrency. |
| 100-1K concurrent sessions | Separate pipeline workers from API server. Use Celery/ARQ task queue for pipeline execution. WebSocket connections via Redis pub/sub for horizontal scaling. PostgreSQL+pgvector required. |
| 1K+ concurrent sessions | Stateless API servers behind load balancer. Dedicated worker pool for LLM-heavy stages. Connection manager for WebSocket fan-out. Consider splitting research tool execution into separate microservice. |

### Scaling Priorities

1. **First bottleneck: LLM calls.** Each analysis loop iteration makes multiple LLM calls (issue-spotting, gap analysis, question generation). Rate limiting and per-task model routing (cheaper models for classification, expensive models for complex reasoning) addresses this. The folio-enrich `TaskLLMs` pattern is directly applicable.

2. **Second bottleneck: WebSocket connection management.** Long-running analysis sessions (hours/days when waiting for consumer responses) mean many open WebSocket connections. Redis pub/sub for cross-process message routing, with connection pooling and heartbeat-based cleanup.

3. **Third bottleneck: Research tool API rate limits.** External research APIs (CourtListener, Westlaw) have per-org rate limits. Per-tool rate limiting with queuing, and result caching (same jurisdiction + query = cached result across sessions).

## Anti-Patterns

### Anti-Pattern 1: Synchronous Pipeline Blocking

**What people do:** Run the entire analysis loop synchronously in the HTTP request handler, blocking until all iterations complete.
**Why it's wrong:** Analysis can take minutes to hours (especially with user interaction pauses). HTTP timeouts kill long-running requests. No progress visibility for the user.
**Do this instead:** Return the session ID immediately. Run the pipeline asynchronously (background task or worker queue). Push progress via WebSocket. Support pause/resume for user-interaction stages.

### Anti-Pattern 2: Separate Graph Database for Fact Mapping

**What people do:** Introduce Neo4j or similar for the fact-claim-element graph because "it's a graph problem."
**Why it's wrong:** Per-case graphs are small (10s-100s of nodes). A separate graph database adds deployment complexity, data synchronization challenges, and another failure mode. The multi-tenant/self-hosted requirement means every additional service doubles operational burden.
**Do this instead:** Store graph data as relational adjacency tables in the same database. Serialize to JSON for visualization. The graph operations needed (traversal for gap analysis, serialization for rendering) are O(n) on small graphs and don't benefit from graph database indexing.

### Anti-Pattern 3: Monolithic Screening Protocol Format

**What people do:** Hardcode screening logic in Python if/else chains, making protocol changes require code deployments.
**Why it's wrong:** Screening protocols must be configurable per organization, shareable as community assets, and updatable without redeployment. Legal professionals (not developers) define protocols.
**Do this instead:** Define protocols as structured data (YAML/JSON) with a condition/action schema. The protocol engine interprets these at runtime. Store in the database with org-scoping. Provide an admin UI for editing.

### Anti-Pattern 4: Coupling LLM Provider to Pipeline Logic

**What people do:** Import `openai` directly in pipeline stages, hardcoding provider-specific API calls throughout the codebase.
**Why it's wrong:** Organizations use different LLM providers (OpenAI, Anthropic, local Ollama). The alea-llm-client abstraction exists specifically for this purpose. Hardcoding prevents self-hosted deployments with local models.
**Do this instead:** All LLM calls go through alea-llm-client's `BaseAIModel` interface. Pipeline stages receive their LLM provider via dependency injection (following folio-enrich's `TaskLLMs` pattern). Different tasks can use different providers/models.

### Anti-Pattern 5: Storing PII in LLM Prompts Without Encryption

**What people do:** Pass raw consumer narratives (names, addresses, case details) to LLM providers without considering data residency, privilege, or consent.
**Why it's wrong:** Legal data is potentially attorney-client privileged. LLM providers may log prompts. GDPR/state privacy laws require data minimization. The system must support "no-LLM-training" guarantees.
**Do this instead:** PII-strip or pseudonymize before LLM calls where possible. Use provider APIs with data processing agreements (no training). Field-level encryption at rest. Consent tracking per data element. Audit logs for every external data transmission.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **folio-python** | Direct library import | Embedded in backend process. Loads OWL ontology at startup (~18K classes). Used for IRI lookup, taxonomy navigation, LLM-powered semantic search. Lightweight enough to embed. |
| **folio-enrich** | HTTP API bridge | Heavy document processing (PDF, DOCX extraction + FOLIO tagging). Runs as separate service. Bridge pattern in `services/documents/processor.py`. |
| **folio-insights** | HTTP API bridge | Knowledge extraction from legal texts. Used to populate the admin knowledge base with elements, best practices, pitfalls per legal area. |
| **folio-mcp** | MCP tool-use | Provides FOLIO ontology as MCP tools for LLM agent use during analysis. LLM can invoke FOLIO queries autonomously within the exploration stage. |
| **alea-llm-client** | Direct library import | Multi-provider LLM abstraction. `BaseAIModel` interface for all LLM calls. Supports OpenAI, Anthropic, and compatible providers. |
| **CourtListener API** | HTTP adapter | Open legal research API. Free tier with rate limits. Used for case law and opinion search. |
| **Westlaw/Lexis** | HTTP adapter | Commercial research APIs. Available per org subscription. Higher rate limits, broader coverage. |
| **Deepgram/AssemblyAI** | HTTP adapter | Cloud ASR services. Alternative to local faster-whisper. Better accuracy for legal terminology with custom vocabularies. |
| **Clio/MyCase/Legal Server** | HTTP adapter | CMS sync connectors. Push case data and analysis results. Pull existing case context. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **Frontend <-> API** | REST + WebSocket | REST for CRUD (sessions, protocols, config). WebSocket for real-time pipeline progress, question/answer exchange, and graph updates. |
| **API <-> Pipeline** | Async task dispatch | API layer enqueues pipeline jobs. Pipeline executes asynchronously. Progress emitted via event bus (in-process EventEmitter or Redis pub/sub). |
| **Pipeline <-> Services** | Direct async calls | Pipeline stages call services directly (same process). Services handle their own caching, rate limiting, and error recovery. |
| **Pipeline <-> Storage** | Repository pattern | Abstract repository interfaces. Pipeline stages never import storage implementation directly. Factory selects Postgres or SQLite backend at startup. |
| **Storage <-> Database** | SQLAlchemy (Postgres) / aiosqlite (SQLite) | Async database access. Migrations via Alembic for Postgres. Schema auto-create for SQLite. Both implement the same repository interface. |

## Build Order (Dependencies)

The following build sequence respects component dependencies. Each phase can begin only after its dependencies are complete.

```
Phase 1: Foundation (no dependencies)
  +-- Data models (session, analysis, graph, protocol, organization, job)
  +-- Storage abstraction (repository interfaces)
  +-- SQLite storage implementation (for rapid development)
  +-- Config system (env vars, tenant context)
  +-- Pipeline stage ABC + IntakeJob model

Phase 2: Core Pipeline (depends on Phase 1)
  +-- LLM service wrapper (alea-llm-client integration)
  +-- FOLIO service wrapper (folio-python integration)
  +-- Ingest stage (text passthrough first, voice/doc later)
  +-- Issue Spot stage (LLM + FOLIO IRI matching)
  +-- IntakeOrchestrator (linear-only mode, no loop yet)

Phase 3: Exploration & Research (depends on Phase 2)
  +-- Screening protocol data model + engine
  +-- Explore stage (3-layer: FOLIO edges, protocols, LLM)
  +-- Research adapter ABC + first adapter (CourtListener)
  +-- Research stage (parallel fan-out)
  +-- Research tool registry (HTTP adapters first)

Phase 4: Analysis Loop (depends on Phase 3)
  +-- FactClaimGraph model + operations
  +-- Fact Map stage
  +-- Gap Analysis stage
  +-- Question stage (question generation)
  +-- Convergence detector (multi-signal)
  +-- Termination stage
  +-- Orchestrator loop mode (iterative)

Phase 5: API & Real-Time (depends on Phase 4)
  +-- FastAPI app factory + routing
  +-- REST endpoints (sessions, admin, analysis)
  +-- WebSocket session management
  +-- Real-time progress streaming
  +-- Auth/tenant middleware

Phase 6: Frontend (depends on Phase 5)
  +-- Zustand stores (session, analysis, UI)
  +-- Intake UI (text input first)
  +-- Analysis dashboard (progress, issues)
  +-- Graph visualization (D3 force-directed)
  +-- Matrix visualization
  +-- Narrative-anchored visualization

Phase 7: Multi-Modal & Production (depends on Phase 6)
  +-- ASR service (voice input)
  +-- Document processor (folio-enrich bridge)
  +-- PostgreSQL storage implementation
  +-- Field-level PII encryption
  +-- CMS sync connectors
  +-- MCP tool registry integration
  +-- Output format stage (structured memos)

Phase 8: Deployment & Hardening (depends on Phase 7)
  +-- Docker multi-tenant configuration
  +-- Docker self-hosted configuration
  +-- Audit logging
  +-- Consent flow management
  +-- Protocol library (community sharing)
  +-- Performance optimization (caching, rate limiting)
```

**Build order rationale:** The pipeline is the product's core. Build it first, test it in isolation (CLI or simple API), then layer real-time communication and visualization on top. Multi-modal input and production infrastructure come last because text-only input exercises the full pipeline without ASR/document complexity. PostgreSQL and encryption are deferred because SQLite lets you iterate faster during development.

## Sources

- folio-enrich `PipelineStage` base class and `PipelineOrchestrator` (local codebase) -- HIGH confidence
- folio-insights `InsightsPipelineStage` and orchestrator with checkpointing (local codebase) -- HIGH confidence
- folio-python `FOLIO` class with OWL parsing, taxonomy navigation, LLM search (local codebase) -- HIGH confidence
- [IMPROVE: Iterative Model Pipeline Refinement](https://arxiv.org/html/2502.18530v1) -- iterative LLM pipeline convergence patterns -- MEDIUM confidence
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- tool registry and agent patterns -- HIGH confidence
- [MCP Registry Preview](https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/) -- pluggable tool discovery -- HIGH confidence
- [2026 MCP Roadmap](http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/) -- server-as-agent evolution -- MEDIUM confidence
- [Multi-Tenant Architecture Guide (WorkOS)](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture) -- tenant isolation patterns -- MEDIUM confidence
- [SaaS Multitenant Solution Architecture (Microsoft)](https://learn.microsoft.com/en-us/azure/architecture/guide/saas-multitenant-solution-architecture/) -- deployment patterns -- MEDIUM confidence
- [Neo4j: Legal Documents to Knowledge Graphs](https://neo4j.com/blog/developer/from-legal-documents-to-knowledge-graphs/) -- graph modeling for legal data -- MEDIUM confidence
- [FastAPI SSE for LLM Streaming](https://medium.com/@2nick2patel2/fastapi-server-sent-events-for-llm-streaming-smooth-tokens-low-latency-1b211c94cff5) -- real-time streaming patterns -- MEDIUM confidence
- [Zylos: Multi-Model AI Code Review](https://zylos.ai/research/2026-02-17-multi-model-ai-code-review) -- iterative convergence detection -- MEDIUM confidence

---
*Architecture research for: Legal intake system with iterative LLM analysis, ontology integration, and multi-modal input*
*Researched: 2026-03-22*
