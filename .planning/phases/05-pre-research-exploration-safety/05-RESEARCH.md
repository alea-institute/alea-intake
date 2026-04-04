# Phase 5: Pre-Research Exploration & Safety - Research

**Researched:** 2026-04-04
**Domain:** Three-layer exploration engine, screening protocol library, continuous safety middleware
**Confidence:** HIGH

## Summary

Phase 5 adds two major subsystems to the existing analysis pipeline: (1) a three-layer exploration engine that runs as a new `explore` stage between `issue_spot` and `research` in the AnalysisOrchestrator, and (2) continuous per-message safety screening middleware on the WebSocket message handler. Both subsystems are powered by a shared screening protocol library with 16 seed protocols across three severity tiers (Critical, Elevated, Advisory).

The codebase already has all necessary integration points: the AnalysisOrchestrator has a clear `STAGES` list that can be extended, the `IssueSpotStage` demonstrates the exact pattern for building new stages (constructor injection, `execute()` method, Pydantic schema validation, DB persistence), the `ConceptResolver` provides FOLIO IRI deduplication, and the `adjacency.py` module provides graph-based FOLIO traversal. The WebSocket handler in `intake.py` has a clear message loop with type-based dispatch where screening middleware can hook in.

**Primary recommendation:** Build this phase in three layers: (1) DB models and protocol CRUD API, (2) the three-layer exploration stage integrated into the orchestrator, (3) the continuous screening middleware on the WebSocket handler. Use the existing stage pattern from `issue_spot.py` verbatim for the exploration stage structure.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** JSON protocol definitions stored in DB with versioning. Each protocol has: trigger conditions (area of law, keyword patterns, FOLIO concept matches), questions to ask, escalation actions, severity tier. CRUD via admin API. Runtime activation without redeployment.
- **D-02:** Bundled defaults + org uploads. System ships with 16 curated seed protocols. Orgs can create private protocols visible only to them. Orgs can opt to share protocols to a community pool visible to all orgs on the platform. Self-contained, no external marketplace.
- **D-03:** Org-level activation with mandatory flag. Each org has an active_protocols list with per-protocol config: mandatory (always runs even if professional skips), optional (professional can enable/disable per intake), or disabled. Critical-tier protocols are mandatory-by-default for new orgs.
- **D-04:** Semantic versioning with active-version pinning. Each protocol has semver (1.0, 1.1, 2.0). Orgs pin to a specific version. Running intakes always use the version active when the intake started -- no mid-conversation changes.
- **D-05:** Hybrid parallel approach -- cheap LLM "wide net" scan runs in parallel (via asyncio.gather) with sequential FOLIO -> Protocols -> expensive LLM pipeline. Results merged via ConceptResolver deduplication to FOLIO IRIs. Best of both: speed + precision.
- **D-06:** Configurable rounds with stability detection. Org sets min_rounds (default 1) and max_rounds (default 3). After each round, check if new issues were discovered. Stop when no new issues found (stable) or max_rounds reached. Exploration questions from each round feed into the next.
- **D-07:** New 'explore' stage between issue-spot and research in the analysis orchestrator: issue-spot -> EXPLORE -> research -> fact-map -> gap-analyze -> question. Exploration discovers new issues, which feed into research. Naturally fits the existing stage architecture from Phase 4.
- **D-08:** Lightweight per-message check + deep periodic scan. Every consumer message gets a fast keyword/pattern check against active protocol triggers (<50ms). If triggered, queue a deep screening run. Deep screening also runs periodically (e.g., every 3 messages or every new fact extraction).
- **D-09:** Separate systems: screening middleware + exploration stage. Per-message screening is a lightweight middleware/hook on every message. The exploration stage is the deep three-layer analysis within the orchestrator loop. Screening can trigger an out-of-band deep exploration if it detects something urgent. Two distinct code paths with different performance profiles.
- **D-10:** Priority-based interrupt model. Three tiers determine behavior:
  - **Critical** (immediate interrupt): DV/IPV, child abuse, elder abuse, self-harm, human trafficking -> immediate safety resources + mandatory questions
  - **Elevated** (queued for next pause): stalking, sexual assault, substance abuse, mental health crisis, immigration detention risk -> surface at next natural conversation break
  - **Advisory** (fold into exploration): housing instability, employment retaliation, financial exploitation, firearms access, custody concerns, medical neglect -> added to next exploration round
