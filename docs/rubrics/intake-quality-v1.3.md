# Intake Quality Rubric — v1.3 (LOCKED; Damien rulings 2026-07-10)

> **STATUS: LOCKED.** This rubric codifies Damien's four validation rulings of
> 2026-07-10 (canonical record: `briefs/qa/2026-07-10-imm-rulings-answers.json`) on top
> of the LOCKED v1.2 text. Damien chose the **strictest** option on all four questions.
> Where the earlier v1.3-DRAFT (which predated the rulings) differed, **Damien's answers
> win** — this LOCKED text supersedes the draft. Findings now cite
> `intake-quality-v1.3`. The four rulings amended two gates beyond the draft: RUB-01
> broadens from "case-dispositive only" to **every doctrine-level sub-issue fairly
> raised**, and RUB-09 hardens from a provisional tiered standard to a **strict
> primary-source gate on every computed deadline**.

**Rubric ID prefix:** `RUB-INTAKE-`
**Applies to:** the alea-intake analysis pipeline output for a single client intake — the FOLIO mappings, claim/element analysis, gap analysis, deadline surfacing, plain-language memo, and export artifacts.
**Judged against:** the client's messy first-person narrative + any uploaded documents (the *source of truth*), the FOLIO ontology (via deterministic `folio-python` checks first, FOLIO MCP for semantic-fit calls), and this rubric.
**Derives from:** `intake-quality-v1.md` (LOCKED v1.2, Damien 2026-07-07). Everything in v1.2 carries forward unchanged except where a **v1.3 ruling** block appears below.

---

## What v1.3 changes vs v1.2 (at a glance)

| Ruling | Criterion | Effect | Source | Status |
|---|---|---|---|---|
| **RUB-01 depth** | RUB-INTAKE-01 | **Every doctrine-level sub-issue fairly raised by the facts** must be surfaced (as a claim, a flagged issue, **or** a question). Practice-area addenda are **non-exhaustive oracles** and do NOT bound the gate — an unlisted doctrine sub-issue fairly raised gates too. Full element analysis is NOT required; surfacing-as-question suffices as the *form*. | Damien r1 (strictest) | **LOCKED** |
| **RUB-08 lapsed** | RUB-INTAKE-08 | **Lapsed** (expired) deadlines MUST be computed, explicitly flagged as lapsed, **and routed to the exception pathway** (e.g. INA § 208(a)(2)(D) extraordinary/changed circumstances). | Damien r2 (strictest) | **LOCKED** |
| **RUB-09 sourcing** | RUB-INTAKE-09 | **STRICT: every computed deadline must carry its governing primary source, or the gate fails — even when the date is correct.** An uncited computed deadline GATE-fails; a wrong/fabricated cite GATE-fails. | Damien r3 (strictest) | **LOCKED** |
| **RUB-15 exec-summary** | RUB-INTAKE-15 | An export shipping an **empty `executive_summary`** (or any empty declared field) is materially incomplete — **GATE fail, full stop**. | Damien r4 (strictest) | **LOCKED** |

Everything else (RUB-02/03/04/05/06/07/10/11/12/13/14/16, weights, GATE set, scoring scale) is **unchanged from v1.2**.

---

## How scoring works (unchanged from v1.2)

Each criterion is scored on a **0–3 scale** with concrete anchors, plus a **weight**. A run's rubric score is the weighted mean. Criteria marked **[GATE]** are pass/fail blockers: any GATE failure caps the whole run at "borderline" regardless of the weighted mean, because it represents a way the product actively misleads or harms a vulnerable self-represented person.

| Score | Meaning |
|---|---|
| **3 — Excellent** | Meets the bar a legal-aid attorney would sign off on. |
| **2 — Adequate** | Usable; minor omissions or imprecision that don't mislead. |
| **1 — Weak** | Present but materially incomplete, imprecise, or confusing. |
| **0 — Failing** | Absent, wrong, or actively misleading. |
| **N/A** | Criterion doesn't apply to this narrative (state why). |

**GATE criteria (any failure caps run at "borderline"):** 01, 04, 05, 08, 09, 15. *(Unchanged from v1.2.)*

---

## A. Issue-spotting & claim/element correctness

