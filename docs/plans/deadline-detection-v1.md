# Plan — Deadline / SOL Detection (v1, "detect + hedge")

**Type:** CE feature (new work; improvement II.3.1). **Rubric:** satisfies RUB-INTAKE-08
(surfacing) and RUB-INTAKE-09 (accuracy/honesty) under the **locked v1.0 "detect + hedge"**
decision — surface time-sensitive events prominently with a "verify the exact date" hedge;
compute a date only where a verified rule exists; never state a confident wrong date.

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

## Non-goals (v1)
- No comprehensive 50-state rule library. **Minnesota + a tiny generic ruleset only**, each
  rule human-reviewed and cited. Everything else is "detected + hedged, not computed."
- No calendar/ICS export, no reminders/notifications (II.3.1 later phases).
- No change to the "detect + hedge" gate — a computed date is always presented as "estimated,
  verify."

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
