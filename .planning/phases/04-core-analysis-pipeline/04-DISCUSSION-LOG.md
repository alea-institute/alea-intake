# Phase 4: Core Analysis Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 04-core-analysis-pipeline
**Areas discussed:** Analysis loop architecture, Fact-to-claim mapping, Gap analysis & follow-up questions, Convergence & termination

---

## Analysis Loop Architecture

### Orchestration Model

| Option | Description | Selected |
|--------|-------------|----------|
| Single LLM orchestrator | One LLM call per iteration decides which stage to run next (agent-loop pattern) | ✓ |
| Fixed pipeline with stage skipping | Stages always run in defined order, individual stages can be skipped | |
| Event-driven stage triggers | Each stage emits events that trigger the next relevant stage | |

**User's choice:** Single LLM orchestrator
**Notes:** Simpler, more adaptive — can skip irrelevant stages or re-run stages

### Execution Model

| Option | Description | Selected |
|--------|-------------|----------|
| Background async job | Analysis runs as async task, WebSocket pushes progress | |
| Inline in WebSocket | Analysis stages execute as part of WebSocket message flow | |
| Hybrid | Initial issue-spotting inline, deeper analysis as background job | ✓ |

**User's choice:** Hybrid
**Notes:** Best UX — fast initial feedback, then async for heavy lifting

### Checkpointing

| Option | Description | Selected |
|--------|-------------|----------|
| DB-persisted stage snapshots | Save full analysis state to DB models after each stage | ✓ |
| JSON document per iteration | Write JSON document per iteration | |
| You decide | Claude picks based on existing patterns | |

**User's choice:** DB-persisted stage snapshots

### Trigger Model

| Option | Description | Selected |
|--------|-------------|----------|
| After sufficient new facts accumulate | Run when N new facts extracted since last run | |
| Explicit trigger by consumer/professional | Consumer clicks "Analyze" | |
| Both: auto + manual | Auto-triggers after threshold, manual trigger anytime | ✓ |

**User's choice:** Both: auto + manual

---

## Fact-to-Claim Mapping

### Confidence Scoring

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-factor composite score | Combine LLM confidence, FOLIO match strength, source fact confidence | ✓ |
| Single LLM-assigned score | LLM assigns 0-1 confidence | |
| Binary with qualitative flags | Supported/weak with qualitative reasons | |

**User's choice:** Multi-factor composite score

### Multi-Jurisdictional Analysis

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel per-jurisdiction | Separate analysis branches in parallel per jurisdiction | ✓ |
| Sequential with switching | Analyze primary jurisdiction first, then repeat | |
| Unified with annotations | Single pass with jurisdiction tags | |

**User's choice:** Parallel per-jurisdiction analysis

### DB Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated mapping tables | AnalysisClaim, ClaimElement, FactClaimMapping tables | ✓ |
| JSON document per run | Full mapping graph as JSON blob | |
| You decide | Claude picks based on existing patterns | |

**User's choice:** Dedicated mapping tables

### Discovered Claims

| Option | Description | Selected |
|--------|-------------|----------|
| Surface as "potential claims" | Show separately with explanation, consumer decides | ✓ |
| Include at lower confidence | Auto-include, gap analysis questions about them | |
| Flag for professional review only | Only professionals see discovered claims | |

**User's choice:** Surface as "potential claims" with explanation

---

## Gap Analysis & Follow-Up Questions

### Gap Types

| Option | Description | Selected |
|--------|-------------|----------|
| All four types | Unsupported elements, unexplored claims, weak mappings, procedural | ✓ |
| Elements + claims only | Focus on unsupported elements and unexplored claims | |
| You decide | Claude determines gap taxonomy | |

**User's choice:** All four types

### Question Generation

| Option | Description | Selected |
|--------|-------------|----------|
| LLM generates grouped by topic | Natural-language questions grouped by topic area, priority-ranked | ✓ |
| Template-based with LLM refinement | Predefined templates, LLM adapts wording | |
| Hybrid templates + LLM | Templates for common gaps, LLM for novel ones | |

**User's choice:** LLM generates consumer-friendly questions grouped by topic

### Questions Per Iteration

| Option | Description | Selected |
|--------|-------------|----------|
| 3-5 prioritized questions | Highest-priority questions, remaining carry to next iteration | |
| All gaps as questions | Present all gaps, consumer answers what they can | ✓ |
| Adaptive based on engagement | Start with 3, increase/decrease based on consumer behavior | |

**User's choice:** All gaps as questions

### Question Transparency

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable per org | Org setting controls whether questions include rationale | ✓ |
| Always explain | Every question includes brief rationale | |
| Never explain | Keep it conversational | |

**User's choice:** Configurable per org

---

## Convergence & Termination

### Convergence Signals

| Option | Description | Selected |
|--------|-------------|----------|
| All five signals, weighted | Coverage %, confidence plateau, iteration count, fatigue, diminishing gaps | ✓ |
| Coverage + iteration cap | Stop when coverage hits threshold OR cap reached | |
| You decide | Claude designs convergence model | |

**User's choice:** All five signals, weighted

### Iteration Hard Cap

| Option | Description | Selected |
|--------|-------------|----------|
| 10 iterations | Most cases converge in 3-5. Configurable per org | ✓ |
| 5 iterations | More conservative | |
| 20 iterations | Very thorough | |

**User's choice:** 10 iterations (default, configurable)

### Convergence UX

| Option | Description | Selected |
|--------|-------------|----------|
| Progressive indicator | Visual completeness indicator during iterations | |
| Summary at termination only | Summary when convergence reached | |
| Both: progress + summary | Real-time progress + comprehensive summary | ✓ |

**User's choice:** Both: progress + summary

### Override

| Option | Description | Selected |
|--------|-------------|----------|
| Consumer can request more | Consumer/professional can override and continue | ✓ |
| Professional override only | Only professionals can restart analysis | |
| No override | Once converged, analysis is final | |

**User's choice:** Yes — consumer can request more analysis

---

## Claude's Discretion

- DB schema details for analysis state models
- LLM prompt design for orchestrator, gap analysis, question generation
- Convergence signal weight defaults and fatigue detection heuristics
- Stage-to-stage data flow serialization
- Background job framework choice

## Deferred Ideas

None — discussion stayed within phase scope