### RUB-INTAKE-01 — Issue completeness (spots the unspoken issues) · weight 3 · [GATE]
Does the analysis identify **all** legal issues fairly raised by the facts — *including issues the client did not know to name*? This is the core value proposition. A landlord-tenant narrative that mentions only "I'm being evicted" but describes black mold must surface **habitability / warranty-of-habitability** as well as the eviction defense.

- **3:** All reasonably-raised issues surfaced, including non-obvious ones, with no hallucinated issues.
- **2:** All primary issues surfaced; one minor secondary issue missed.
- **1:** Primary issue surfaced but ≥1 significant issue the facts clearly raise is missed.
- **0:** Misses the primary issue, or invents an issue with no basis in the facts.
- **GATE fails** when *any* doctrine-level sub-issue fairly raised by the facts is entirely absent (see ruling).

> **v1.3 ruling — FULL DOCTRINE DEPTH (Damien r1, strictest).** **Every doctrine-level
> sub-issue fairly raised by the facts must be surfaced.** Surfacing may take any form —
> a claim, a flagged issue, **or** a concrete follow-up question; the system does **not**
> have to perform the full element analysis at intake. Surface-as-question is an
> acceptable *form* (e.g. *"You mentioned your husband is a green-card holder and hurt you
> — a VAWA self-petition may apply; a lawyer should confirm,"* or *"Your asylum window may
> have closed years ago — ask a lawyer about the one-year-bar exceptions under INA
> § 208(a)(2)(D)"*). What Damien tightened vs the draft is the **scope of the gate**:
>
> **What GATE-fails under this ruling:** *any* doctrine-level sub-issue **fairly raised by
> the facts** that is **entirely absent** — not surfaced as a claim, an issue, *or* a
> question. The gate is **no longer limited to "case-dispositive" issues**. Non-obvious
> linkages count: e.g. the immigration matter's **lapsed asylum-bar exception routing
> (§ 208(a)(2)(D))**, **VAWA self-petition**, **U-nonimmigrant status**, the **§ 245(c)(2)
> unauthorized-employment adjustment bar and its VAWA-self-petitioner exemption linkage**,
> the **Pereira/Niz-Chavez NTA time-date-place defect probe**; the family matter's
> **§ 518B.01 Order-for-Protection grounds**, the **§ 518.17 subd. 1(a)(4) domestic-abuse
> best-interest custody factor**, and **parental-abduction / flight-risk** interim terms.
>
> **Practice-area addenda are non-exhaustive ORACLES, not bounds.** The addenda list
> known sub-issues to help judges, but a doctrine sub-issue fairly raised by the facts and
> *not* on the addenda list **still gates**. Surfacing the *wrong* concept, or burying the
> issue so the client could not act on it, does not count as surfacing.

### RUB-INTAKE-02 — Claim identification accuracy · weight 3
*(Unchanged from v1.2.)* Are the identified legal claims/causes of action correct for the jurisdiction and facts, correctly named, and not over- or under-inclusive?
- **3:** Claims correct, correctly named, jurisdiction-appropriate, none spurious.
- **2:** Claims correct; minor naming imprecision or a borderline-includable claim.
- **1:** Core claim right but mislabeled, or a clearly-inapplicable claim included.
- **0:** Wrong claims, or claims that don't match the facts/jurisdiction.

### RUB-INTAKE-03 — Element mapping & fact linkage · weight 3
*(Unchanged from v1.2.)* For each claim, are the legal **elements** enumerated correctly, and is each element linked to the specific **fact(s)** from the narrative? Fact→element linkage must be **traceable to a real narrative span**, not generated.
- **3:** Elements complete and correct; every satisfied element cites a real fact span; unsatisfied elements flagged.
- **2:** Elements correct; most linked to facts; ≤1 linkage vague.
- **1:** Elements listed but linkage sparse or generic.
- **0:** Elements wrong/missing, or fact linkages fabricated.

### RUB-INTAKE-04 — No fabrication / extractive fidelity · weight 3 · [GATE]
*(Unchanged from v1.2.)* No fact, party, date, dollar amount, or quote in the analysis or memo may be invented. Everything asserted as a client fact must trace to the narrative or an uploaded document.
- **3:** Zero fabricated facts; every factual assertion traceable.
- **1:** A non-material embellishment (e.g., a rounded figure) not in the source.
- **0 / GATE fails:** Any material fabricated fact, party, date, or amount.

---

## B. FOLIO ontology mapping *(unchanged from v1.2)*

### RUB-INTAKE-05 — FOLIO mapping validity (deterministic) · weight 2 · [GATE]
Every FOLIO concept the system maps to must be a **real, resolvable FOLIO IRI** on the expected branch (verified by scripted `folio-python`, not by eye). No dead IRIs, no malformed identifiers.
- **3:** 100% of mapped IRIs resolve and sit on a sensible branch.
- **2:** ≥95% resolve; the rest are clearly-labeled unmapped/low-confidence, not broken IRIs.
- **1:** 80–95% resolve, or unmapped concepts silently dropped.
- **0 / GATE fails:** Broken/hallucinated IRIs presented as valid mappings.

**Semantic-fit sub-criterion (v1.2 amendment, Damien 2026-07-07 — carried forward unchanged):** mechanical resolvability alone does not satisfy RUB-05. Each *surfaced* mapping must also be a **semantically plausible** concept for the claim it is attached to (assessed per RUB-06's method). A run whose IRIs all resolve but whose surfaced mappings are substantially semantic mismatches (e.g. habitability → Product Liability Law, or a geographic/utility placeholder concept surfaced as a claim) scores at most **1** on RUB-05, and GATE-fails if the mismatches are presented with false confidence as valid mappings.

### RUB-INTAKE-06 — FOLIO mapping semantic fit · weight 2 *(unchanged)*
Do the mapped concepts actually *fit* the facts (semantic judgment)? An eviction narrative should map to landlord-tenant / housing concepts, not a coincidental lexical match.
- **3:** Mappings are the right concepts a domain expert would choose.
- **2:** Mostly right; a few over-broad or over-narrow but defensible.
- **1:** Several mappings are lexically-driven mismatches.
- **0:** Mappings semantically wrong / misleading.

### RUB-INTAKE-07 — Unmappable-concept handling · weight 1 *(unchanged)*
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

> **v1.3 ruling — LAPSED DEADLINES COMPUTED + ROUTED (Damien r2, strictest).** **A LAPSED
> (already-expired) deadline MUST be (1) computed to its date, (2) explicitly flagged as
> lapsed, AND (3) routed to the exception pathway** — not silently dropped because it is
> in the past. A missed-and-expired deadline is malpractice-relevant: it tells the client
> (and any reviewing attorney) that a right was likely lost and routes to the
> fallback/exception analysis. The required behavior: compute the date, label it clearly
> (*"this deadline has already passed — [date]"*), **and surface the exception pathway with
> its governing authority** (e.g. the asylum one-year bar's *changed- or
> extraordinary-circumstances* exception under **INA § 208(a)(2)(D)**). **GATE fails** when
> a lapsed deadline plainly raised by the facts (e.g. the asylum one-year bar that expired
> Aug 14, 2020) is never computed or surfaced, **or** is computed/flagged but not routed to
> its exception pathway. A lapsed deadline that is computed, flagged-as-lapsed, and
> exception-routed **passes** (it need not be presented as "urgent/live").

### RUB-INTAKE-09 — Deadline correctness & primary-source grounding · weight 2 · [GATE]
Each computed deadline must be **correct for the jurisdiction** and grounded in the governing authority. Genuinely ambiguous *inputs* may be hedged ("confirm your exact service date"), but the *rule and computation must be right* — no confidently-stated wrong dates.
- **3:** Deadline correct, computed from a **cited** primary source for the right jurisdiction; input-level ambiguity (if any) clearly flagged.
- **2:** Correct deadline from the right authority, but the primary-source citation is slightly generic/imprecise (right statute, imprecise subsection).
- **1:** *(does not pass the gate)* Deadline stated without a governing source, or from a secondary/uncited basis.
- **0 / GATE fails:** States a specific deadline that is wrong, cites the wrong jurisdiction/authority, or fabricates a citation.

> **v1.3 ruling — STRICT PRIMARY-SOURCE GATE (Damien r3, strictest).** The strict
> RUB-LT-16-style reading governs RUB-09 **everywhere**: **every computed deadline must
> carry its governing primary source, or the gate fails — even when the computed date is
> correct.** This supersedes the v1.3-DRAFT's provisional tiered standard (which would have
> let a hedged, uncited computed deadline pass): under the LOCKED reading it does **not**
> pass.
>
> - **(a) Codified law (statute / regulation / court rule):** a computed deadline
>   **REQUIRES a correct pin-cite** to the governing authority (e.g. `Minn. Stat.
>   § 504B.321`, `Minn. Stat. § 518.12`, `INA § 208(a)(2)(B)`, `8 C.F.R. § 1003.18` /
>   `INA § 239`). These sources are public and free — there is no excuse for omitting the
>   cite. A **missing** cite on a computed codified-law deadline is a **GATE failure**, even
>   if the date is right.
> - **(b) Case law / foreign / genuinely inaccessible jurisdictions:** cite the governing
>   authority to the best available precision, mark **provenance + reduced confidence**, and
>   include **"verify with counsel"** guidance. Honest inability to reach an authoritative
>   *reporter text* is tolerated **only if the governing authority is still named**; a
>   computed deadline with **no** governing source named GATE-fails.
> - **(c) An UNCITED computed deadline GATE-fails.** Hedging does not cure a missing
>   governing source under the LOCKED reading. (A *detected-but-not-computed* event that is
>   honestly surfaced as "not computed — verify" is not a computed deadline and does not
>   trigger this gate; it simply is not a RUB-08 "computed" credit either.)
> - **(d) A WRONG or fabricated citation is an AUTOMATIC FAIL** (0 / GATE) — ties into
>   RUB-04's no-fabrication gate. A confidently-cited authority that does not say what the
>   system claims, or does not exist, is worse than no cite.
>
> **Rationale:** deadlines are the highest-stakes output; a date a self-represented person
> would act on must be traceable to the law that produces it. Quoting/linking full source
> text remains a v2 depth goal, but **naming the correct governing primary source is now a
> v1 gate** on every computed deadline.

---

## D. Plain-language / accessibility *(unchanged from v1.2)*

### RUB-INTAKE-10 — Reading level · weight 2
Consumer-facing output must target **~6th grade** reading level. Measured with a readability score (Flesch-Kincaid/SMOG) + reviewer judgment.
- **3:** ~6th grade throughout; legal terms defined in plain words on first use.
- **2:** ~7th–8th grade; a few unavoidable terms undefined.
- **1:** Frequent unexplained legalese / above 9th grade.
- **0:** Reads like a brief to another lawyer.

### RUB-INTAKE-11 — Tone & non-alarming clarity · weight 1
- **3:** Calm, direct, actionable; urgency conveyed as "do X by Y."
- **2:** Clear; tone slightly clinical or slightly alarming.
- **1:** Confusing, condescending, or needlessly alarming.
- **0:** Actively distressing or shaming.

### RUB-INTAKE-12 — Translation fidelity (i18n) · weight 1
Inner-loop spot-check languages: **English, Spanish, Chinese**; all 7 on the final 8–10 pass.
- **3:** Faithful, complete, plain-language in the checked languages.
- **2:** Faithful; minor untranslated UI string.
- **1:** Partial English fallback in consumer content.
- **0:** Mistranslation that changes legal meaning, or wholesale fallback.

---

## E. Gap analysis & next steps *(unchanged from v1.2)*

### RUB-INTAKE-13 — Gap analysis usefulness · weight 2
- **3:** Gaps precisely tied to unsatisfied elements; questions concrete and answerable.
- **2:** Useful gaps; some questions generic.
- **1:** Vague "provide more info" prompts.
- **0:** No gap analysis, or gaps unrelated to the actual missing elements.

> **Cross-reference to RUB-01 (v1.3 ruling):** because surfacing unstated doctrine **as a
> question** is an acceptable *form* of surfacing under RUB-01, the gap-question generator
> is the primary vehicle for the "spot the unspoken issue" value proposition. A doctrine
> sub-issue surfaced only here (e.g. a VAWA, § 245(c)(2)-exemption, Pereira, or
> one-year-bar follow-up question) counts for RUB-01 as well as RUB-13. But note the RUB-01
> gate is scoped to **every doctrine-level sub-issue fairly raised** — the question channel
> must actually *cover* them, not merely exist.

### RUB-INTAKE-14 — Referral / escalation appropriateness · weight 1
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

> **v1.3 ruling — EMPTY DECLARED FIELD = GATE FAIL (Damien r4, strictest).** **An export
> shipping an EMPTY `executive_summary` — or any empty declared field — is materially
> incomplete: GATE fail, full stop.** The executive summary is **gate-required content**,
> not an optional block: it is the single field a hurried client or reviewing attorney
> reads first. Shipping an export that claims completeness (`completeness = 1.0`, summary
> profile-flag on) while the summary string is empty is a round-trip / integrity failure,
> regardless of whether the feature renders on-screen. Consequence: **BUG-23 (empty
> `executive_summary`) is GATE-BLOCKING** under v1.3 and must be fixed before RUB-15 can
> pass on any persona whose export exhibits it.

### RUB-INTAKE-16 — End-to-end run integrity · weight 1 *(unchanged)*
- **3:** Clean end-to-end; uploaded docs demonstrably incorporated.
- **2:** Completes; a non-fatal warning or a doc weakly incorporated.
- **1:** Completes only with a manual workaround.
- **0:** Pipeline errors, drops data, or ignores uploaded documents.

---

## Weighting summary *(unchanged from v1.2)*

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

## Changelog

### v1.3 (LOCKED, Damien 2026-07-10) — four validation rulings, strictest option on all four
Canonical record: `briefs/qa/2026-07-10-imm-rulings-answers.json`. Supersedes the
v1.3-DRAFT (which predated the rulings); where they differ, these rulings win.
- **RUB-INTAKE-01 (r1 → FULL doctrine depth):** **every** doctrine-level sub-issue fairly
  raised by the facts must be surfaced (as claim, issue, or question); full element
  analysis not required (surface-as-question is an acceptable form). The gate is **no
  longer limited to case-dispositive issues**. Practice-area addenda are **non-exhaustive
  oracles that do NOT bound the gate**. *(Stricter than the draft, which gated only
  case-dispositive issues.)*
- **RUB-INTAKE-08 (r2 → lapsed computed + routed):** lapsed/expired deadlines must be
  computed, flagged lapsed, **and routed to the exception pathway** (e.g. INA
  § 208(a)(2)(D)). GATE fails if a lapsed deadline fairly raised is never computed/surfaced
  **or** not exception-routed.
- **RUB-INTAKE-09 (r3 → STRICT primary-source gate):** **every** computed deadline must
  carry its governing primary source or the gate fails, even when the date is correct. An
  uncited computed deadline GATE-fails; a wrong/fabricated cite GATE-fails. *(Stricter than
  the draft's provisional standard, which let a hedged uncited computed deadline pass.)*
- **RUB-INTAKE-15 (r4 → empty field = gate fail):** an export with an empty
  `executive_summary` (or any empty declared field) is materially incomplete — GATE fail,
  full stop. BUG-23 is gate-blocking.
- No changes to weights, the GATE set, the 0–3 scale, or criteria
  02/03/04/05/06/07/10/11/12/13/14/16.

### v1.2 (LOCKED, Damien 2026-07-07)
- Added the semantic-fit sub-criterion to RUB-INTAKE-05 (mechanical resolvability no longer
  sufficient; substantial semantic mismatches cap RUB-05 at 1 and GATE-fail if presented with
  false confidence). Triggered re-judging of RUB-05 findings.

### v1.1 (LOCKED, Damien 2026-07-05)
- Deadlines REQUIRED, computed, primary-source-cited, all 50 states (RUB-08/09 hard-gate;
  supersedes v1.0 detect+hedge). Reading level tightened to ~6th grade. Inner-loop i18n =
  English/Spanish/Chinese. Practice-area rubric addenda = yes. Weights accepted as drafted.

---

*Lane 3 alea-intake persona UAT campaign. Findings cite `intake-quality-v1.3` as of the
2026-07-10 lock. Practice-area addenda under `docs/rubrics/practice-areas/` remain
non-exhaustive judging oracles; they inform but do not bound the RUB-01 gate.*