- **D-11:** Universal harm screening -- DV and all harm-based protocols run across ALL areas of law, not just family law.
- **D-12:** Full taxonomy ships as 16 seed protocols (5 Critical, 5 Elevated, 6 Advisory).
- **D-13:** Cross-cutting concerns: "Are you safe right now?" universal opener, safety planning resources, mandated reporting awareness flags.
- **D-14:** Trauma-informed conversational framing. Questions normalize the inquiry, offer opt-out, explain purpose when transparency enabled. Never clinical/legal jargon. Safety resources always visible.
- **D-15:** Question transparency configurable per org (carries forward from Phase 4, D-12). Applies to exploration questions as well.

### Claude's Discretion
- Protocol JSON schema design (fields, trigger condition syntax)
- Screening middleware implementation (hook into WebSocket message handler vs. FastAPI middleware)
- Deduplication algorithm for merging cheap-LLM and sequential-pipeline results
- Safety resource content (hotline numbers, organization-specific resources)
- Mandated reporting jurisdiction-specific rules

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXPLORE-01 | System performs pre-research exploration between issue-spotting and research phases | D-07: New `explore` stage in orchestrator STAGES list between `issue_spot` and `research`. Stage pattern from `IssueSpotStage` provides exact blueprint. |
| EXPLORE-02 | Exploration uses three layers: FOLIO ontology relationships, curated screening protocols, and LLM reasoning | D-05: Hybrid parallel -- cheap LLM in parallel with sequential FOLIO adjacency -> protocol matching -> expensive LLM. Existing `adjacency.py` and `ConceptResolver` are Layer 1. |
| EXPLORE-03 | Organizations can define mandatory safety screening protocols that run before analysis proceeds | D-01/D-03: Protocol CRUD API + org activation with mandatory/optional/disabled flags. `folio_admin.py` router pattern for admin CRUD. |
| EXPLORE-04 | Safety screening is continuous throughout the conversation, not just at intake start | D-08/D-09: Lightweight per-message screening hook in `_handle_text_message`. Fast keyword/pattern check (<50ms), deep scan on trigger or periodic interval. |
| EXPLORE-05 | Exploration depth is configurable per organization (1 round to "until stable") | D-06: `min_rounds`/`max_rounds` in org config + stability detection. Extend `AnalysisConfig` Pydantic model with exploration fields. |
| EXPLORE-06 | System explains why it's asking exploration questions (configurable transparency per org) | D-15: `question_transparency` field already exists on `AnalysisConfig`. Extend to exploration questions. |
| EXPLORE-07 | Open screening protocol library allows community-contributed protocols across organizations | D-02: `is_shared` flag on protocol model. Community pool = protocols with `is_shared=True`. Query by `owner_org_id IS NULL OR is_shared=True`. |
| EXPLORE-08 | Organizations can create private screening protocols not shared with the library | D-02: `owner_org_id` column + `is_shared=False` default. Private = org-owned and not shared. |
| EXPLORE-09 | Default DV screening protocol ships with the system for family law matters | D-11/D-12: DV is Critical-tier, runs across ALL areas of law. One of 16 seed protocols loaded on first boot. |
| EXPLORE-10 | Exploration can surface entirely new legal issues not in the initial issue-spotting | D-05/D-07: Exploration-discovered issues become new `AnalysisClaim` records with `is_potential=True` and `claim_type="discovered"`. Feeds into research stage. |
</phase_requirements>

## Standard Stack

### Core

All dependencies already in the project. No new packages required.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0+ | Protocol models, screening state models | Already used for all DB models via TenantBase/SharedBase |
| Pydantic v2 | 2.x | Protocol JSON schema, exploration stage I/O schemas | Already used for all analysis stage schemas |
| asyncio | stdlib | Parallel exploration (asyncio.gather for D-05) | Already used in orchestrator for parallel jurisdiction analysis |
| alea-llm-client | existing | Cheap and expensive LLM calls for exploration layers | Already wrapped by LLMService with per-org config |
| folio-python | existing | FOLIO adjacency traversal for Layer 1 | Already used via adjacency.py and ConceptResolver |
| FastAPI | existing | Protocol admin CRUD API, screening middleware | Already used for all routers |

