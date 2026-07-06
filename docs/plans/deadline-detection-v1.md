# Plan — Deadline / SOL Detection

**Type:** CE feature (new work; improvement II.3.1). **Rubric:** must satisfy RUB-INTAKE-08
(detect + compute + surface) and RUB-INTAKE-09 (correct + primary-source-cited) under the
**locked v1.1 "required" decision** (Damien, 2026-07-05).

> **Scope revised 2026-07-05 (Damien):** deadlines are **REQUIRED, computed, correct, and
> cited to primary sources** — statutes, regulations, court rules (civil/criminal/local),
> judicial standing orders, and any other applicable primary authority — for the client's
> **actual state, across all 50 U.S. states** (plus federal authority for immigration). This
> is a large expansion over the shipped v1 "MN + generic, hedged" engine. Staged below:
> the shipped engine is the framework + seed; reaching 50-state correctness is a legal-content
> pipeline, honestly a multi-step CE effort, not a one-shot code change.

## Status (what's shipped vs remaining)
- **Shipped (v1, deployed):** the framework — `DeadlineEvent`/`Deadline` model, pure
  `compute_deadlines` engine, a small **cited** MN + generic rule table, LLM event detection,
  and prominent memo/action-item surfacing. Deterministic date math unit-tested.
- **Remaining (v1.1 target):** (a) drop hedge-as-default → compute-and-assert with a required
  primary-source citation; (b) scale the rule coverage from MN+generic to **all 50 states ×
  the covered matter types**, grounded in primary sources (see "50-state scaling" below);
  (c) per-deadline citation to the governing authority surfaced in the memo.

## Problem
The pipeline has no deadline/SOL detection (`ActionItem.deadline` hardcoded `None`, no date
math, no rule table). Every persona plants hard, dated deadlines (eviction hearing, 30-day
custody response, removal hearing, lapsed asylum 1-year) that the product must surface — the
single highest-stakes consumer value (missed deadlines end cases).

## Goal (v1)
For each intake, **detect** every time-sensitive event in the narrative + uploaded documents,
**compute** the resulting deadline where a small set of verified rules applies, and **surface**
all of them prominently in the memo + action items, always hedged. Deterministic-first
(gestalt): LLM extracts events (probabilistic) → deterministic rule table + date math →
deterministic surfacing.

## Non-goals
- No calendar/ICS export, no reminders/notifications yet (later II.3.1 phases).
- Not attempting to hand-curate every deadline for every matter type in one pass — coverage
  grows state-by-state, matter-by-matter, each entry cited + verified before it's trusted
  (see scaling). Uncovered (state, matter) pairs must **fail loudly / escalate**, never emit
  an uncited guess presented as authoritative (that would fail RUB-INTAKE-09).

## 50-state scaling — how "required + correct + primary-source-cited" is actually reached
The rule table cannot be a hardcoded MN block. Structure it as a **jurisdiction-keyed rule
registry** `rules[state][matter_type] -> [DeadlineRule{trigger, compute_fn, citation, source_url,
verified_by, verified_on}]`, populated by a **gestalt pipeline** (deterministic-first, LLM in
the middle, deterministic verify):
1. **Retrieve primary sources** for a (state, matter, trigger): statutes, court rules
   (civil/criminal/local), standing orders — from an authoritative corpus (e.g. official state
   code/rules sites, CourtListener, a licensed rules dataset). This is a data-acquisition task
   as much as code.
