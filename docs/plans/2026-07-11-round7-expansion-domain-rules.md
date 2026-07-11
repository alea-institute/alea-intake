# Round 7 — Expansion Domain Rules + Cross-Domain Guards (CE plan)

**Date:** 2026-07-11 · **Branch:** `round7-domain-rules` · **Rubric:** intake-quality-v1.3 (LOCKED — not amended)
**Canonical inputs:** `briefs/qa/2026-07-11-evidence-pack-answers.json` (7 accepted decisions),
`briefs/qa/2026-07-10-imm-rulings-answers.json` (strict rulings r1–r4 govern).

## Goal

Damien accepted all 7 recommendations from the INTAKE-PERSONAS pack. Implement every accepted
decision, re-run all 8 personas against the fixed dev deploy, judge under LOCKED v1.3 with the
updated answer keys, and ship an updated decision-instrument evidence pack. Target: core-3 stays
6/6; expansion reaches 6/6 or precisely-diagnosed residuals.

## Key architectural constraint (discovered)

Persona intakes run **unbound** (`practice_area_id: null`); analysis is practice-area-agnostic at
runtime. Therefore the domain guard (BUG-32/33) **cannot** read a bound practice area — it must
**infer** the domain deterministically from the narrative, then scope rules/probes to the inferred
domain. This is exactly "guard by practice area, not by patching individual personas."

## Decisions being implemented

- **D01 / BUG-34** — Author domain-rule sets (deadline rules + doctrine probes) for the 5 expansion
  areas: elder-exploitation, wage-theft, benefits-denial, employment-discrimination, consumer-debt.
  Every computed deadline carries its governing primary source (r3: uncited deadline = GATE fail).
  Lapsed deadlines computed, flagged lapsed, routed to exceptions (r2).
- **D01 / BUG-32** — Domain guards so deadline rules never fire cross-domain. Concrete: MN-scoped
  `mn_family_response_30d` (§518.12) force-fires on employment terminations, UI determinations, POA
  signings. `stated_court_date` mislabels realtor/severance/agency dates as "the court's own summons".
  `generic_notice_window` cites "notice or lease" on debt/bank letters. Guard by inferred domain.
- **D01 / BUG-33** — Doctrine-probe cross-domain bleed fixed the same way (probes scoped to domain;
  OFP/custody probes must not fabricate DV predicates in wage-theft/elder runs).
- **D02** — Reading level toward ~6th grade (RUB-10), especially `court_self_help`. Non-gating.
- **D03** — Fix bogus fact→element linkages (RUB-03 scored 1). Non-gating.
- **D04** — Eliminate "Supported (85%)" vs "not yet supported by any facts" self-contradiction —
  one source of truth for element support status. Non-gating.
- **D05** — Verify confidence-cap fix (5b25a70) holds: Retaliatory Eviction claim itself surfaces,
  not only via its probe. No rubric escalation.
- **D06** — Restore habitability claim to its full 4-element set (regressed to 3). Non-gating.
- **D07** — Add Minn. Stat. §504B.331 service-by-posting doctrine probe to the LT answer key
  (ANSWER-KEYS.md). Raises the judging bar this round.

Only D01 (BUG-32/33/34) is gating; D02/D03/D04/D06 are non-gating quality items; D05 is verification;
D07 is answer-key/judging.

## Task breakdown

1. **Domain classifier** — new `app/services/analysis/domain_classifier.py`: deterministic
   narrative→domain(s) inference (keyword table per area), returns matched domain set.
2. **Deadline rules** — add `domains` scope to `DeadlineRule`; author the 5 expansion rule sets
   (all cited + lapsed-routed); scope `mn_family_response_30d`→family, and constrain
   `stated_court_date`/`generic_notice_window` so they never mislabel non-court/non-notice events.
   Thread `domains` through `find_rule` / `compute_deadlines` (engine) / `deadline_detect` (classify
   from gathered text).
3. **Doctrine probes** — add `domains` scope to `DoctrineProbe`; author expansion probes (FDCPA
   validation, garnishment/exempt income, SOL-restart trap, §181.13 penalty, misclassification, UI
   misconduct carve-out, EEOC/MHRA, FMLA, severance-release, §609.2334/§626.557/POA revocation/OFP);
   scope existing probes to their domains; thread `domains` through `run_probes` / `gap_analyze`.
4. **D04** — one source of truth: suppress/close stale `unsupported_element` gaps at assembly time
   when the element is satisfied/mapped; align gap re-detection.
5. **D06** — strengthen issue_spot prompt with canonical habitability 4-element set.
6. **D02** — strengthen plain-language prompt + ensure court_self_help uses `plain`; light
   deterministic sentence-split post-pass.
7. **D07** — add §504B.331 service-by-posting probe to LT answer key + a matching deterministic LT
   probe so the system can satisfy the raised bar.
8. **Tests** — unit tests for classifier, every new rule (cited + lapsed), cross-domain non-firing
   guards, every new probe, probe non-bleed, D04 gap suppression. Full suite green.

## Verification plan

- Unit: `pytest` full backend suite green; new tests prove (a) each expansion deadline computes with
  its cite, (b) `mn_family_response_30d` does NOT fire on wage/benefits/elder/consumer served-events,
  (c) each expansion probe fires on its narrative and does NOT bleed into other domains.
- Live: push master → Railway redeploy (verify `/health` commit) → run all 8 personas
  (`persona_run.py`) → `folio_check.py --all` + `memo_checks.py`.
- Judge: 8 opus judge subagents vs LOCKED v1.3 + updated ANSWER-KEYS + sidecars; verdicts as FINAL
  message. Gate criteria 01/04/05/08/09/15.
- Pack: rebuild with decision-instrument generator (evidence chains verbatim), redeploy same artifact
  URL. Spend cap $10 (target $3–6), report actual.
