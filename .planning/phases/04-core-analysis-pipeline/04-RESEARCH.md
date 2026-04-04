# Phase 4: Core Analysis Pipeline - Research

**Researched:** 2026-04-03
**Domain:** LLM-driven iterative legal analysis with agent-loop orchestration, DB checkpointing, and WebSocket progress
**Confidence:** HIGH

## Summary

Phase 4 builds the iterative analysis engine that consumes extracted facts (Phase 3) and FOLIO concept resolutions (Phase 2), maps them to legal claims and elements across jurisdictions, identifies gaps, generates consumer-friendly follow-up questions, and loops until multi-signal convergence. This is the analytical core of the system.

The architecture is an LLM-orchestrated agent loop backed by DB-persisted state. Each iteration runs stages (issue-spot, research-stub, fact-map, gap-analyze, question) with the LLM deciding stage progression. The pipeline uses `asyncio.create_task` for background execution, pushing stage-by-stage progress via the existing `IntakeConnectionManager` WebSocket infrastructure. Checkpointing after every stage enables pause/resume across sessions.

**Primary recommendation:** Build a stateless `AnalysisPipelineService` with per-stage methods orchestrated by an LLM-driven controller. Use dedicated SQLAlchemy models (`AnalysisRun`, `AnalysisIteration`, `AnalysisStage`, `AnalysisClaim`, `ClaimElement`, `FactClaimMapping`) for state persistence and audit trail. Use `asyncio.create_task` for async execution -- no external task queue needed at this scale.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Single LLM orchestrator per iteration -- one LLM call decides which stage to run next (agent-loop pattern). Stages: issue-spot, research, fact-map, gap-analyze, question. Orchestrator can skip irrelevant stages or re-run stages as needed.
- **D-02:** Hybrid execution model -- initial issue-spotting runs inline for fast feedback, then deeper analysis (research, mapping, gap analysis) runs as an async background job. WebSocket pushes stage-by-stage progress updates. Consumer can continue chatting while analysis proceeds.
- **D-03:** DB-persisted stage snapshots for checkpointing -- after each stage completes, save the full analysis state (current iteration, stage results, mappings, gaps) to dedicated DB models. Resume by loading the latest snapshot. Clean audit trail per ANALYSIS-09/ANALYSIS-10.
- **D-04:** Dual trigger model -- auto-triggers when N new facts accumulate since last analysis (threshold configurable per org), plus manual trigger available to consumer/professional at any time. Auto-trigger can be disabled per org.
- **D-05:** Multi-factor composite confidence scoring -- combine: (1) LLM mapping confidence, (2) FOLIO ConceptResolver match strength, (3) source fact confidence. Weighted composite with org-configurable weights.
- **D-06:** Parallel per-jurisdiction analysis -- when facts span jurisdictions, run separate analysis branches in parallel. Each jurisdiction gets its own claim/element/authority mappings. Results merged in output with jurisdiction labels.
- **D-07:** Dedicated mapping tables -- AnalysisClaim, ClaimElement, FactClaimMapping DB models with many-to-many relationships, confidence scores, jurisdiction metadata, and iteration tracking. Matches existing model pattern (ExtractedFact, FactSourceSpan).
- **D-08:** Discovered claims surfaced as "potential claims" with explanation -- claims the system discovers that weren't in the consumer's narrative are shown separately with a clear rationale. Consumer/professional decides whether to pursue.
- **D-09:** Four gap types detected -- unsupported elements (claim elements with no fact), unexplored claims (discovered but not investigated), weak mappings (low confidence), and procedural requirements (deadlines, filing requirements).
- **D-10:** LLM generates consumer-friendly questions grouped by topic -- LLM takes gap list + consumer context and generates natural-language questions grouped by topic area. Questions ranked by priority (highest-impact gaps first).
- **D-11:** All gaps presented as questions per iteration -- consumer answers what they can, skips what they can't. Remaining gaps carry to next iteration. No artificial cap on question count.
- **D-12:** Question rationale is configurable per org -- transparency setting controls whether questions include explanations of why they're being asked or stay conversational.
- **D-13:** All five convergence signals, weighted -- coverage % (elements with facts), confidence plateau (scores stop improving), iteration count (hard cap), user fatigue (skip rate, response time), diminishing gaps (fewer new gaps per iteration). Weighted combination with org-configurable thresholds.
- **D-14:** Default iteration hard cap: 10 iterations -- most cases converge in 3-5. Configurable per org.
- **D-15:** Progressive confidence indicator + summary at termination -- real-time progress indicator during iterations, comprehensive summary when convergence reached.
- **D-16:** Consumer and professional can override termination -- after convergence, consumer can say "I have more to add" or "keep digging." Resets some convergence signals and continues.

