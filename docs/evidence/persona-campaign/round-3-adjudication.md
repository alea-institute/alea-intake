# Round-3 Judge Verdict Adjudication — appellate review

**Adjudicator:** Fable (Lane 3), 2026-07-10 · skeptical-appellate mode
**Scope:** the 6 open (non-muted) round-3 judge verdicts surfaced for Damien's agree/disagree in
`docs/evidence/persona-campaign/validation-review.html`, re-examined against the underlying run
artifacts (runs 30/31/34, exports 63-68 / 75-77, memos), `personas/ANSWER-KEYS.md`, and the
**LOCKED rubric v1.3** (`docs/rubrics/intake-quality-v1.3.md`, commit a31010b).
**Mandate:** Damien — *"I don't have time to do detailed analyses of the Judge's rulings — use your best judgment."*

---

## 0. Governing-rubric reconciliation (read first)

This adjudication applies **LOCKED v1.3**, not the softer "v1.3-draft" interpretations that this
task was originally briefed against. That brief predated Damien's actual answers. His authenticated
rulings — `briefs/qa/2026-07-10-imm-rulings-answers.json`, paste-back from artifact c20a57e0,
submitted 2026-07-10 17:30 — chose the **STRICTEST option on all four questions**, and a concurrent
authorized process already **locked v1.3** (a31010b) and began engineering to it (93112e7, e6bbf74).
Two rulings are stricter than the briefed draft and change gate outcomes here:

