# Phase 5: Pre-Research Exploration & Safety - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Three-layer exploration engine that runs between issue-spotting and research within the analysis loop to discover adjacent legal issues the consumer didn't mention. Plus continuous per-message safety screening that runs as middleware on every consumer message throughout the conversation. Includes a comprehensive harm-based protocol library with 16 seed protocols across three severity tiers.

</domain>

<decisions>
## Implementation Decisions

### Screening Protocol Architecture
- **D-01:** JSON protocol definitions stored in DB with versioning. Each protocol has: trigger conditions (area of law, keyword patterns, FOLIO concept matches), questions to ask, escalation actions, severity tier. CRUD via admin API. Runtime activation without redeployment.
- **D-02:** Bundled defaults + org uploads. System ships with 16 curated seed protocols. Orgs can create private protocols visible only to them. Orgs can opt to share protocols to a community pool visible to all orgs on the platform. Self-contained, no external marketplace.
- **D-03:** Org-level activation with mandatory flag. Each org has an active_protocols list with per-protocol config: mandatory (always runs even if professional skips), optional (professional can enable/disable per intake), or disabled. Critical-tier protocols are mandatory-by-default for new orgs.
- **D-04:** Semantic versioning with active-version pinning. Each protocol has semver (1.0, 1.1, 2.0). Orgs pin to a specific version. Running intakes always use the version active when the intake started — no mid-conversation changes.

### Three-Layer Exploration Engine
- **D-05:** Hybrid parallel approach — cheap LLM "wide net" scan runs in parallel (via asyncio.gather) with sequential FOLIO → Protocols → expensive LLM pipeline. Results merged via ConceptResolver deduplication to FOLIO IRIs. Best of both: speed + precision.
- **D-06:** Configurable rounds with stability detection. Org sets min_rounds (default 1) and max_rounds (default 3). After each round, check if new issues were discovered. Stop when no new issues found (stable) or max_rounds reached. Exploration questions from each round feed into the next.
- **D-07:** New 'explore' stage between issue-spot and research in the analysis orchestrator: issue-spot → EXPLORE → research → fact-map → gap-analyze → question. Exploration discovers new issues, which feed into research. Naturally fits the existing stage architecture from Phase 4.

### Continuous Safety Screening
- **D-08:** Lightweight per-message check + deep periodic scan. Every consumer message gets a fast keyword/pattern check against active protocol triggers (<50ms). If triggered, queue a deep screening run. Deep screening also runs periodically (e.g., every 3 messages or every new fact extraction).
- **D-09:** Separate systems: screening middleware + exploration stage. Per-message screening is a lightweight middleware/hook on every message. The exploration stage is the deep three-layer analysis within the orchestrator loop. Screening can trigger an out-of-band deep exploration if it detects something urgent. Two distinct code paths with different performance profiles.
- **D-10:** Priority-based interrupt model. Three tiers determine behavior:
  - **Critical** (immediate interrupt): DV/IPV, child abuse, elder abuse, self-harm, human trafficking → immediate safety resources + mandatory questions
  - **Elevated** (queued for next pause): stalking, sexual assault, substance abuse, mental health crisis, immigration detention risk → surface at next natural conversation break
  - **Advisory** (fold into exploration): housing instability, employment retaliation, financial exploitation, firearms access, custody concerns, medical neglect → added to next exploration round

### Harm Protocol Taxonomy (16 Seed Protocols)
- **D-11:** Universal harm screening — DV and all harm-based protocols run across ALL areas of law, not just family law. DV can surface in employment, housing, immigration, criminal defense, etc.
- **D-12:** Full taxonomy ships as seed protocols:
  - **Critical (mandatory-by-default):** (1) DV/IPV, (2) Child abuse/neglect, (3) Elder/dependent adult abuse, (4) Self-harm/suicidal ideation, (5) Human trafficking
  - **Elevated (enabled-by-default, optional):** (6) Stalking/harassment, (7) Sexual assault, (8) Substance abuse, (9) Mental health crisis, (10) Immigration detention risk
  - **Advisory (available, disabled-by-default):** (11) Housing instability, (12) Employment retaliation, (13) Financial exploitation, (14) Firearms access, (15) Custody/parental alienation, (16) Medical neglect