### Claude's Discretion
- Specific DB schema details for analysis state models (builds on existing patterns)
- LLM prompt design for the orchestrator, gap analysis, and question generation
- Convergence signal weight defaults and fatigue detection heuristics
- Stage-to-stage data flow serialization format
- Background job framework choice (existing async patterns vs. task queue)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANALYSIS-01 | Iterative analysis loop: issue-spot, research, fact-map, gap-analyze, question, loop | Agent-loop pattern with LLM orchestrator (D-01), stage methods in AnalysisPipelineService |
| ANALYSIS-02 | Many-to-many fact-to-claim-to-element mapping with confidence scores | Dedicated mapping tables (D-07), composite confidence scoring (D-05) |
| ANALYSIS-03 | Gap identification: unsupported elements, unexplored claims, weak mappings, procedural requirements | Four gap types (D-09) detected by gap-analyze stage |
| ANALYSIS-04 | Prioritized, consumer-friendly follow-up questions | LLM question generation from gaps (D-10), priority ranking by gap impact |
| ANALYSIS-05 | Questions grouped by topic to reduce fatigue | LLM topic grouping in question stage (D-10), topic field in FollowUpQuestion model |
| ANALYSIS-06 | Multi-signal loop termination: coverage, confidence plateau, iteration count, fatigue, diminishing gaps | Five convergence signals (D-13), ConvergenceEvaluator service |
| ANALYSIS-07 | Org-configurable termination weights and thresholds | AnalysisConfig model extending OrganizationConfig, JSON column for weights |
| ANALYSIS-08 | Parallel multi-jurisdictional analysis | Per-jurisdiction branches via asyncio.gather (D-06), jurisdiction labels on claims |
| ANALYSIS-09 | Checkpoint after every stage for pause/resume | DB-persisted stage snapshots (D-03), AnalysisStage model with full state |
| ANALYSIS-10 | Full audit trail: stages, sources, confidence scores | AuditLog integration + AnalysisStage.audit_json for per-stage detail |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy[asyncio] | 2.0.49 | Async ORM for analysis state models | Already in use, async session pattern established |
| alea-llm-client | >=0.3.0 | LLM calls for orchestrator, gap analysis, question generation | Already in use via LLMService pattern |
| folio-python[search] | >=0.2.1 | FOLIO concept resolution for claim mapping | Already in use via ConceptResolver |
| Pydantic | 2.12.5 | Schema validation for LLM structured output | Already in use for extraction schemas |
| asyncio (stdlib) | 3.13 | Background task execution, parallel jurisdiction analysis | No external dependency needed per D-02 discretion |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI BackgroundTasks | 0.135.1 | Trigger point for async analysis | Entry point for background pipeline launch |
| aiosqlite | >=0.22.0 | SQLite async for testing | Already in test fixtures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.create_task | Celery + Redis | Celery adds Redis dependency, deployment complexity; overkill for single-process analysis. Upgrade path available if horizontal scaling needed later. |
| Manual stage orchestration | LangGraph/LangChain | Adds large dependency tree, opinionated patterns; simpler to build a lightweight orchestrator matching existing service patterns |
| JSON checkpointing | Redis-based state | DB persistence is already established; Redis adds infra dependency without benefit for checkpoint use case |

