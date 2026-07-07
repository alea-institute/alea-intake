# Intake Quality Rubric — v1.2 (LOCKED; amended by Damien 2026-07-07)

**Rubric ID prefix:** `RUB-INTAKE-`
**Applies to:** the alea-intake analysis pipeline output for a single client intake — the FOLIO mappings, claim/element analysis, gap analysis, deadline surfacing, plain-language memo, and export artifacts.
**Judged against:** the client's messy first-person narrative + any uploaded documents (the *source of truth*), the FOLIO ontology (via deterministic `folio-python` checks first, FOLIO MCP for semantic-fit calls), and this rubric.
**Status:** **LOCKED v1.2** (v1.1 Damien 2026-07-05; v1.2 amendment Damien 2026-07-07 — semantic-fit sub-criterion added to RUB-INTAKE-05, see below). Campaign findings cite `intake-quality-v1.2`. Amendments bump the version and trigger re-judging of affected findings.

**Lock decisions (Damien, 2026-07-05):**
- **Deadlines are REQUIRED and must be computed correctly (v1.1 — supersedes v1.0's "detect+hedge").** RUB-INTAKE-08/09 now hard-gate: the system must **compute** each applicable deadline for the correct jurisdiction and **cite the governing primary source** — statutes, regulations, court rules (civil / criminal / local rules), judicial standing orders, and any other applicable primary authority. **Scope = any of the 50 U.S. states** (not MN-only). A missing or wrong required deadline is a GATE failure. (Reasonable, clearly-labeled hedging on genuinely ambiguous facts — e.g., "confirm your exact service date" — is still allowed where the *input* is uncertain, but the *rule and computation* must be correct and sourced.)
- **Reading-level target (RUB-10): ~6th grade** (tightened from 6th–8th).
- **i18n spot-check (RUB-12): English, Spanish, Chinese** each inner loop; all 7 on the final 8–10 pass.
- **Practice-area rubrics (Q4): YES.** In addition to this general rubric, maintain **practice-area rubric addenda** (landlord-tenant, family law, immigration, + the final-pass areas) that pin the domain-specific issues, claims/elements, deadlines, and primary sources a good analysis must hit. See `docs/rubrics/practice-areas/`. (Separately, on binding: personas still run *unbound* — the pipeline is practice-area-agnostic — so the addenda are judging oracles, not a required runtime binding.)
- Group weights accepted as drafted (deadlines remain GATE, so weight is secondary to the pass/fail gate).

---

## How scoring works

Each criterion is scored on a **0–3 scale** with concrete anchors, plus a **weight**. A run's rubric score is the weighted mean. Criteria marked **[GATE]** are pass/fail blockers: any GATE failure caps the whole run at "borderline" regardless of the weighted mean, because it represents a way the product actively misleads or harms a vulnerable self-represented person.

| Score | Meaning |
|---|---|
| **3 — Excellent** | Meets the bar a legal-aid attorney would sign off on. |
| **2 — Adequate** | Usable; minor omissions or imprecision that don't mislead. |
| **1 — Weak** | Present but materially incomplete, imprecise, or confusing. |
| **0 — Failing** | Absent, wrong, or actively misleading. |
| **N/A** | Criterion doesn't apply to this narrative (state why). |

Every score in an evidence pack must cite (a) the RUB-ID, (b) the specific output span, and (c) the source-narrative span or ontology check that justifies it.

---

## A. Issue-spotting & claim/element correctness

### RUB-INTAKE-01 — Issue completeness (spots the unspoken issues) · weight 3 · [GATE]
Does the analysis identify **all** legal issues fairly raised by the facts — *including issues the client did not know to name*? This is the core value proposition (STATE.md core value). A landlord-tenant narrative that mentions only "I'm being evicted" but describes black mold must surface **habitability / warranty-of-habitability** as well as the eviction defense.
- **3:** All reasonably-raised issues surfaced, including non-obvious ones, with no hallucinated issues.
- **2:** All primary issues surfaced; one minor secondary issue missed.
- **1:** Primary issue surfaced but ≥1 significant issue the facts clearly raise is missed.
- **0:** Misses the primary issue, or invents an issue with no basis in the facts.
- **GATE fails** when a case-dispositive issue plainly raised by the facts is absent.

### RUB-INTAKE-02 — Claim identification accuracy · weight 3
Are the identified legal claims/causes of action correct for the jurisdiction and facts, correctly named, and not over- or under-inclusive?
- **3:** Claims correct, correctly named, jurisdiction-appropriate, none spurious.
- **2:** Claims correct; minor naming imprecision or a borderline-includable claim.
- **1:** Core claim right but mislabeled, or a clearly-inapplicable claim included.
- **0:** Wrong claims, or claims that don't match the facts/jurisdiction.

### RUB-INTAKE-03 — Element mapping & fact linkage · weight 3
For each claim, are the legal **elements** enumerated correctly, and is each element linked to the specific **fact(s)** from the narrative that support (or fail to support) it? Fact→element linkage must be **traceable to a real narrative span**, not generated.
- **3:** Elements complete and correct; every satisfied element cites a real fact span; unsatisfied elements flagged.
- **2:** Elements correct; most linked to facts; ≤1 linkage vague.
- **1:** Elements listed but linkage sparse or generic.
- **0:** Elements wrong/missing, or fact linkages fabricated (cite facts not in the narrative).

### RUB-INTAKE-04 — No fabrication / extractive fidelity · weight 3 · [GATE]
No fact, party, date, dollar amount, or quote in the analysis or memo may be invented. Everything asserted as a client fact must trace to the narrative or an uploaded document.
- **3:** Zero fabricated facts; every factual assertion traceable.
- **1:** A non-material embellishment (e.g., a rounded figure) not in the source.
- **0 / GATE fails:** Any material fabricated fact, party, date, or amount.

---

## B. FOLIO ontology mapping

### RUB-INTAKE-05 — FOLIO mapping validity (deterministic) · weight 2 · [GATE]
Every FOLIO concept the system maps to must be a **real, resolvable FOLIO IRI** on the expected branch (verified by scripted `folio-python`, not by eye). No dead IRIs, no malformed identifiers.
- **3:** 100% of mapped IRIs resolve and sit on a sensible branch.
- **2:** ≥95% resolve; the rest are clearly-labeled unmapped/low-confidence, not broken IRIs.
- **1:** 80–95% resolve, or unmapped concepts silently dropped.
- **0 / GATE fails:** Broken/hallucinated IRIs presented as valid mappings.

**Semantic-fit sub-criterion (v1.2 amendment, Damien 2026-07-07):** mechanical resolvability alone does not satisfy RUB-05. Each *surfaced* mapping must also be a **semantically plausible** concept for the claim it is attached to (assessed per RUB-06's method — FOLIO MCP + reviewer). A run whose IRIs all resolve but whose surfaced mappings are substantially semantic mismatches (e.g. habitability → Product Liability Law, or placeholder/sandbox concepts surfaced as claims) scores at most **1** on RUB-05, and GATE-fails if the mismatches are presented with false confidence as valid mappings. Re-judging of previously-scored RUB-05 findings is required under v1.2.

### RUB-INTAKE-06 — FOLIO mapping semantic fit · weight 2
Do the mapped concepts actually *fit* the facts (semantic judgment — FOLIO MCP + reviewer)? An eviction narrative should map to landlord-tenant / housing concepts, not a coincidental lexical match.
- **3:** Mappings are the right concepts a domain expert would choose.
- **2:** Mostly right; a few over-broad or over-narrow but defensible.
- **1:** Several mappings are lexically-driven mismatches.
- **0:** Mappings semantically wrong / misleading.

### RUB-INTAKE-07 — Unmappable-concept handling · weight 1
When a real legal concept in the facts has **no adequate FOLIO concept**, is it preserved and flagged (candidate for the Ecosystem Loop) rather than force-fit or dropped?
- **3:** Gaps preserved, labeled, surfaced as ontology-suggestion candidates.
- **2:** Gaps preserved but not clearly surfaced.
- **1:** Some force-fitting to a poor concept.
- **0:** Real concepts silently dropped or force-fit with false confidence.

---

## C. Deadline / statute-of-limitations surfacing

### RUB-INTAKE-08 — Deadline detection, computation & prominence · weight 3 · [GATE]
Every applicable time-sensitive event (eviction answer/hearing, response deadlines, notice-to-quit periods, SOL windows, filing deadlines) must be **detected, computed for the correct jurisdiction, and surfaced prominently** — required, not optional (v1.1). Missed deadlines end cases — the highest-stakes consumer criterion. Scope = any of the 50 U.S. states.
- **3:** All applicable deadlines detected AND computed to a specific date/window for the correct jurisdiction, surfaced up-front, each tied to its governing primary source (see RUB-INTAKE-09).
- **2:** All primary deadlines computed & surfaced; a secondary one detected but only noted, not computed.
- **1:** Dates echoed but not computed into deadlines / not prominent.
- **0 / GATE fails:** A required deadline plainly raised by the facts is not surfaced, or not computed to an actionable date.

### RUB-INTAKE-09 — Deadline correctness & primary-source grounding · weight 2 · [GATE]
Each computed deadline must be **correct for the jurisdiction** and **cite the governing primary authority** — statute, regulation, court rule (civil / criminal / local), judicial standing order, or other applicable primary source. Genuinely ambiguous *inputs* may be hedged ("confirm your exact service date"), but the *rule and computation must be right and sourced* — no confidently-stated wrong dates, no uncited "trust me" deadlines.
- **3:** Deadline correct, computed from a **cited** primary source for the right jurisdiction; input-level ambiguity (if any) clearly flagged.
- **2:** Correct deadline, but the primary-source citation is generic/imprecise.
- **1:** Deadline stated without a source, or computed from a secondary/uncited basis.
- **0 / GATE fails:** States a specific deadline that is wrong, or cites the wrong jurisdiction/authority.

---

## D. Plain-language / accessibility

### RUB-INTAKE-10 — Reading level · weight 2
Consumer-facing output (memo, next-steps, gap questions) must target **~6th grade** reading level (persona: stressed, mobile-first, mixed literacy). Measured with a readability score (Flesch-Kincaid/SMOG) + reviewer judgment.
- **3:** ~6th grade throughout; legal terms defined in plain words on first use.
- **2:** ~7th–8th grade; a few unavoidable terms undefined.
- **1:** Frequent unexplained legalese / above 9th grade.
- **0:** Reads like a brief to another lawyer.

### RUB-INTAKE-11 — Tone & non-alarming clarity · weight 1
Is the output honest about seriousness without inducing panic, and free of jargon that would confuse or shame a self-represented person? Safety/urgency framed as actionable next steps.
- **3:** Calm, direct, actionable; urgency conveyed as "do X by Y."
- **2:** Clear; tone slightly clinical or slightly alarming.
- **1:** Confusing, condescending, or needlessly alarming.
- **0:** Actively distressing or shaming.

### RUB-INTAKE-12 — Translation fidelity (i18n) · weight 1
For the 7 supported languages, is translated output faithful, complete (no English fallback leaking into a non-English memo), and still plain-language? Inner-loop spot-check languages: **English, Spanish, Chinese**; all 7 on the final 8–10 pass.
- **3:** Faithful, complete, plain-language in the checked languages.
- **2:** Faithful; minor untranslated UI string.
- **1:** Partial English fallback in consumer content.
- **0:** Mistranslation that changes legal meaning, or wholesale fallback.

---

## E. Gap analysis & next steps

### RUB-INTAKE-13 — Gap analysis usefulness · weight 2
Does the system identify what facts are **missing** to complete each claim, and ask targeted follow-up questions a non-lawyer can answer?
- **3:** Gaps precisely tied to unsatisfied elements; questions concrete and answerable.
- **2:** Useful gaps; some questions generic.
- **1:** Vague "provide more info" prompts.
- **0:** No gap analysis, or gaps unrelated to the actual missing elements.

### RUB-INTAKE-14 — Referral / escalation appropriateness · weight 1
When the matter is out of scope, urgent, or below a completeness threshold, does the system route to referral/escalation appropriately (not over-referring trivial matters, not under-referring emergencies)?
- **3:** Referral/escalation triggers match real urgency & scope.
- **2:** Reasonable; one over/under-referral.
- **1:** Referral logic misfires on this matter.
- **0:** Emergency not escalated, or everything dumped to referral.

---

## F. Export & mechanical integrity

### RUB-INTAKE-15 — Export integrity · weight 2 · [GATE]
The exported artifact (PDF/JSON/DOCX) must **open in a standard reader without corruption**, contain the full memo + analysis, preserve FOLIO citations, and match the on-screen content (round-trip fidelity).
- **3:** Export opens clean, complete, faithful to on-screen content, citations intact.
- **2:** Opens; minor formatting drift.
- **1:** Opens but content missing or badly formatted.
- **0 / GATE fails:** Corrupt/won't open, or materially incomplete vs on-screen.

### RUB-INTAKE-16 — End-to-end run integrity · weight 1
The full journey (register → consent → intake → narrative → analysis → memo → export) completes without server error, data loss, or silent stage failure; analysis reflects **all** submitted input including uploaded documents.
- **3:** Clean end-to-end; uploaded docs demonstrably incorporated.
- **2:** Completes; a non-fatal warning or a doc weakly incorporated.
- **1:** Completes only with a manual workaround.
- **0:** Pipeline errors, drops data, or ignores uploaded documents.

---

## Weighting summary

| Group | Criteria | Σ weight |
|---|---|---|
| A. Issue/claim/element correctness | 01–04 | 12 |
| B. FOLIO mapping | 05–07 | 5 |
| C. Deadlines | 08–09 | 5 |
| D. Plain language | 10–12 | 4 |
| E. Gaps/referral | 13–14 | 3 |
| F. Export/integrity | 15–16 | 3 |
| **Total** | **16 criteria** | **32** |

**GATE criteria (any failure caps run at "borderline"):** 01, 04, 05, 08, 09, 15.

---

## Resolved questions (Damien, 2026-07-05 → v1.1)

1. **Reading level** → **~6th grade** (RUB-INTAKE-10 updated).
2. **Deadline scope** → **required + correct + primary-source-cited, all 50 states** (RUB-INTAKE-08/09 now hard-gate; supersedes detect+hedge).
3. **Inner-loop languages** → **English, Spanish, Chinese**; all 7 on the final pass (RUB-INTAKE-12).
4. **Practice-area rubrics** → **YES** — maintain per-practice-area addenda in `docs/rubrics/practice-areas/` (landlord-tenant, family, immigration, + final-pass areas). Personas still run unbound; addenda are judging oracles.
5. **Weighting** → accepted as drafted.

---

*Lane 3 alea-intake persona UAT campaign. Every evidence-pack finding cites `intake-quality-v1.1`. The v1.0→v1.1 deadline change (detect+hedge → required) triggers re-judging of RUB-INTAKE-08/09 once the deadline engine covers computed, cited, 50-state deadlines.*