| Q | Briefed draft (this task's original framing) | Damien's LOCKED ruling (governs) |
|---|---|---|
| Q1 / r1 (RUB-01) | (b) surface-as-question suffices; gate only **case-dispositive** issues | **Full doctrine depth** — *every* doctrine-level sub-issue fairly raised must be surfaced; gate not limited to case-dispositive |
| Q2 / r2 (RUB-08) | lapsed computed + flagged | lapsed computed + flagged **+ routed to exception** (same direction) |
| Q5 / r3 (RUB-09) | UNSURE → provisional tiered standard; hedged-uncited may pass | **Strict** — every computed deadline must carry its governing primary source **or the gate fails**, even if the date is right |
| Q6 / r4 (RUB-15) | (b) empty exec-summary fails (same direction) | empty declared field = gate fail, full stop (same direction) |

Adjudicating under the softer draft would produce a scorecard inconsistent with the locked rubric.
Where this matters it is called out inline. Note also (r1 detail): *surface-as-question remains an
acceptable **form** of surfacing* — Damien tightened the **scope** of what must be surfaced, not the
required depth of each item.

---

## 1. Verdict table

The 6 open verdicts are all judge **FAIL (gate)** rulings. "AGREE" = the fail is correct;
"AGREE-WITH-NOTE" = fail correct but the judge's **cited evidence is stale or inaccurate** for
round 3 (the conclusion survives on different, verified round-3 evidence); "OVERTURN" = fail
incorrect. A skeptical check confirmed **every** cited evidence string against the round-3 artifacts.

| # | Persona · verdict | Judge ruling | **Adjudication** | One-line reason |
|---|---|---|---|---|
| 1 | LT · RUB-05 | Fail (gate) | **AGREE-WITH-NOTE** | Fails in R3, but on R3 evidence (habitability→**Product Liability Law** @0.85; Tenant's-Rights→**"Tenant"** entity; Retaliatory-Eviction→**"Unlawful Detainer"**), not the page's "Habitable→Living / Rent-Withholding→Insurance" strings — those are round-2 and are **absent** from R3 artifacts. |
| 2 | IMM · RUB-01 | Fail (gate) | **AGREE** | Under strict v1.3 r1 the fail is if anything strengthened: asylum one-year-bar routing, VAWA self-petition (surfaces only as one buried rationale sentence — not an actionable issue/question), §245(c)(2)/VAWA-exemption, and Pereira defect are all fairly raised yet entirely absent. |
| 3 | IMM · RUB-08 | Fail (gate) | **AGREE** | Lapsed asylum one-year bar (Aug 14 2020) is entirely absent from the deadline array (no "one-year"/§208 text); only the Aug 20 2026 hearing + 2 narrative-event non-deadlines exist. Clear v1.3 r2 gate fail. |
| 4 | IMM · RUB-05 | Fail (gate) | **AGREE-WITH-NOTE** | Fails in R3, but the page's cited "Rize (Turkish city)" and "Markman Hearing URGENT" were **removed** in R3; the real R3 basis is Fake-SSN→**"sequence"** @0.80, Asylum-Deadline→**"Status"** @0.85, Fraudulent-SSN→**"Social Security Number"** entity, Asylum-Follow-up→generic **"Application"**, plus ~5 family-law concepts on an immigration matter. |
| 5 | FC · RUB-01 | Fail (gate) | **AGREE-WITH-NOTE** | Correct **under LOCKED v1.3** (reverses the R3 manifest's interim PASS-weak): parental-abduction/flight-risk and the §518.17(1)(a)(4) DV-custody-factor linkage are fairly raised yet not surfaced as actionable issues. But two cited-evidence points are inaccurate for R3 — custody is framed as **"Child Custody Response"/establishment**, not "Modification"; and the abduction threat sits under **"Threatening Behavior,"** while "Parental Alienation" is a *separate unmapped* claim. |
| 6 | FC · RUB-05 | Fail (gate) | **AGREE-WITH-NOTE** | Fails in R3, but the mechanism is **IRI-level** geographic mis-resolution — "Legal Representation" @0.90 → **"Resen"** (North Macedonia municipality), flagged URGENT; "Child Endangerment" @0.75 → **"Child"** entity, URGENT; bare **"Order"** — not "Macedonia/Europe surfaced as 0.70 claim labels" as the page states (those visible labels were relabeled in R3; the geographic bug survives only at the IRI level, BUG-22). |

**Tally:** AGREE 2 · AGREE-WITH-NOTE 4 · OVERTURN 0. **All six FAIL conclusions stand.** No verdict
is a false positive; the recurring defect is that the validation page reused **round-2 cited
evidence** on several cards, so 4 of 6 rest on stale/imprecise quotes even though the round-3 gate
failures are real on fresh evidence.

---

## 2. Per-verdict justifications

### Verdict 1 — Landlord-tenant · RUB-05 (FOLIO validity + semantic fit) → AGREE-WITH-NOTE
The judge's page card quotes "Habitable Living Conditions → Living (vital status, 90%)", "Rent
Withholding → Insurance Claims", "Retaliatory Behavior → Lease (85%)", "Utility Disruption →
Service." **None of those four strings exist in the round-3 artifacts** (run 31 / exports 66-68 /
memos 66-68) — they are round-2 quotes carried over on the walkthrough card. The skeptical check,
however, confirms RUB-05 **still gate-fails in round 3 on genuine mismatches**: the winning
habitability GATE claim "Breach of Warranty of Habitability Due to Mold" (0.85) resolves to
**Product Liability Law** (TORT-PRDL) — the *verbatim* example in the v1.2 amendment; "Violation of
Tenant's Rights to Repairs" (0.90) → the entity **"Tenant"**; "Retaliatory Eviction" (0.85) →
**"Unlawful Detainer"**; and "Product Liability Claims" surfaced as topical noise. 14/17 claims
carry an IRI, all 14 resolve, 3 carry none. Substantial semantic mismatches presented at
0.85-0.90 confidence → RUB-05 caps at 1 and gate-fails. **Conclusion correct; cite the round-3
evidence, retire the round-2 quotes.**

### Verdict 2 — Immigration · RUB-01 (issue completeness) → AGREE
Under LOCKED v1.3 r1 the bar is *every doctrine-level sub-issue fairly raised*, surfaced as claim,
issue, **or** question. Verified against run 34: **VAWA** appears only as a single sentence inside
the rationale of the "Domestic Violence and Impact on Immigration Status" claim ("might qualify for
protections under VAWA…") — no "self-petition"/"I-360", not a distinct claim, not a question, not a
deadline. The rubric is explicit that *burying an issue so the client could not act on it does not
count as surfacing*. The **asylum one-year bar / §208(a)(2)(D) exception routing** is entirely
absent (0 hits for "one-year"/"§208"). The **§245(c)(2) unauthorized-employment bar + VAWA-exemption
linkage** and the **Pereira/Niz-Chavez NTA defect probe** are absent. Multiple doctrine sub-issues
fairly raised are entirely absent → RUB-01 gate-fails, and the strict lock only hardens this.
(Engineering commit e6bbf74 begins adding these probes, but that post-dates run 34 — the round-3
artifact under review still lacks them.) **Agree.**

### Verdict 3 — Immigration · RUB-08 (deadline detection & computation) → AGREE
Exactly three deadline objects in run 34: the Aug 20 2026 hearing (computed + cited
8 C.F.R. §1003.18 / INA §239 + prominent), and two narrative events ("Danilo hit me again on
March 15"; "I called the Bloomington police") with `computed_date: null`. The answer key's **hard
lapsed item — the asylum one-year bar, expired Aug 14 2020 — is entirely absent**: no deadline
object, no "one-year"/§208 text, no exception routing. LOCKED v1.3 r2 requires a lapsed deadline to
be computed, flagged-as-lapsed, **and** exception-routed; here it is not surfaced at all. Clear gate
fail. (Sibling commit 93112e7 adds the exception routing after the fact; irrelevant to the round-3
verdict.) **Agree.**

### Verdict 4 — Immigration · RUB-05 (FOLIO validity + semantic fit) → AGREE-WITH-NOTE
The card cites "Unauthorized Employment → Rize (Turkish city, 85%)" and "Markman Hearing surfaced
URGENT." **Both were removed in round 3** — 0 hits for "Rize"/"Markman" in run 34 / exports 75-77
(the manifest's own EP-005 says "Rize/Markman GONE," so the card is stale). RUB-05 nonetheless
gate-fails on fresh round-3 mismatches: "Consequences of Using a Fake SSN" (0.80) → the ontology
primitive **"sequence"**; "Asylum Application Deadline and Status" (0.85) → generic **"Status"**;
"Use of Fraudulent SSN" (0.90) → the entity **"Social Security Number"**; "Asylum Application
Follow-up" (0.70) → generic **"Application"**; plus ~5 family-law concepts (Matrimonial Emergency
Applications, Temporary Child Custody, etc.) surfaced on an asylum/DV matter. 14/16 IRIs resolve, 2
none, ≥4 gross mismatches. **Conclusion correct; the Rize/Markman evidence is obsolete — re-cite the
round-3 mismatches.**

### Verdict 5 — Family-custody · RUB-01 (issue completeness) → AGREE-WITH-NOTE
This is the one verdict the round-3 re-judge had interimly softened: manifest EP-006 scored FC
RUB-01 "PASS (weak)" under the pre-lock/draft reading, while the walkthrough card still shows FAIL.
**Under LOCKED v1.3 r1 (strictest) the FAIL is correct** and the interim PASS-weak is reversed:
verified against run 30, the **parental-abduction / flight-risk** issue is fairly raised ("he'd take
the kids and I'd never see them again") yet not surfaced as an actionable issue, and the **§518.17
subd. 1(a)(4) domestic-abuse best-interest custody factor** is never connected to the Jun 28 incident
("518.17"/"518B" → 0 hits). Both are doctrine-level sub-issues fairly raised and entirely absent as
surfaced issues → gate fail. **Notes on the judge's cited evidence (inaccurate for R3):** (a) the
card says custody is "misframed as Modification," but round-3 frames it as **"Child Custody
Response"/establishment** over a Petition to Establish (no "Modification" string) — the "Modification"
point is stale and, in any case, a RUB-02 naming issue, not RUB-01; (b) the abduction threat is
captured under **"Threatening Behavior,"** not "mapped to Parental Alienation" — a separate unmapped
"Parental Alienation" claim exists but the threat is not routed to it. The core RUB-01 basis
(flight-risk + §518.17 DV-factor absent) holds. **Agree the fail under LOCKED v1.3; correct the two
evidence points; flag that this overturns the interim PASS-weak.**

### Verdict 6 — Family-custody · RUB-05 (FOLIO validity + semantic fit) → AGREE-WITH-NOTE
The card says "Macedonia + Europe attached as claims @0.70 and URGENT-flagged in all 3 memos/PDFs."
Verified: there are **no claim labels "Macedonia"/"Europe"** in round 3 (the geographic content is
reachable *only* by resolving an IRI; earlier text-grep "Resen" hits were false positives inside
"repre**sen**tation"). The real, precisely-matching round-3 defect is **"Legal Representation" @0.90
→ IRI `RC15aa638D53bC3Edca48b3e` = "Resen," a North Macedonia municipality (EUR-MK), flagged
URGENT** — the round-2 geographic bug relabeled and now caught only at the IRI level (BUG-22).
Additional confirmed mismatches: "Child Endangerment" (0.75) → the entity **"Child"** (URGENT);
"Emergency Relief and Protection Orders" (0.75) → bare **"Order"/"Ruling."** 13/14 IRIs resolve.
Substantial mismatches at high confidence, several URGENT-flagged → RUB-05 gate-fails. **Conclusion
correct; the mechanism is IRI-level, not "Macedonia/Europe as 0.70 claims" — re-cite accordingly.**

---

## 3. Corrected gate scorecard under LOCKED v1.3

Two of Damien's strict rulings re-gate criteria **beyond the six contested verdicts**, campaign-wide:

- **r3 (RUB-09 strict source):** LT and FC computed their deadlines from *document-echo* citations
  with **zero codified-law pin-cites** (no §504B / no MN Rule of Civil Procedure cite). The round-3
  judge passed RUB-09 at score 1 ("nothing wrong asserted"); under strict r3 an uncited computed
  codified-law deadline **gate-fails**. → **LT RUB-09 pass→FAIL; FC RUB-09 pass→FAIL.** IMM RUB-09
  **stays PASS** (its Aug 20 hearing carries 8 C.F.R. §1003.18 / INA §239 — the campaign's one
  correctly-sourced deadline).
- **r4 (RUB-15 empty exec-summary):** every export ships an empty `executive_summary` while
  `completeness = 1.0` (BUG-23). The LT judge passed RUB-15 "with the defect noted"; under strict r4
  it **gate-fails**. → **LT RUB-15 pass→FAIL** (IMM and FC RUB-15 were already failing).

| Persona (run) | 01 | 04 | 05 | 08 | 09 | 15 | **v1.3 gates** | v1.2 R3 baseline |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Landlord-tenant** (31) | PASS* | PASS | **FAIL** | PASS | **FAIL↓** | **FAIL↓** | **3 / 6** | 5 / 6 |
| **Immigration** (34) | **FAIL** | PASS | **FAIL** | **FAIL** | PASS | **FAIL** | **2 / 6** | 2 / 6 |
| **Family-custody** (30) | **FAIL↓** | PASS | **FAIL** | **FAIL** | **FAIL↓** | **FAIL** | **1 / 6** | 3 / 6 |

`↓` = gate that flips **pass→fail** vs the round-3 v1.2 judging, purely from the strict v1.3 lock.
`*` LT RUB-01 stays PASS but is now **borderline** under strict r1 (security-deposit surfaced only
weakly with no IRI; the $300/$350/$1,200 amount inconsistency and the stretch defective-notice issue
are never flagged) — not one of the 6 contested verdicts, so left as the judge scored it, but
flagged for the round-4 re-judge.

**Net effect of the strict lock:** campaign gate-pass count drops from **10/18 → 6/18**. The strict
rulings did not overturn any FAIL; they converted several *borderline passes* (uncited deadlines,
empty exec-summary) into fails and hardened the two RUB-01 gates. This is the honest, stricter
picture Damien's rulings produce — all three personas remain **borderline** (each has ≥1 gate fail),
and the round-4 engineering targets are now: BUG-22 (RUB-05 exploration-lane semantic fit, all 3),
BUG-23 (RUB-15 exec-summary, all 3), BUG-24 (RUB-08 FC 30-day rule), primary-source citations on LT
& FC deadlines (RUB-09), and IMM doctrine-depth + lapsed-bar routing (RUB-01/08; commits e6bbf74 /
93112e7 in flight).

---

## 4. Evidence-hygiene finding for the round-4 review page

The systemic issue this appellate pass surfaced is **not** wrong verdicts — it is that the
validation-review page reused **round-2 cited evidence** on 4 of 6 cards (LT-05, IMM-05, FC-01,
FC-05) after round-3 re-ran. Every conclusion still holds on verified round-3 evidence, but the
quotes a reviewer sees are partly obsolete. **Round-4 recommendation:** regenerate each verdict card
directly from the round-4 run artifacts so the cited mismatch strings match what is actually in the
run, and drop the "round-2 walkthrough kept as explainer" overlay for any card whose evidence
changed.

---

*Sources: `personas/ANSWER-KEYS.md`; `runs/{landlord-tenant,immigration,family-custody}/run.json` +
exports 63-68 / 75-77 + memos (round 3, runs 30/31/34); `manifest.json` EP-004/005/006 scorecards;
`docs/rubrics/intake-quality-v1.3.md` (LOCKED, a31010b); `briefs/qa/2026-07-10-imm-rulings-answers.json`.
All judge-cited evidence strings independently verified against the round-3 artifacts (FOLIO IRIs
resolved live). Adjudication applies LOCKED v1.3; findings previously cited v1.2.*