- **D-13:** Cross-cutting concerns built into all critical protocols: "Are you safe right now?" universal opener, safety planning resources (hotlines, shelters, emergency contacts), mandated reporting awareness flags.
- **D-14:** Trauma-informed conversational framing for sensitive topics. Questions normalize the inquiry ("many people in your situation experience..."), offer opt-out ("you don't have to answer"), explain purpose when transparency is enabled. Never use clinical or legal jargon. Safety resources always visible.
- **D-15:** Question transparency configurable per org (carries forward from Phase 4, D-12). Applies to exploration questions as well — org controls whether the system explains why it's asking exploration/screening questions.

### Claude's Discretion
- Protocol JSON schema design (fields, trigger condition syntax)
- Screening middleware implementation (hook into WebSocket message handler vs. FastAPI middleware)
- Deduplication algorithm for merging cheap-LLM and sequential-pipeline results
- Safety resource content (hotline numbers, organization-specific resources)
- Mandated reporting jurisdiction-specific rules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — Analysis orchestrator architecture, stage-based design, question transparency
- `.planning/phases/02-folio-ontology-integration/02-CONTEXT.md` — ConceptResolver, FOLIO adjacency discovery
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — Auth, encryption, tenant isolation patterns

### Existing Code
- `backend/app/services/folio/adjacency.py` — FOLIO graph-based adjacency discovery (Layer 1)
- `backend/app/services/folio/concept_resolver.py` — resolve_concepts() for FOLIO IRI matching (deduplication)
- `backend/app/services/analysis/orchestrator.py` — AnalysisOrchestrator stage loop (integration point)
- `backend/app/services/analysis/stages/` — Existing stage implementations to follow as pattern
- `backend/app/services/llm_service.py` — LLMService for cheap + expensive LLM calls
- `backend/app/models/analysis.py` — AnalysisStage model for exploration stage checkpoints
- `backend/app/routers/intake.py` — WebSocket handler (screening middleware integration point)

### Requirements
- `.planning/REQUIREMENTS.md` §Pre-Research Exploration & Safety — EXPLORE-01 through EXPLORE-10

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **adjacency.py**: FOLIO graph traversal — direct input to Layer 1 of exploration
- **ConceptResolver**: Maps text to FOLIO IRIs — used for deduplication between exploration layers
- **AnalysisOrchestrator**: Stage-based loop — exploration becomes a new stage between issue-spot and research
- **LLMService**: Per-org provider config — use for both cheap (fast scan) and expensive (deep reasoning) LLM calls
- **analysis/schemas.py**: Pydantic schema pattern — extend for protocol and exploration schemas

### Established Patterns
- **Stage architecture**: Each stage is a class with `execute()` method, independently testable
- **Org-configurable settings**: JSON config on Organization model — extend for protocol activation
- **DB models**: TenantBase with JSON metadata columns — use for protocol definitions

### Integration Points
- Exploration stage inserts into orchestrator's stage sequence (after issue-spot, before research)
- Screening middleware hooks into WebSocket message handler (before/after text_message processing)
- Protocol CRUD via admin API (new router, follows folio_admin pattern)
- Exploration-discovered issues feed back into issue-spotting as new AnalysisClaim records

</code_context>

<specifics>
## Specific Ideas

- DV screening is **universal** — runs in every area of law, not just family law
- "Are you safe right now?" is a mandatory opener for any critical-tier protocol trigger
- Mandated reporting awareness should flag jurisdiction-specific reporting obligations
- Cheap LLM in the parallel branch uses the fastest/cheapest available provider from org config

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-pre-research-exploration-safety*
*Context gathered: 2026-04-04*