### Supporting

No new dependencies. The phase uses only existing infrastructure.

### Alternatives Considered

None applicable -- all decisions are locked, and the existing stack covers every need.

**Installation:**
```bash
# No new packages required -- all dependencies already installed
```

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
  models/
    screening.py           # ScreeningProtocol, ProtocolVersion, OrgProtocolActivation, ScreeningEvent
  services/
    exploration/
      __init__.py
      engine.py            # ExplorationEngine (three-layer + round loop)
      layers.py            # Layer implementations (FOLIO adjacency, protocol match, LLM reasoning)
      schemas.py           # Pydantic schemas for exploration I/O
    screening/
      __init__.py
      middleware.py         # ScreeningMiddleware (per-message fast check)
      protocol_service.py   # ProtocolService (CRUD, activation, version management)
      trigger_matcher.py    # TriggerMatcher (keyword/pattern/FOLIO concept matching)
      seed_protocols.py     # 16 seed protocol definitions as Python dicts
  services/analysis/
    stages/
      explore.py           # ExploreStage (integrates into orchestrator)
  routers/
    screening_admin.py     # Protocol CRUD + activation admin endpoints
```

### Pattern 1: Exploration Stage (follows IssueSpotStage pattern exactly)
**What:** New stage class `ExploreStage` with `execute()` method that runs the three-layer exploration engine.
**When to use:** Called by `AnalysisOrchestrator` between `issue_spot` and `research` stages.
**Example:**
```python
# Source: existing pattern from backend/app/services/analysis/stages/issue_spot.py
class ExploreStage:
    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
        org_config: dict | None = None,
    ) -> None:
        self._llm = llm_service
        self._session = db_session
        self._folio = folio
        self._embedding_service = embedding_service
        self._org_config = org_config or {}

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        claims: list[AnalysisClaim],
        facts: list[ExtractedFact],
    ) -> dict:
        """Execute exploration: three layers in parallel, multi-round stability."""
        engine = ExplorationEngine(
            folio=self._folio,
            llm_service=self._llm,
            embedding_service=self._embedding_service,
            db_session=self._session,
            org_config=self._org_config,
        )
        return await engine.explore(run, iteration, claims, facts)
```

### Pattern 2: Three-Layer Parallel Exploration (D-05)
**What:** Cheap LLM runs in parallel with sequential FOLIO -> Protocols -> Expensive LLM pipeline. Results merged via ConceptResolver deduplication.
**When to use:** Each exploration round within the ExplorationEngine.
**Example:**
```python
# Source: D-05 hybrid parallel approach
async def _run_exploration_round(self, context: ExplorationContext) -> ExplorationRoundResult:
    """Single exploration round with parallel execution."""
    # Branch A: Cheap LLM wide-net scan (fast)
    cheap_task = self._layer_cheap_llm(context)

    # Branch B: Sequential precision pipeline
    async def _sequential_pipeline():
        folio_results = await self._layer_folio_adjacency(context)
        protocol_results = await self._layer_protocol_match(context, folio_results)
        expensive_results = await self._layer_expensive_llm(context, folio_results, protocol_results)
        return folio_results + protocol_results + expensive_results

    sequential_task = _sequential_pipeline()

    # Run both branches in parallel
    cheap_results, sequential_results = await asyncio.gather(cheap_task, sequential_task)

    # Merge and deduplicate via ConceptResolver FOLIO IRIs
    merged = self._deduplicate_results(cheap_results + sequential_results)
    return merged