**Installation:**
```bash
# No new dependencies needed -- all libraries already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
  services/
    analysis/
      __init__.py
      pipeline.py          # AnalysisPipelineService -- main orchestrator
      stages/
        __init__.py
        issue_spot.py      # Issue-spotting stage
        fact_map.py        # Fact-to-claim mapping stage
        gap_analyze.py     # Gap analysis stage
        question_gen.py    # Follow-up question generation
        research_stub.py   # Research stage stub (full impl in Phase 6)
      convergence.py       # ConvergenceEvaluator with multi-signal logic
      scoring.py           # Composite confidence scoring
      schemas.py           # Pydantic schemas for LLM I/O
      triggers.py          # Auto-trigger and manual trigger logic
  models/
    analysis.py            # All analysis DB models
  routers/
    analysis.py            # REST endpoints for trigger, status, resume
```

### Pattern 1: LLM Orchestrator Agent Loop
**What:** Single LLM call per iteration decides which stage to run next. The orchestrator receives current analysis state (iteration count, stage results, gaps, convergence signals) and returns the next action.
**When to use:** Every iteration of the analysis loop.
**Example:**
```python
# Orchestrator prompt returns structured JSON
class OrchestratorDecision(BaseModel):
    next_stage: Literal["issue_spot", "research", "fact_map", "gap_analyze", "question", "converge"]
    reasoning: str
    skip_stages: list[str] = []

async def run_iteration(self, run: AnalysisRun) -> AnalysisIteration:
    """Execute one iteration of the analysis loop."""
    iteration = await self._create_iteration(run)
    
    while True:
        decision = await self._call_orchestrator(run, iteration)
        
        if decision.next_stage == "converge":
            break
        
        stage_result = await self._execute_stage(
            decision.next_stage, run, iteration
        )
        await self._checkpoint_stage(iteration, decision.next_stage, stage_result)
    
    # Evaluate convergence
    converged = await self._convergence_evaluator.evaluate(run, iteration)
    iteration.converged = converged
    await self._session.flush()
    return iteration
```

### Pattern 2: DB-Persisted Checkpointing
**What:** After each stage completes, full analysis state is persisted as an AnalysisStage record with the stage output JSON. Resume loads the latest stage snapshot.
**When to use:** After every stage execution for fault tolerance.
**Example:**
```python
async def _checkpoint_stage(
    self,
    iteration: AnalysisIteration,
    stage_name: str,
    result: dict,
) -> AnalysisStage:
    """Persist stage results as a checkpoint."""
    stage = AnalysisStage(
        iteration_id=iteration.id,
        stage_name=stage_name,
        status="completed",
        result_json=result,
        audit_json={
            "sources_consulted": result.get("sources", []),
            "confidence_scores": result.get("confidences", {}),
            "duration_ms": result.get("duration_ms", 0),
        },
    )
    self._session.add(stage)
    await self._session.flush()
    
    # Also write to immutable audit log
    await self._audit_service.log_action(
        action=f"analysis.stage.{stage_name}",
        resource_type="analysis_iteration",
        resource_id=iteration.id,
        details=stage.audit_json,
    )
    return stage
```

### Pattern 3: Async Background Execution with WebSocket Progress
**What:** Initial issue-spotting runs inline (fast feedback), then deeper analysis runs as `asyncio.create_task`. Each stage completion pushes a WebSocket update via the existing IntakeConnectionManager.
**When to use:** Triggered by REST endpoint or auto-trigger.
**Example:**
```python
async def trigger_analysis(self, intake_id: int, session_id: int) -> AnalysisRun:
    """Start analysis: inline issue-spot, then background deep analysis."""
    run = await self._create_run(intake_id)
    
    # Inline issue-spotting for immediate feedback
    issue_result = await self._stages["issue_spot"].execute(run)
    await self._checkpoint_stage(run.current_iteration, "issue_spot", issue_result)
    await self._push_progress(session_id, "issue_spot", issue_result)
    
    # Background deep analysis
    asyncio.create_task(
        self._run_deep_analysis(run, session_id)
    )
    
    return run

async def _push_progress(self, session_id: int, stage: str, result: dict):
    """Push stage progress via WebSocket."""
    from app.routers.intake import manager
    await manager.send_to_session(session_id, {
        "type": "analysis_progress",
        "stage": stage,
        "status": "completed",
        "summary": result.get("summary", ""),
        "claims_found": result.get("claims_count", 0),
        "gaps_found": result.get("gaps_count", 0),
    })
```

