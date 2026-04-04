# Phase 5: Pre-Research Exploration & Safety - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 05-pre-research-exploration-safety
**Areas discussed:** Screening protocol architecture, Three-layer exploration engine, Continuous safety screening, DV default protocol & question design, Harm protocol scope & types, Integration with analysis loop, Protocol versioning & updates

---

## Screening Protocol Architecture

### Protocol Storage Model

| Option | Description | Selected |
|--------|-------------|----------|
| JSON/YAML in DB | Structured JSON with versioning, CRUD via admin API | ✓ |
| Python code per protocol | Python classes with execute() method | |
| Hybrid JSON + Python hooks | JSON for structure, Python for complex logic | |

**User's choice:** JSON/YAML protocol definitions in DB

### Community Library

| Option | Description | Selected |
|--------|-------------|----------|
| Bundled defaults + org uploads | Ship curated defaults, orgs create private or share to community | ✓ |
| External protocol registry | Separate service/repo | |
| File-based protocol packs | JSON/YAML files in deployment | |

**User's choice:** Bundled defaults + org uploads

### Activation Model

| Option | Description | Selected |
|--------|-------------|----------|
| Org-level with mandatory flag | Per-protocol: mandatory/optional/disabled | ✓ |
| Global mandatory + org optional | Platform-wide mandatories plus org additions | |

**User's choice:** Org-level activation with mandatory flag

---

## Three-Layer Exploration Engine

### Layer Interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential: FOLIO → Protocols → LLM | Each layer adds to previous | |
| Parallel all three | Run simultaneously, merge | |
| Hybrid parallel | Cheap LLM parallel + sequential FOLIO→Protocols→expensive LLM | ✓ |

**User's choice:** Hybrid — cheap LLM wide-net scan in parallel with sequential FOLIO → Protocols → expensive LLM
**Notes:** User proposed the hybrid approach. Cheap LLM catches colloquial/cultural patterns FOLIO might miss. ConceptResolver deduplicates both streams to FOLIO IRIs.

### Exploration Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable rounds + stability | Min/max rounds, stop when stable | ✓ |
| Fixed rounds per org | Always run exactly N rounds | |
| Until stable (no max) | Keep going until no new issues | |

**User's choice:** Configurable rounds with stability detection

---

## Continuous Safety Screening

### Per-Message Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Lightweight check + deep periodic | Fast keyword check per message, deep scan periodic | ✓ |
| Full screening every message | Three-layer on every message | |
| Background continuous scan | Async processing, never blocks | |

**User's choice:** Lightweight per-message check + deep periodic scan

### Interrupt Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Priority-based: immediate vs queued | Critical interrupts, elevated queues, advisory folds in | ✓ |
| Always queue for next pause | Never interrupt mid-conversation | |
| Always interrupt immediately | Any trigger interrupts | |

**User's choice:** Priority-based: immediate vs queued

---

## DV Default Protocol & Question Design

### DV Protocol Scope

**User's choice:** Universal harm screening — DV and all harm-based protocols run across ALL areas of law, not just family law
**Notes:** User explicitly expanded scope beyond family law. DV can surface in employment, housing, immigration, criminal defense, etc.

### Question Sensitivity

| Option | Description | Selected |
|--------|-------------|----------|
| Trauma-informed conversational | Normalize, offer opt-out, explain purpose | ✓ |
| Clinical screening format | Direct questions from instruments | |
| Professional-mediated only | Only shown to professionals | |

**User's choice:** Trauma-informed conversational framing

---

## Harm Protocol Scope & Types

### Default Protocol Count

| Option | Description | Selected |
|--------|-------------|----------|
| Core safety suite (5) | DV, child abuse, elder abuse, self-harm, trafficking | |
| DV only | Others as community protocols | |
| Comprehensive (16) | Full taxonomy: 5 critical + 5 elevated + 6 advisory | ✓ |

**User's choice:** Full taxonomy as seed protocols (16 protocols across 3 tiers)
**Notes:** User wanted comprehensive coverage. All 16 ship as seed protocols — orgs can customize, disable, or extend.

### Severity Tiers

| Option | Description | Selected |
|--------|-------------|----------|
| Three tiers: critical/elevated/advisory | Tier determines interrupt behavior | ✓ |
| Binary: urgent/standard | Simpler two-tier | |

**User's choice:** Three tiers

---

## Integration with Analysis Loop

### Orchestrator Integration

| Option | Description | Selected |
|--------|-------------|----------|
| New 'explore' stage | Between issue-spot and research in loop | ✓ |
| Pre-loop exploration | One-time pass before loop starts | |
| Both pre-loop + in-loop | Initial deep + lighter per iteration | |

**User's choice:** New 'explore' stage between issue-spot and research

### Screening vs Exploration Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Separate systems | Screening middleware + exploration stage | ✓ |
| Unified system | One system at different depths | |

**User's choice:** Separate systems: screening middleware + exploration stage

---

## Protocol Versioning

| Option | Description | Selected |
|--------|-------------|----------|
| Semver with active-version pinning | Orgs pin version, intakes lock at start | ✓ |
| Latest-always | Always use latest | |

**User's choice:** Semantic versioning with active-version pinning

---

## Claude's Discretion

- Protocol JSON schema design
- Screening middleware implementation approach
- Deduplication algorithm for merging exploration layers
- Safety resource content
- Mandated reporting jurisdiction rules

## Deferred Ideas

None — discussion stayed within phase scope