```

### Pattern 3: Screening Protocol DB Model (D-01)
**What:** Protocol definitions stored as versioned JSON in DB with trigger conditions, questions, escalation actions.
**When to use:** For the screening protocol library (seed + org-created + community-shared).
**Example:**
```python
# Source: follows TenantBase pattern from models/analysis.py, but protocols
# are SharedBase (cross-org community pool) with org activation in TenantBase
class ScreeningProtocol(SharedBase):
    """A screening protocol definition in the community library."""
    __tablename__ = "screening_protocols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    severity_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # critical, elevated, advisory
    owner_org_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = system seed
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)  # system-shipped
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProtocolVersion(SharedBase):
    """Versioned protocol content with trigger conditions and questions."""
    __tablename__ = "protocol_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)  # semver: "1.0.0"
    trigger_conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    questions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    escalation_actions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    safety_resources_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OrgProtocolActivation(TenantBase):
    """Per-org protocol activation with mandatory/optional/disabled status."""
    __tablename__ = "org_protocol_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[int] = mapped_column(Integer, nullable=False)
    pinned_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    activation_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # mandatory, optional, disabled
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

### Pattern 4: Screening Middleware Hook (D-08/D-09)
**What:** Lightweight per-message screening hook that runs before/after `_handle_text_message` processing in the WebSocket handler.
**When to use:** Every consumer message gets a fast keyword/pattern check.
**Example:**
```python
# Source: hooks into existing _handle_text_message in routers/intake.py
async def screen_message(
    content: str,
    session_id: int,
    active_protocols: list[OrgProtocolActivation],
    trigger_matcher: TriggerMatcher,
) -> ScreeningResult:
    """Fast per-message screening against active protocol triggers (<50ms).

    Returns immediately with any triggered protocols, does NOT run deep analysis.
    Deep analysis queued separately if critical trigger detected.
    """
    triggered = trigger_matcher.match_fast(content, active_protocols)
    return ScreeningResult(
        triggered_protocols=triggered,
        needs_deep_scan=any(t.severity_tier == "critical" for t in triggered),
        needs_queued_scan=any(t.severity_tier == "elevated" for t in triggered),
    )
```

### Pattern 5: Orchestrator Integration (D-07)
**What:** Modify `AnalysisOrchestrator.STAGES` and `_get_stage_instance` to include `explore` between `issue_spot` and `research`.
**When to use:** After exploration stage is built.
**Example:**
```python
# Source: modification to existing orchestrator.py
class AnalysisOrchestrator:
    STAGES = ["issue_spot", "explore", "research", "fact_map", "gap_analyze", "question_gen"]
    #                        ^^^^^^^^ NEW

    def _get_stage_instance(self, stage_name: str) -> Any:
        # ... existing stage instances ...
        if stage_name == "explore":
            from app.services.analysis.stages.explore import ExploreStage
            return ExploreStage(
                llm_service=self._llm,
                db_session=self._session,
                folio=self._folio,
                embedding_service=self._embedding_service,
                org_config=self._org_config,
            )
```

### Anti-Patterns to Avoid
- **Running all 16 protocols on every message:** Only run protocols activated for the org. Pre-filter by activation_mode != "disabled".
- **Blocking the WebSocket on deep screening:** Fast keyword check is synchronous-fast (<50ms). Deep LLM-based screening must be queued as a background task, never blocking the message loop.
- **Mid-conversation protocol version changes:** Pin protocol version at intake start per D-04. Store the pinned_version_id on the intake/session, not looked up dynamically.
- **Storing protocol definitions in TenantBase:** Protocols are cross-org shared resources (community pool). Store in SharedBase. Only activations are per-tenant (TenantBase).
- **Hand-rolling keyword matching:** Use compiled regex patterns stored in trigger_conditions_json. Pre-compile on protocol load, not per-message.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FOLIO adjacency traversal | Custom graph walker | `adjacency.discover_adjacent_concepts()` | Already handles hierarchy + OWL properties with depth limits and max_nodes safety cap |
| FOLIO IRI deduplication | Custom string matching | `ConceptResolver.resolve_concepts()` | Three-stage pipeline with confidence scoring already handles dedup across sources |
| LLM structured output parsing | Manual JSON parsing | Pydantic schema validation (as in `IssueSpotResult`) | Handles validation, defaults, type coercion; established pattern across all stages |
| Parallel async execution | Thread pools or custom orchestration | `asyncio.gather()` | Already used in orchestrator for parallel jurisdictions; standard Python async |
| Protocol trigger pattern matching | Custom pattern language | Compiled regex + set-based keyword lookup | Regex is standard for pattern matching; set lookup is O(1) for keywords |
| Semver comparison | Custom version parsing | `packaging.version.Version` or simple tuple comparison | Semver is well-defined; `packaging` is already a pip dependency |