### Pattern 4: Composite Confidence Scoring
**What:** Multi-factor confidence for fact-to-claim mappings combining LLM confidence, ConceptResolver match strength, and source fact confidence with org-configurable weights.
**When to use:** Every FactClaimMapping creation.
**Example:**
```python
@dataclass
class ConfidenceWeights:
    llm_weight: float = 0.4
    concept_weight: float = 0.3
    fact_weight: float = 0.3

def compute_composite_confidence(
    llm_confidence: float,
    concept_confidence: float,
    fact_confidence: float,
    weights: ConfidenceWeights | None = None,
) -> float:
    """Compute weighted composite confidence score."""
    w = weights or ConfidenceWeights()
    return (
        llm_confidence * w.llm_weight
        + concept_confidence * w.concept_weight
        + fact_confidence * w.fact_weight
    )
```

### Pattern 5: Parallel Multi-Jurisdiction Analysis
**What:** When facts reference multiple jurisdictions, run separate analysis branches concurrently via `asyncio.gather`. Each branch has its own claims, elements, and authority mappings.
**When to use:** When facts span jurisdictions (detected during issue-spotting).
**Example:**
```python
async def _run_jurisdictional_analysis(
    self, run: AnalysisRun, jurisdictions: list[str]
) -> list[dict]:
    """Run parallel analysis branches for each jurisdiction."""
    tasks = [
        self._analyze_jurisdiction(run, jurisdiction)
        for jurisdiction in jurisdictions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter successful results; log failures
    valid = []
    for j, r in zip(jurisdictions, results):
        if isinstance(r, Exception):
            logger.error("Jurisdiction %s analysis failed: %s", j, r)
        else:
            valid.append(r)
    return valid
```

### Anti-Patterns to Avoid
- **Monolithic pipeline function:** Do NOT put all stages in one giant async function. Each stage must be its own module/method for testability and independent retry.
- **In-memory state only:** Do NOT rely on Python objects for analysis state. If the process restarts mid-analysis, all progress is lost. DB checkpointing is mandatory (D-03).
- **Blocking LLM calls in event loop:** Always use `await` for alea-llm-client calls. The model.json_async() method is already async.
- **Unbounded iteration:** Always enforce the hard cap (D-14, default 10). The convergence evaluator must check iteration count before any other signal.
- **Mixing audit trail with analysis state:** The AuditLog (immutable, append-only) and AnalysisStage.audit_json (queryable per-stage detail) serve different purposes. Write to both.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM structured output parsing | Custom JSON parsing + regex | Pydantic model_validate on alea-llm-client .json_async().data | Edge cases in JSON extraction, escaping; Pydantic handles validation |
| Concept resolution | Custom embedding search | Existing ConceptResolver three-stage pipeline | Already built with proper scoring weights and multi-stage fallback |
| WebSocket progress broadcast | Custom socket management | Existing IntakeConnectionManager.send_to_session | Already handles multi-connection per session, error tolerance |
| Audit logging | Custom log tables | Existing AuditService.log_action | Consistent format, immutable, indexed |
| Async DB sessions | Manual connection management | Existing engine + AsyncSession pattern from conftest/intake router | Schema translate map, tenant isolation already handled |

**Key insight:** The existing codebase has well-established patterns for LLM calls, DB persistence, WebSocket communication, and audit logging. The analysis pipeline should compose these existing services rather than building parallel infrastructure.

## Common Pitfalls

### Pitfall 1: asyncio.create_task without Exception Handling
**What goes wrong:** Background tasks silently swallow exceptions. Analysis fails with no error surfaced to the user.
**Why it happens:** `asyncio.create_task` fire-and-forget; unhandled exceptions only appear as "Task exception was never retrieved" warnings.
**How to avoid:** Wrap the background coroutine in try/except, update the AnalysisRun status to "failed" on error, and push a WebSocket error notification. Store the error in the run's metadata_json.
**Warning signs:** Tests pass (because they await directly) but production background tasks silently fail.