2. **Extract candidate rules** with an LLM (e.g. "response due N days after service under Rule
   X") — each candidate carries the quoted source text + citation.
3. **Verify deterministically before trust:** the computed offset must be reproducible by pure
   date math; the citation must resolve; a legal reviewer (or a high-bar LLM-judge + spot
   human review) signs off. Only **verified** rules become active; unverified → escalate/gap,
   never a confident output.
4. **Seed order:** persona states first (MN), then highest-A2J-need states, expanding on a
   cadence; each state's coverage tracked. Immigration = federal authority (INA/8 CFR/EOIR)
   plus related state-criminal deadlines.
This is a **standalone CE feature of real size** (legal-content + verification pipeline). It
should get its own `/ce:plan` + likely a curated/licensed rules data source; realistic honesty:
50-state correctness is incremental, gated per (state, matter) by the verification step —
the rubric's GATE then applies only where the app claims a computed deadline, and the app must
escalate rather than guess where coverage is absent.

## Architecture (gestalt: probabilistic detect → deterministic compute → deterministic surface)

1. **Detect (reuse extraction).** Extend the fact-extraction prompt/schema to tag
   time-sensitive events with a normalized structure: `{event_type, raw_text, date (ISO or
   null), trigger ("served"|"notice_posted"|"hearing"|"filed"|"incident"|...), jurisdiction
   hint}`. Events already partly covered (`time_period` fact category) — formalize a
   `DeadlineEvent` extraction alongside facts. Source span preserved (provenance).

2. **Compute (deterministic rule table).** New `app/services/deadline/`:
   - `rules.py` — a small, **human-reviewed, cited** table: e.g. MN eviction summons→hearing
     window (Minn. Stat. § 504B.321, 7–14 days, flag edge), MN family response = service + 30
     days (§ 518.—/Rule 303), generic "notice_date + N days" for a stated notice period,
     SOL "already lapsed?" check (compare event date + statutory window vs today). Each rule
     carries `{id, jurisdiction, citation, compute_fn, confidence, hedge_text}`.
   - `engine.py` — `compute_deadlines(events, jurisdiction, today) -> list[Deadline]` using
     `dateutil`/stdlib date math (weekend/holiday roll noted but flagged as "verify"). Pure,
     deterministic, unit-testable. Where no rule matches → passthrough event as
     `computed=False` (detected + hedged only).

3. **Surface (deterministic).**
   - New model `Deadline` (analysis-scoped): `{intake_id, run_id, event_text, trigger_date,
     computed_date, rule_id, citation, computed (bool), urgency, hedge, source_span}`.
   - Populate `ActionItem.deadline` (already exists) from computed deadlines so the action-items
     template renders them.
   - New memo section **"⏰ Deadlines & Time-Sensitive Items"** rendered FIRST (before CIRAC),
     each item: what, the (estimated) date + basis or "date unclear", and the hedge
     "This is an estimate — confirm the exact date with the court or a lawyer." Urgency sort.
   - Also feed the existing gap `procedural_requirement` type so unclear deadlines become
     gap questions ("What exact date were you served?").

## Wiring
- Detection runs in the extraction backfill (already the single pre-analysis hook) or as a
  dedicated orchestrator step after `fact_map`. Prefer: a `deadline_detect` stage appended to
  the orchestrator STAGES, reading events, calling the engine, persisting `Deadline` rows.
- Output assembly (`DataAssembler`) pulls `Deadline` rows into `OutputContext.deadlines`; the
  template engine renders the new top section. Decoupled from the LanguageAdapter change.

## Tests
- `test_deadline_engine.py`: deterministic — feed synthetic events (served 2026-06-15 → +30 =
  2026-07-15; notice 2026-03-03 + 14 = 2026-03-17; asylum entry 2019-08-14 +1yr lapsed by
  2026) → assert computed dates + `computed`/hedge flags. No LLM.
- `test_deadline_extraction.py`: mock LLM returns events; assert `DeadlineEvent`s persisted.
- Memo render test: a `Deadline` list produces the top section with hedge text.
- Persona validation (post-LLM-key): all 3 personas surface their planted deadlines with the
  right computed dates where a rule exists, hedged elsewhere.

## Rollout
- Land behind the existing analysis path (additive). No schema-destructive change (new table).
  On dev: `ALEA_SKIP_MIGRATIONS=true` + create_all builds the new `deadlines` table on restart
  (no column-type change, so no manual drop needed).
- Quality bar: rules are cited + human-reviewed; date math unit-tested; hedge everywhere.

## Open [PM] (II.3.1) — defer, not blocking v1 detect+hedge
Which jurisdictions after MN; how assertive the warnings; ICS/reminders. Batch to Damien at the
II.3.1 kickoff.