**Key insight:** Every major component in this phase has an existing pattern or utility in the codebase. The exploration stage follows IssueSpotStage. The protocol models follow TenantBase/SharedBase. The admin CRUD follows folio_admin.py. The parallel execution follows the orchestrator's jurisdiction parallelism. The only truly new code is the trigger matching logic and the seed protocol content.

## Common Pitfalls

### Pitfall 1: Protocol Version Drift During Active Intake
**What goes wrong:** Org updates a protocol while an intake is in progress. New version has different questions or triggers.
**Why it happens:** Forgetting to snapshot the active version at intake start.
**How to avoid:** Store pinned_version_id on the intake session at creation time. All protocol lookups during that intake use the pinned version, never the latest. D-04 mandates this explicitly.
**Warning signs:** Tests that pass with single protocol version but fail when versions are updated mid-test.

### Pitfall 2: Screening Middleware Blocking WebSocket
**What goes wrong:** Deep LLM-based screening runs synchronously in the message handler, causing multi-second delays on every message.
**Why it happens:** Confusing the fast keyword check (D-08) with the deep exploration stage (D-09).
**How to avoid:** The per-message screening MUST be fast keyword/pattern/FOLIO-concept matching only (<50ms). Any LLM call or DB-heavy operation gets queued as a background task. Use `asyncio.create_task()` for the deep scan.
**Warning signs:** WebSocket message acknowledgment latency exceeding 100ms.

### Pitfall 3: Exploration Round Explosion
**What goes wrong:** Exploration discovers many new issues each round, causing rounds to never stabilize and hitting max_rounds.
**Why it happens:** Overly sensitive triggers or LLM hallucinating spurious legal issues.
**How to avoid:** Apply confidence thresholds to exploration-discovered issues (minimum confidence to count as "new"). ConceptResolver deduplication ensures the same concept discovered by multiple layers only counts once.
**Warning signs:** max_rounds consistently reached during testing with realistic scenarios.

### Pitfall 4: SharedBase vs TenantBase Confusion for Protocols
**What goes wrong:** Protocol definitions stored in TenantBase, making community sharing impossible. Or activations stored in SharedBase, breaking tenant isolation.
**Why it happens:** The project has both bases and the distinction is subtle.
**How to avoid:** Protocols themselves (definitions + versions) go in SharedBase (cross-org). Protocol activations (what each org enables) go in TenantBase (per-tenant). This mirrors the existing pattern where Organization is SharedBase but OrganizationConfig is TenantBase.
**Warning signs:** Queries for "community pool" protocols returning nothing because they're in a different tenant schema.

### Pitfall 5: Critical Safety Protocol Not Interrupting
**What goes wrong:** Consumer mentions domestic violence but the system doesn't immediately surface safety resources because the screening result is queued instead of interrupting.
**Why it happens:** Treating all severity tiers the same in the interrupt model.
**How to avoid:** D-10 mandates three distinct behaviors: Critical = immediate interrupt (send WebSocket safety message NOW), Elevated = queued for next pause, Advisory = fold into exploration. The immediate interrupt path must bypass the normal message flow.
**Warning signs:** No immediate WebSocket message when test scenario includes DV keywords.

### Pitfall 6: Seed Protocol Loading Race Condition
**What goes wrong:** Multiple workers start simultaneously, each trying to seed the 16 default protocols, causing duplicate rows.
**Why it happens:** No idempotency guard on seed loading.
**How to avoid:** Use `INSERT ... ON CONFLICT DO NOTHING` or check-then-insert with unique constraint on protocol slug. The seed loading should be idempotent.
**Warning signs:** Duplicate protocol slugs in the database after restart.

## Code Examples