### Pitfall 2: DB Session Scope in Background Tasks
**What goes wrong:** The background task uses a DB session that was closed when the original request completed.
**Why it happens:** FastAPI dependency-injected sessions are request-scoped. Background tasks outlive the request.
**How to avoid:** Create a NEW DB session inside the background task (using `engine.connect()` + `AsyncSession` as done in the WebSocket handlers). Never pass the request-scoped session to background tasks.
**Warning signs:** "Session is closed" or "Can't operate on closed transaction" errors.

### Pitfall 3: Convergence Signals Fighting Each Other
**What goes wrong:** Analysis oscillates -- convergence is nearly reached, new facts lower coverage, loop continues indefinitely until hard cap.
**Why it happens:** Single-signal convergence is brittle. A new consumer answer can reset coverage without improving overall quality.
**How to avoid:** Use the weighted multi-signal approach (D-13). Each signal contributes proportionally. A single signal regression should not override a strong combined score. Add hysteresis: once combined convergence score exceeds threshold, require it to drop significantly (not just marginally) before continuing.
**Warning signs:** Iterations consistently hitting the hard cap instead of converging in 3-5.

### Pitfall 4: N+1 Queries in Fact Loading
**What goes wrong:** Loading all facts for an intake with their source spans and concept mappings generates hundreds of individual queries.
**Why it happens:** Lazy loading in SQLAlchemy async sessions raises errors (greenlet_spawn). Developers add eager loading incrementally instead of designing the query upfront.
**How to avoid:** Use explicit `selectinload` or `joinedload` in the initial query. Design the fact-loading query for the analysis pipeline to include all needed relationships in one pass.
**Warning signs:** Slow analysis startup, many small queries visible in SQL logs.

### Pitfall 5: LLM Output Schema Drift
**What goes wrong:** LLM returns valid JSON but with unexpected structure (missing fields, extra nesting, string instead of list).
**Why it happens:** LLMs are probabilistic. Different providers/models format JSON differently. Schema enforcement varies by provider.
**How to avoid:** Always validate LLM output through Pydantic schemas (as done in FactExtractionService). Use default_factory for optional fields. Catch ValidationError and log the raw output for debugging. Consider retry with a corrected prompt on validation failure.
**Warning signs:** Sporadic "validation failed" errors in logs, empty analysis results.

### Pitfall 6: Stale Checkpoint Resume with Schema Changes
**What goes wrong:** Code deploys change the stage output format, but existing checkpoints have the old format. Resume fails to deserialize.
**Why it happens:** JSON columns don't enforce schema. Old snapshots persist in the DB.
**How to avoid:** Add a `schema_version` field to AnalysisStage. When resuming, check version compatibility. If incompatible, re-run the stage instead of deserializing the old checkpoint. Log the version mismatch.
**Warning signs:** Resume failures after deployments; works for new analyses but not resumed ones.

## Code Examples

