# Intake Quality Rubric — v1.0 (LOCKED 2026-07-05)

**Rubric ID prefix:** `RUB-INTAKE-`
**Applies to:** the alea-intake analysis pipeline output for a single client intake — the FOLIO mappings, claim/element analysis, gap analysis, deadline surfacing, plain-language memo, and export artifacts.
**Judged against:** the client's messy first-person narrative + any uploaded documents (the *source of truth*), the FOLIO ontology (via deterministic `folio-python` checks first, FOLIO MCP for semantic-fit calls), and this rubric.
**Status:** **LOCKED v1.0** (Damien, 2026-07-05). Shared via Proof for review; the one substantive lock decision — deadline gating — is recorded below. Campaign findings cite `intake-quality-v1.0`. Amendments bump the version and trigger re-judging of affected findings.

**Lock decisions (Damien, 2026-07-05):**
- **Deadlines = "detect + hedge" for v1.** RUB-INTAKE-08/09 require the system to surface time-sensitive events prominently and flag "verify the exact date"; a run is **not** GATE-failed merely for lacking exact jurisdiction computation. Full computed deadlines are the II.3.1 feature (a separate build). A *confidently-stated wrong* date still fails RUB-INTAKE-09.
- Reading-level target (RUB-10): **6th–8th grade** (default; can tighten to 6th later).
- i18n spot-check (RUB-12): **Spanish, Vietnamese, Chinese** each inner loop; all 7 on the final 8–10 pass (default).
- Practice-area binding (Q4): personas run **generic/unbound** — the analysis pipeline is practice-area-agnostic (confirmed in code), so full FOLIO/claim analysis is expected without a registered practice area.
- Group weights accepted as drafted.

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

### RUB-INTAKE-08 — Deadline detection & prominence · weight 3 · [GATE]
Time-sensitive events in the narrative (eviction notice date, "answer due in 5 days," notice-to-quit period, SOL windows, filing deadlines) must be **detected and surfaced prominently**. Missed deadlines end cases — this is the highest-stakes consumer criterion.
- **3:** All date-bearing/deadline-bearing events detected and surfaced up-front with the computed deadline where a rule exists.
- **2:** Key deadline surfaced; a secondary date not computed but noted.
- **1:** Dates echoed but not framed as deadlines / not prominent.
- **0 / GATE fails:** A hard deadline plainly present in the facts is not surfaced at all.
> **Accuracy caveat:** a computed deadline must be **correct or explicitly hedged**. An LLM-guessed specific deadline presented as authoritative, if wrong, is a GATE failure under RUB-INTAKE-09 — better to flag "a deadline likely applies; verify the exact date" than to state a wrong date confidently.

### RUB-INTAKE-09 — Deadline accuracy & honesty · weight 2 · [GATE]
Any *specific* computed deadline must be correct for the jurisdiction, or clearly hedged as an estimate to verify. No confidently-stated wrong dates.
- **3:** Deadlines computed correctly with jurisdiction basis, or honestly hedged.
- **1:** Deadline hedged but vague enough to be unhelpful.
- **0 / GATE fails:** Confidently states a specific deadline that is wrong.

---

## D. Plain-language / accessibility

### RUB-INTAKE-10 — Reading level · weight 2
Consumer-facing output (memo, next-steps, gap questions) should target roughly a **6th–8th grade** reading level (persona: stressed, mobile-first, mixed literacy). Measured with a readability score (Flesch-Kincaid/SMOG) + reviewer judgment.
- **3:** ~≤8th grade throughout; legal terms defined in plain words on first use.
- **2:** Mostly plain; a few unavoidable terms undefined.
- **1:** Frequent unexplained legalese.
- **0:** Reads like a brief to another lawyer.

### RUB-INTAKE-11 — Tone & non-alarming clarity · weight 1
Is the output honest about seriousness without inducing panic, and free of jargon that would confuse or shame a self-represented person? Safety/urgency framed as actionable next steps.
- **3:** Calm, direct, actionable; urgency conveyed as "do X by Y."
- **2:** Clear; tone slightly clinical or slightly alarming.
- **1:** Confusing, condescending, or needlessly alarming.
- **0:** Actively distressing or shaming.

### RUB-INTAKE-12 — Translation fidelity (i18n) · weight 1
For the 7 supported languages, is translated output faithful, complete (no English fallback leaking into a non-English memo), and still plain-language? Spot-checked per language.
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

## Open questions for Damien (resolve during Proof review)

1. **Reading-level target** — is 6th–8th grade right, or stricter (~6th, per II.3.4)? RUB-INTAKE-10.
2. **Deadline scope** — for v1, should we *require* correct computed deadlines for any jurisdiction, or is "detect + hedge + flag to verify" acceptable until the MN + 1–2 state rule tables exist (II.3.1)? This governs how hard RUB-INTAKE-08/09 gate.
3. **Which 3 of the 7 languages** to spot-check each inner loop (RUB-INTAKE-12), and which for the final 8–10 persona pass.
4. **Practice-area binding** — the live server registers only `personal_injury`. Should landlord-tenant/immigration/family personas run as *generic* intakes (still expecting full FOLIO/claim analysis), and is "generic intake produces full analysis" itself a rubric expectation or a known v1 limitation?
5. **Weighting** — are the group weights (issue-spotting heaviest, then deadlines/FOLIO) aligned with your sense of what matters most for A2J?

---

*Draft prepared for the Lane 3 alea-intake persona UAT campaign. On lock, rename to `intake-quality-v1.0.md` (or bump), and every evidence-pack finding cites this version.*