### Trigger Conditions JSON Schema
```python
# Recommended schema for trigger_conditions_json in ProtocolVersion
{
    "keywords": ["domestic violence", "DV", "hit me", "afraid of partner", "restraining order"],
    "keyword_match_mode": "any",  # "any" or "all"
    "folio_concept_iris": [
        "https://folio.openlegalstandard.org/objective/DomesticViolence",
    ],
    "area_of_law_iris": [],  # Empty = universal (runs across ALL areas)
    "regex_patterns": [
        "\\b(hit|punch|slap|chok|stalk|threaten)\\w*\\b.*\\b(partner|spouse|husband|wife|boyfriend|girlfriend)\\b"
    ],
    "exclude_keywords": [],  # Keywords that suppress this trigger (reduce false positives)
    "min_confidence": 0.3,  # Minimum confidence from keyword matching to trigger
}
```

### Questions JSON Schema
```python
# Recommended schema for questions_json in ProtocolVersion
[
    {
        "question_id": "dv_safe_now",
        "text": "Are you safe right now?",
        "text_transparent": "Many people in situations like yours may be experiencing harm at home. Are you currently in a safe place?",
        "priority": 1,
        "is_mandatory": True,  # Must be asked even if professional skips
        "follow_up_if_yes": None,
        "follow_up_if_no": "dv_safety_plan",
        "trauma_informed_framing": True,
    },
    {
        "question_id": "dv_safety_plan",
        "text": "Do you have a safety plan or a safe place you can go?",
        "text_transparent": "We want to make sure you have support. Do you have a plan for your safety?",
        "priority": 2,
        "is_mandatory": True,
        "follow_up_if_yes": None,
        "follow_up_if_no": None,
        "trauma_informed_framing": True,
    },
]
```

### Escalation Actions JSON Schema
```python
# Recommended schema for escalation_actions_json in ProtocolVersion
{
    "immediate_resources": [
        {
            "name": "National Domestic Violence Hotline",
            "phone": "1-800-799-7233",
            "text": "Text START to 88788",
            "url": "https://www.thehotline.org",
            "available": "24/7",
        },
    ],
    "mandated_reporting_flag": True,
    "mandated_reporting_note": "In many jurisdictions, professionals are mandated reporters for suspected child abuse, elder abuse, or vulnerable adult abuse.",
    "flag_for_attorney_review": True,
    "pause_analysis": False,  # Critical protocols don't pause, they interrupt
}
```

### Exploration Config Extension for AnalysisConfig
```python
# Source: extend existing schemas.py AnalysisConfig
class ExplorationConfig(BaseModel):
    """Org-level exploration configuration (D-05, D-06)."""
    min_rounds: int = Field(default=1, ge=1, le=10)
    max_rounds: int = Field(default=3, ge=1, le=10)
    cheap_llm_provider: str | None = None  # Override org default for cheap scan
    cheap_llm_model: str | None = None
    stability_threshold: int = 0  # New issues count <= this = stable
    exploration_confidence_threshold: float = 0.4  # Min confidence for discovered issues
    question_transparency: bool = True  # Inherited from AnalysisConfig if not set

class AnalysisConfig(BaseModel):
    """Extended with exploration fields."""
    # ... existing fields ...
    exploration: ExplorationConfig = Field(default_factory=ExplorationConfig)
```

### Deduplication Algorithm (Claude's Discretion)
```python
# Merge cheap-LLM and sequential-pipeline results via ConceptResolver
async def _deduplicate_results(
    self,
    all_results: list[ExplorationResult],
) -> list[ExplorationResult]:
    """Deduplicate exploration results to FOLIO IRIs.

    Strategy:
    1. Group results by resolved FOLIO IRI (using ConceptResolver)
    2. For each IRI group, keep the result with highest confidence
    3. Results without IRI resolution kept if text is sufficiently distinct
    """
    iri_map: dict[str, ExplorationResult] = {}
    unresolved: list[ExplorationResult] = []

    for result in all_results:
        if result.folio_iri:
            existing = iri_map.get(result.folio_iri)
            if existing is None or result.confidence > existing.confidence:
                iri_map[result.folio_iri] = result
        else:
            # Try to resolve via ConceptResolver
            resolved = await resolve_concepts(
                result.description,
                folio=self._folio,
                embedding_service=self._embedding_service,
            )
            if resolved and resolved[0].confidence > 0.5:
                iri = resolved[0].iri
                result.folio_iri = iri
                existing = iri_map.get(iri)
                if existing is None or result.confidence > existing.confidence:
                    iri_map[iri] = result
            else:
                unresolved.append(result)

    return list(iri_map.values()) + unresolved
```