### DB Models for Analysis State
```python
# backend/app/models/analysis.py
from datetime import datetime
from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import TenantBase


class AnalysisRun(TenantBase):
    """Top-level analysis run for an intake. Multiple runs possible per intake."""
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    # "running", "paused", "converged", "terminated", "failed"
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "auto", "manual"
    current_iteration_number: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=10)
    convergence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    convergence_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AnalysisIteration(TenantBase):
    """One iteration of the analysis loop within a run."""
    __tablename__ = "analysis_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    converged: Mapped[bool] = mapped_column(Boolean, default=False)
    convergence_signals_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AnalysisStage(TenantBase):
    """Result of a single stage within an iteration. Serves as checkpoint."""
    __tablename__ = "analysis_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iteration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AnalysisClaim(TenantBase):
    """A legal claim identified during analysis."""
    __tablename__ = "analysis_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_name: Mapped[str] = mapped_column(String(255), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "identified" (from narrative) or "discovered" (system-found potential claim)
    folio_iri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_potential: Mapped[bool] = mapped_column(Boolean, default=False)
    # True = discovered by system, not explicit in narrative (D-08)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    iteration_discovered: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ClaimElement(TenantBase):
    """A required element for a legal claim."""
    __tablename__ = "claim_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(Integer, nullable=False)
    element_name: Mapped[str] = mapped_column(String(255), nullable=False)
    element_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_satisfied: Mapped[bool] = mapped_column(Boolean, default=False)
    satisfaction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FactClaimMapping(TenantBase):
    """Many-to-many mapping between extracted facts and claim elements."""
    __tablename__ = "fact_claim_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_id: Mapped[int] = mapped_column(Integer, nullable=False)
    element_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    concept_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fact_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapping_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AnalysisGap(TenantBase):
    """An identified gap in the analysis."""
    __tablename__ = "analysis_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # "unsupported_element", "unexplored_claim", "weak_mapping", "procedural_requirement"
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = more important
    status: Mapped[str] = mapped_column(String(20), default="open")
    # "open", "addressed", "skipped"
    iteration_found: Mapped[int] = mapped_column(Integer, nullable=False)
    iteration_resolved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FollowUpQuestion(TenantBase):
    """A follow-up question generated from gap analysis."""
    __tablename__ = "follow_up_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic_group: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Only shown if org has transparency enabled (D-12)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # "pending", "answered", "skipped"
    answer_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iteration_asked: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

### Convergence Evaluator
```python
# backend/app/services/analysis/convergence.py
from dataclasses import dataclass

@dataclass
class ConvergenceWeights:
    """Default weights for convergence signals."""
    coverage: float = 0.30       # Elements with supporting facts
    confidence_plateau: float = 0.20  # Scores stopped improving
    iteration_cap: float = 0.10  # Approaching max iterations
    user_fatigue: float = 0.15   # Skip rate, response time
    diminishing_gaps: float = 0.25  # Fewer new gaps per iteration

@dataclass
class ConvergenceSignals:
    coverage_pct: float        # 0.0-1.0
    confidence_delta: float    # Change from previous iteration
    iteration_number: int
    max_iterations: int
    skip_rate: float           # Questions skipped / questions asked
    avg_response_time_sec: float
    new_gaps_count: int
    previous_gaps_count: int

class ConvergenceEvaluator:
    def __init__(self, weights: ConvergenceWeights | None = None, threshold: float = 0.75):
        self.weights = weights or ConvergenceWeights()
        self.threshold = threshold

    def evaluate(self, signals: ConvergenceSignals) -> tuple[bool, float]:
        """Evaluate convergence. Returns (converged, score)."""
        # Hard cap always terminates
        if signals.iteration_number >= signals.max_iterations:
            return True, 1.0
        
        scores = {
            "coverage": signals.coverage_pct,
            "confidence_plateau": 1.0 - min(abs(signals.confidence_delta), 0.1) / 0.1,
            "iteration_cap": signals.iteration_number / signals.max_iterations,
            "user_fatigue": min(signals.skip_rate * 2, 1.0),
            "diminishing_gaps": (
                1.0 - (signals.new_gaps_count / max(signals.previous_gaps_count, 1))
                if signals.previous_gaps_count > 0 else 0.5
            ),
        }
        
        combined = sum(
            scores[k] * getattr(self.weights, k)
            for k in scores
        )
        
        return combined >= self.threshold, round(combined, 4)