### Screening Middleware Integration Point
```python
# Source: modification to existing _handle_text_message in routers/intake.py
async def _handle_text_message(websocket, session_id, user_id, data, engine):
    content = data.get("content", "")
    party_id = data.get("party_id")

    async with engine.connect() as conn:
        # ... existing session setup ...

        # --- NEW: Per-message screening ---
        screening_result = await screen_message_fast(
            content=content,
            session_id=session_id,
            db_session=db_session,
        )

        # Critical tier: immediate interrupt
        if screening_result.has_critical:
            await websocket.send_json({
                "type": "safety_alert",
                "severity": "critical",
                "resources": screening_result.safety_resources,
                "questions": screening_result.mandatory_questions,
            })

        # Elevated tier: queue for next pause
        if screening_result.has_elevated:
            # Store queued screening event, surface at next conversation break
            await _queue_elevated_screening(db_session, session_id, screening_result)

        # Advisory tier: fold into next exploration round
        if screening_result.has_advisory:
            await _add_to_exploration_queue(db_session, session_id, screening_result)

        # --- Continue existing message handling ---
        message = await svc.store_message(...)
        # ... rest of existing flow ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static screening checklists | LLM-augmented screening with structured protocols | 2024-2025 | Catches implicit indicators, not just explicit keywords |
| Area-of-law-specific DV screening | Universal harm screening across all areas | D-11 (project decision) | DV detected in employment, housing, immigration contexts |
| Single-pass issue discovery | Multi-round iterative exploration with stability detection | D-06 (project decision) | Finds cascading issues (DV in custody -> child safety -> housing) |
| Synchronous screening blocking analysis | Async parallel screening with priority interrupts | D-08/D-09 (project decision) | <50ms per-message overhead with deep analysis in background |

## Open Questions

1. **Cheap LLM Selection**
   - What we know: Org config has llm_provider and llm_model for the primary LLM. D-05 wants a "cheap" LLM for the wide-net scan.
   - What's unclear: Should the cheap LLM be a separate config field, or should it always use the fastest/cheapest from the org's configured provider?
   - Recommendation: Add optional `cheap_llm_provider` and `cheap_llm_model` to `ExplorationConfig`. Default to org's primary provider with a smaller model (e.g., gpt-4o-mini if org uses openai, claude-3-haiku if anthropic). Falls back to primary model if not configured.

2. **Seed Protocol Loading Timing**
   - What we know: 16 seed protocols must ship with the system. They need to exist in the DB before any org can activate them.
   - What's unclear: When to load seeds -- application startup (lifespan), first org creation, or explicit admin action?
   - Recommendation: Load during application lifespan (after DB engine initialization) using idempotent upsert. Check count first to avoid unnecessary writes on every restart.

3. **Mandated Reporting Specifics**
   - What we know: D-13 mentions mandated reporting awareness flags. Laws vary by jurisdiction.
   - What's unclear: How much jurisdiction-specific mandated reporting logic to include in v1.
   - Recommendation: v1 ships with a generic mandated reporting awareness note in protocol escalation_actions. Jurisdiction-specific rules are flagged but not automated -- the protocol notes that "in many jurisdictions, professionals are mandated reporters" and flags the case for attorney review. Full jurisdiction-specific automation is v2 scope.

4. **ScreeningEvent Persistence Scope**
   - What we know: Every per-message screening check runs. D-10 says critical triggers get immediate action.
   - What's unclear: Should every screening check (including no-trigger results) be persisted for audit trail?
   - Recommendation: Persist only triggered events (ScreeningEvent records with protocol_id, trigger details, action taken). Non-triggered checks are too numerous for useful audit. The audit trail captures what was detected and what action was taken, not every clean scan.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pytest.ini` or `backend/pyproject.toml` |
| Quick run command | `cd backend && python -m pytest tests/test_exploration.py tests/test_screening.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPLORE-01 | Explore stage runs between issue_spot and research | unit | `pytest tests/test_exploration_stage.py::test_explore_in_orchestrator_stages -x` | Wave 0 |
| EXPLORE-02 | Three layers: FOLIO, protocols, LLM | unit | `pytest tests/test_exploration_engine.py::test_three_layer_parallel -x` | Wave 0 |
| EXPLORE-03 | Org-defined mandatory protocols | unit | `pytest tests/test_screening_protocols.py::test_mandatory_activation -x` | Wave 0 |
| EXPLORE-04 | Continuous per-message screening | unit | `pytest tests/test_screening_middleware.py::test_per_message_check -x` | Wave 0 |
| EXPLORE-05 | Configurable exploration depth | unit | `pytest tests/test_exploration_engine.py::test_round_stability_detection -x` | Wave 0 |
| EXPLORE-06 | Question transparency for exploration | unit | `pytest tests/test_exploration_stage.py::test_transparency_config -x` | Wave 0 |
| EXPLORE-07 | Community protocol sharing | unit | `pytest tests/test_screening_protocols.py::test_shared_protocol_visibility -x` | Wave 0 |
| EXPLORE-08 | Private org protocols | unit | `pytest tests/test_screening_protocols.py::test_private_protocol_isolation -x` | Wave 0 |
| EXPLORE-09 | DV seed protocol ships by default | unit | `pytest tests/test_seed_protocols.py::test_dv_protocol_seeded -x` | Wave 0 |
| EXPLORE-10 | Exploration surfaces new claims | unit | `pytest tests/test_exploration_engine.py::test_new_claims_discovered -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_exploration*.py tests/test_screening*.py tests/test_seed_protocols.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_exploration_stage.py` -- covers EXPLORE-01, EXPLORE-06
- [ ] `tests/test_exploration_engine.py` -- covers EXPLORE-02, EXPLORE-05, EXPLORE-10
- [ ] `tests/test_screening_protocols.py` -- covers EXPLORE-03, EXPLORE-07, EXPLORE-08
- [ ] `tests/test_screening_middleware.py` -- covers EXPLORE-04
- [ ] `tests/test_seed_protocols.py` -- covers EXPLORE-09

## Sources

### Primary (HIGH confidence)
- `backend/app/services/analysis/orchestrator.py` -- AnalysisOrchestrator STAGES list, _get_stage_instance(), stage execution pattern
- `backend/app/services/analysis/stages/issue_spot.py` -- IssueSpotStage as canonical stage implementation pattern
- `backend/app/services/folio/adjacency.py` -- discover_adjacent_concepts() for Layer 1
- `backend/app/services/folio/concept_resolver.py` -- resolve_concepts() for deduplication
- `backend/app/routers/intake.py` -- WebSocket handler message loop, IntakeConnectionManager
- `backend/app/routers/folio_admin.py` -- Admin CRUD router pattern with require_role
- `backend/app/models/analysis.py` -- TenantBase model pattern for analysis state
- `backend/app/models/organization.py` -- OrganizationConfig JSON column pattern
- `backend/app/db/base.py` -- TenantBase vs SharedBase separation
- `backend/app/services/analysis/schemas.py` -- AnalysisConfig Pydantic schema pattern

### Secondary (MEDIUM confidence)
- Phase 4 CONTEXT.md decisions D-01 through D-16 -- verified against implemented code
- Phase 5 CONTEXT.md decisions D-01 through D-15 -- implementation decisions from user discussion

### Tertiary (LOW confidence)
- Mandated reporting specifics -- jurisdiction-specific rules not researched in detail; recommendation is generic awareness flags for v1

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already in the project, no new packages
- Architecture: HIGH -- every pattern directly follows existing code patterns in the codebase
- Pitfalls: HIGH -- identified from direct code analysis (version pinning, async blocking, schema separation)
- Protocol design: MEDIUM -- JSON schema design is Claude's discretion, based on requirements analysis

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- no external dependencies to drift)