```

### LLM Orchestrator Prompt Design
```python
# backend/app/services/analysis/pipeline.py
ORCHESTRATOR_SYSTEM_PROMPT = """You are a legal analysis orchestrator. Given the current state of an iterative
legal analysis, decide what stage to run next.

Available stages:
- issue_spot: Identify potential legal claims from facts
- research: Look up legal elements required for identified claims (stub in Phase 4)
- fact_map: Map extracted facts to claim elements
- gap_analyze: Identify gaps in the analysis
- question: Generate follow-up questions for the consumer
- converge: Signal that this iteration is complete

Current analysis state will be provided as JSON.

Rules:
1. Always start an iteration with issue_spot if new facts have been added.
2. Skip research if claims haven't changed since last iteration.
3. Always run fact_map after issue_spot or research.
4. Run gap_analyze after fact_map.
5. Run question after gap_analyze if gaps exist.
6. Signal converge when all stages for this iteration are complete.

Return JSON: {"next_stage": "stage_name", "reasoning": "why", "skip_stages": ["stages to skip"]}"""
```

### Org-Configurable Analysis Settings
```python
# Extend OrganizationConfig with analysis-specific settings
# Add these fields to OrganizationConfig or create AnalysisConfig

ANALYSIS_CONFIG_DEFAULTS = {
    "auto_trigger_enabled": True,
    "auto_trigger_fact_threshold": 5,     # N new facts before auto-trigger
    "max_iterations": 10,
    "convergence_threshold": 0.75,
    "convergence_weights": {
        "coverage": 0.30,
        "confidence_plateau": 0.20,
        "iteration_cap": 0.10,
        "user_fatigue": 0.15,
        "diminishing_gaps": 0.25,
    },
    "confidence_weights": {
        "llm_weight": 0.4,
        "concept_weight": 0.3,
        "fact_weight": 0.3,
    },
    "question_transparency": True,  # Show rationale for questions (D-12)
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-pass LLM analysis | Iterative agent loops with convergence | 2024-2025 | Much higher quality; allows gap-filling and refinement |
| Celery for all background work | asyncio.create_task for I/O-bound | 2023-2024 | Simpler deployment, lower latency for LLM workloads |
| Custom state machines | DB-backed stage checkpointing | Ongoing | Resilience to failures, cross-session resume |
| Flat confidence scores | Composite multi-source confidence | 2024-2025 | More reliable scoring, explainable confidence |

**Deprecated/outdated:**
- sqlalchemy-fsm: Abandoned, last release 2022. Not async-compatible. Use manual status column transitions instead.
- BackgroundTasks for long-running work: FastAPI's BackgroundTasks runs after response but within the request scope. Not suitable for multi-minute analysis. Use `asyncio.create_task` directly.

## Open Questions

1. **Research Stage Depth in Phase 4**
   - What we know: The research stage is part of the loop (D-01) but full legal research tools come in Phase 6 (RESEARCH-01 through RESEARCH-10).
   - What's unclear: How much research capability should Phase 4 implement?
   - Recommendation: Implement a research stage stub that uses FOLIO adjacency discovery and existing ConceptResolver to identify claim elements. It will not query external legal databases. Phase 6 will replace the stub with full research tool integration.

2. **Auto-Trigger Interaction with Chat Flow**
   - What we know: Auto-trigger fires when N new facts accumulate (D-04). Facts are extracted per-message.
   - What's unclear: If analysis is already running and new facts arrive, should they queue for the next run or inject into the current run?
   - Recommendation: Queue for next run. A running analysis operates on a snapshot of facts at trigger time. New facts trigger a new run after the current one completes or at next threshold.

3. **User Fatigue Signal Sources**
   - What we know: Fatigue uses skip rate and response time (D-13).
   - What's unclear: Where to get response time data -- is it time between question delivery and consumer reply?
   - Recommendation: Measure time between follow-up question WebSocket delivery and the next consumer message on the same session. Store on FollowUpQuestion as response_time_sec. Skip rate = questions with status "skipped" / total questions per iteration.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 0.24+ |
| Config file | backend/pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_analysis_pipeline.py -x --timeout=30` |
| Full suite command | `cd backend && python -m pytest tests/ --timeout=30` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANALYSIS-01 | Full iterative loop executes all stages and terminates | unit | `pytest tests/test_analysis_pipeline.py::test_full_iteration_loop -x` | Wave 0 |
| ANALYSIS-02 | Facts mapped to claims/elements as many-to-many with confidence | unit | `pytest tests/test_analysis_pipeline.py::test_fact_claim_mapping_m2m -x` | Wave 0 |
| ANALYSIS-03 | Four gap types detected from analysis state | unit | `pytest tests/test_analysis_pipeline.py::test_gap_detection_four_types -x` | Wave 0 |
| ANALYSIS-04 | Follow-up questions generated from gaps with priority | unit | `pytest tests/test_analysis_pipeline.py::test_question_generation_priority -x` | Wave 0 |
| ANALYSIS-05 | Questions grouped by topic | unit | `pytest tests/test_analysis_pipeline.py::test_questions_grouped_by_topic -x` | Wave 0 |
| ANALYSIS-06 | Multi-signal convergence terminates loop | unit | `pytest tests/test_convergence.py::test_multi_signal_convergence -x` | Wave 0 |
| ANALYSIS-07 | Org config overrides convergence weights | unit | `pytest tests/test_convergence.py::test_org_configurable_weights -x` | Wave 0 |
| ANALYSIS-08 | Parallel jurisdiction analysis produces separate claim sets | unit | `pytest tests/test_analysis_pipeline.py::test_parallel_jurisdictions -x` | Wave 0 |
| ANALYSIS-09 | Stage checkpoint enables pause/resume | unit | `pytest tests/test_analysis_pipeline.py::test_checkpoint_pause_resume -x` | Wave 0 |
| ANALYSIS-10 | Audit trail records all stages with sources and confidence | unit | `pytest tests/test_analysis_pipeline.py::test_audit_trail_completeness -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_analysis_pipeline.py tests/test_convergence.py -x --timeout=30`
- **Per wave merge:** `cd backend && python -m pytest tests/ --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_analysis_pipeline.py` -- covers ANALYSIS-01 through ANALYSIS-05, ANALYSIS-08 through ANALYSIS-10
- [ ] `tests/test_convergence.py` -- covers ANALYSIS-06, ANALYSIS-07
- [ ] `tests/fixtures/analysis_fixtures.py` -- shared fixtures for analysis test data (mock claims, facts, gaps)

## Sources

### Primary (HIGH confidence)
- Project codebase -- all referenced files read directly:
  - `backend/app/services/extraction/fact_extraction.py` -- FactExtractionService pattern
  - `backend/app/services/folio/concept_resolver.py` -- ConceptResolver pipeline
  - `backend/app/services/llm_service.py` -- LLMService with per-org config
  - `backend/app/models/fact.py` -- ExtractedFact, FactSourceSpan model patterns
  - `backend/app/models/folio_concepts.py` -- ConceptMapping, graph node/edge patterns
  - `backend/app/models/intake.py` -- Intake, Message, Session model patterns
  - `backend/app/routers/intake.py` -- WebSocket handler and IntakeConnectionManager
  - `backend/app/services/intake/session_service.py` -- Session lifecycle management
  - `backend/app/services/audit_service.py` -- AuditService.log_action pattern
  - `backend/app/db/base.py` -- TenantBase declarative base
  - `backend/tests/conftest.py` -- Test fixture patterns
  - `backend/tests/test_fact_extraction.py` -- Test patterns with mocked LLM
- SQLAlchemy 2.0 async documentation -- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- FastAPI BackgroundTasks -- https://fastapi.tiangolo.com/tutorial/background-tasks/

### Secondary (MEDIUM confidence)
- FastAPI background task patterns with WebSocket -- https://hexshift.medium.com/implementing-background-tasks-with-websockets-in-fastapi-034cdf803430
- LLM agent loop convergence dynamics -- https://arxiv.org/html/2512.10350v5
- FastAPI long-running operations -- https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi

### Tertiary (LOW confidence)
- None -- all critical patterns verified against project codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in pyproject.toml and actively used
- Architecture: HIGH -- patterns derived from existing codebase conventions (service classes, model patterns, test patterns)
- Pitfalls: HIGH -- derived from real patterns observed in the codebase (session scoping, LLM output validation)
- Convergence logic: MEDIUM -- weight defaults and heuristics are reasonable starting points but may need tuning in practice

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable -- no dependency changes, patterns are project-internal)
