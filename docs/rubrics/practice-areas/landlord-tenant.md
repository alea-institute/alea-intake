# Practice-Area Rubric Addendum — Landlord-Tenant / Housing Law (v1)

**Rubric ID prefix:** `RUB-LT-`
**Extends:** `docs/rubrics/intake-quality-v1.md` (RUB-INTAKE-01..16, v1.1 locked 2026-07-05).
**Applies to:** any intake whose facts fairly raise a landlord-tenant / housing issue, in **any of the 50 U.S. states** — this addendum is jurisdiction-agnostic; the *judge* checks that the analysis identified the tenant's actual state and pulled that state's primary sources, not just any state's.
**Status:** judging oracle only. Personas run **unbound** (the pipeline is practice-area-agnostic); this document does not change runtime behavior — it tells a reviewer/judge what "good" looks like once a landlord-tenant matter shows up.
**Consistency source:** `docs/evidence/persona-campaign/personas/ANSWER-KEYS.md` — landlord-tenant / Danika Osgood (UAT-LT-014, MN ch. 504B) is the calibration example throughout. Every issue below is written to generalize past that one persona and one state.

**How to use this addendum:** score it *alongside* RUB-INTAKE-01..16, not instead of them. A `RUB-LT-##` finding of "missed issue" typically **also** drives a RUB-INTAKE-01 (issue completeness) or RUB-INTAKE-08/09 (deadlines) score/GATE on the general rubric. Cross-references are noted inline as `→ RUB-INTAKE-NN`.

---

## A. Issues that must be spotted (even when unnamed)

The client will almost always name only "eviction." A good analysis surfaces the rest from the facts. For each issue: the trigger facts, and the element(s)/checks a reviewer should see addressed.

### RUB-LT-01 — Eviction / unlawful detainer (nonpayment or holdover) · [primary issue] · [GATE via RUB-INTAKE-01]
**Trigger:** any notice to quit, unlawful detainer summons, "my landlord is evicting me," or a hearing/court date tied to possession.
**Checks:** correct eviction type identified (nonpayment vs. holdover vs. lease-violation vs. no-cause, per state); amount claimed reconciled against tenant's own figures (flag internal inconsistencies, e.g., $300 vs. $350 vs. $1,200 — do not silently pick one); whether tenant disputes the amount, the notice, or possession itself; procedural posture (pre-suit notice stage vs. summons already issued vs. hearing already held).
**Penalize:** treating a mid-lease eviction filing as if the *lease term itself* is what's ending (see RUB-LT-19 failure mode).

### RUB-LT-02 — Breach of warranty/covenant of habitability · [GATE]
**Trigger:** any mention of mold, pests, no heat, no water, broken locks/windows, electrical hazards, structural defects, or health effects (child's asthma, respiratory issues) — **even if the client frames the whole narrative as "I'm being evicted" and never says "habitability."**
**Checks:** condition(s) identified with dates; landlord notice of the condition (texts, calls, work orders) and landlord's response/non-response; duration of the defect; whether it's a defense to nonpayment (rent abatement / recoupment), an independent claim, or both; state's mechanism (repair-and-deduct, rent escrow, receivership, code-enforcement referral).
**This is the archetypal "unspoken issue" this rubric exists to catch** — mirrors RUB-INTAKE-01's core value proposition. A GATE failure here (habitability facts present, not surfaced) should also GATE RUB-INTAKE-01.

### RUB-LT-03 — Retaliatory eviction · [GATE]
**Trigger:** any code-enforcement complaint, health-department call, repair request, tenant organizing, or rent-escrow filing **followed within a suspiciously short window by** a notice, rent increase, non-renewal, or eviction filing.
**Checks:** timeline built explicitly (complaint date → landlord-adverse-action date); temporal proximity is the operative fact — flag if the gap is inside the state's statutory presumption window (many states presume retaliation within 90–180 days; some like MN use 1 year via case law/statute); whether landlord has a documented non-retaliatory reason; presumption vs. burden-shifting framework used correctly for that state.
**Penalize:** noting the code complaint and the notice as separate facts without connecting them — the linkage *is* the claim.

### RUB-LT-04 — Illegal lockout / self-help eviction · [GATE — safety-critical]
**Trigger:** locks changed, utilities shut off by landlord, belongings removed/held, tenant physically barred from unit, "landlord told me to leave by Friday or he'll change the locks" — **without a court order.**
**Checks:** self-help is unlawful in every U.S. state for a tenant with a possessory interest (all eviction must go through court process); identify the immediate-relief mechanism (emergency motion, restoration of possession, statutory penalty/damages — often a multiplier of rent or actual damages); this is inherently an urgency/emergency fact pattern → RUB-LT-16.

### RUB-LT-05 — Security-deposit violations
**Trigger:** deposit not returned, no itemized statement, deductions the tenant disputes, "pet deposit" or "cleaning fee" collected in cash with no receipt, deposit exceeding a state-law cap, no interest paid where required.
**Checks:** amount, form (cash/check), any receipt; state's return deadline after move-out; itemization requirement; interest requirement (some states, e.g., MN); statutory penalty for bad-faith withholding (often a multiplier); note this can arise **mid-tenancy** (irregular deposit-like charge) not just at move-out — don't assume it's only a move-out issue.

### RUB-LT-06 — Rent escrow / repair-and-deduct
**Trigger:** habitability defect (RUB-LT-02) + tenant considering or having withheld rent, paid into an escrow/registry, or deducted repair costs from rent.
**Checks:** whether the tenant actually withheld or is only threatening to; state's specific procedure (court-supervised escrow vs. self-help repair-and-deduct vs. rent receivership) — these are **not interchangeable** and using the wrong one can itself trigger an eviction for nonpayment; prerequisites (notice to landlord, opportunity to cure, monetary caps on repair-and-deduct) checked against facts.

### RUB-LT-07 — Improper / defective notice
**Trigger:** any notice to quit/vacate/cure present in the facts.
**Checks:** correct notice type and required content for the stated grounds (nonpayment vs. lease violation vs. no-cause) under that state's law; required particulars present (amount owed, specific violation, cure period) vs. vague boilerplate ("material lease violation" with no specifics — insufficient in most states); service method valid (personal, posting, mail — per state); notice period length correct for tenancy type and grounds.
**Penalize:** accepting a vague or boilerplate notice as legally sufficient without flagging it as a possible defense.

### RUB-LT-08 — Subsidized-housing protections (Section 8 / public housing / LIHTC)
**Trigger:** any mention of housing voucher, Section 8, public housing authority, HUD, "my rent is based on my income," or a subsidized-sounding building name.
**Checks:** federal good-cause/procedural protections layered on top of state eviction law (HUD "good cause" requirement, informal grievance/hearing rights before termination, specific notice content requirements); PHA involvement/notice obligations; whether the state-law eviction alone is sufficient or federal overlay changes the analysis. Missing this when present is a substantive gap, not cosmetic.

### RUB-LT-09 — Discrimination (Fair Housing Act / state/local analogs)
**Trigger:** facts suggesting the landlord's action correlates with a protected class (race, national origin, sex, familial status/children, disability, religion) or a request for a reasonable accommodation/modification that was denied or ignored, or a refusal to renew tied to a protected characteristic.
**Checks:** protected class or accommodation request identified; comparator or pattern evidence available (differential treatment of similarly-situated tenants); interplay with eviction (is discrimination a defense, a separate HUD/state-agency complaint, or both); note this is frequently the *most* unspoken issue — clients rarely self-label their landlord's conduct as discriminatory.

### RUB-LT-10 — Utility shutoff / essential-services interruption
**Trigger:** landlord-controlled utilities shut off or threatened (heat, water, electric), often overlapping with RUB-LT-02 and RUB-LT-04.
**Checks:** whether shutoff is landlord-caused (potential illegal self-help/habitability) vs. tenant's own nonpayment to the utility; emergency relief availability; treat as urgent regardless of legal theory (→ RUB-LT-16).

### RUB-LT-11 — Lease-term confusion (mid-lease action vs. lease expiration)
**Trigger:** any lease with a stated end date that is *not* the reason for the current dispute.
**Checks:** analysis must not conflate "lease runs through [future date]" with "tenancy is ending" — a mid-lease nonpayment or lease-violation eviction proceeds under different rules (and different notice/cure requirements) than a lease-expiration/non-renewal. See RUB-LT-19 (failure mode) — this is the Danika-persona "distractor" (lease to Jun 30, 2026 is not the operative event).

---

## B. Claims/elements the analysis should enumerate and link to facts

Each identified issue in Section A should, where it rises to a claim, be broken into elements with fact citations — this is the housing-specific application of **RUB-INTAKE-03**.

- **RUB-LT-12 — Habitability claim elements:** (1) condition affecting health/safety or materially affecting use, (2) landlord notice (actual or constructive) of the condition, (3) reasonable opportunity to cure, (4) landlord's failure to cure within that time, (5) causal link to damages/rent abatement claimed. Each element must cite a specific narrative fact (date, message, or document) — no generic "tenant reported issues."
- **RUB-LT-13 — Retaliation claim elements:** (1) tenant engaged in protected activity (complaint, organizing, escrow, withholding, testifying), (2) landlord took adverse action (notice, non-renewal, rent increase, eviction filing), (3) temporal proximity or other evidence of causal link, (4) absence of a legitimate non-retaliatory reason (or analysis of landlord's stated reason). Must state which state's presumption window/framework applies.
- **RUB-LT-14 — Eviction defense elements (whichever ground alleged):** ground pled by landlord (nonpayment/violation/holdover/no-cause) → element-by-element rebuttal available to tenant (payment made/tendered, no valid notice, habitability offset, retaliation, discrimination, improper service) — each tied to a fact.
- **RUB-LT-15 — Security deposit claim elements:** (1) deposit paid (amount, form, date), (2) tenancy ended or ongoing irregular charge, (3) statutory return/itemization deadline passed or violated, (4) bad faith (if state requires it for penalty), (5) damages/penalty multiplier per that state's statute.

---

## C. Deadlines & primary sources

This section is the housing-specific application of **RUB-INTAKE-08/09**, which are GATE criteria requiring deadlines to be **computed** (not just detected), **correct for the tenant's actual state**, and **cited to a primary source** (statute, court rule, local rule, or standing order) — no secondary sources, no invented deadlines, no wrong-state citations.

### RUB-LT-16 — Notice cure/vacate period computed & sourced · [GATE]
The date the landlord's notice was given/posted/served, plus that state's statutory cure or vacate period for the specific ground alleged, must be computed to a specific calendar date and cited to the governing statute (e.g., **Minn. Stat. § 504B.135** for certain notice periods, **§ 504B.321** for the summons timeline; substitute the analogous statute/rule for the tenant's actual state — e.g., Cal. Civ. Code § 1946.1/§ 1161 for CA 3-day/30-day/60-day notices, N.Y. RPAPL § 711/§ 226-c, Mass. Gen. Laws ch. 186 § 11/12, etc.).
- **Judge check:** is the notice date taken from the narrative (not invented), is the period length correct for *that ground* in *that state*, and is the resulting date arithmetic correct?

### RUB-LT-17 — Hearing/summons date and answer-period rule, correctly characterized per state · [GATE]
Some states' summary-eviction procedure has **no separate written answer** (defenses raised orally/live at the first hearing — e.g., Minnesota, per **Minn. Stat. ch. 504B** generally and § 504B.321 for the summons/hearing window); others **do** require a written answer within a short window (e.g., many other states' unlawful-detainer statutes). The analysis must state which regime applies to the tenant's state and **not invent a written-answer deadline where none exists**, and must **not omit** one where it does exist.
- **Judge check:** does the analysis correctly identify whether a written answer is required in this state, and if so, compute its deadline from that state's rule/statute? If not required, does it correctly describe the hearing itself as the operative event (with the hearing date computed and cited) instead of fabricating an answer deadline?
- This directly generalizes the Danika/MN answer key: "MN eviction has NO separate written Answer deadline — defenses raised at hearing; do NOT invent an answer deadline." A model that invents an MN answer deadline, or that assumes every state works like MN (or like a state that *does* require a written answer), fails this criterion.

### RUB-LT-18 — Rent-escrow / repair-and-deduct deadlines and caps
If RUB-LT-06 is triggered, the notice-to-landlord/cure period preceding self-help repair, any dollar/percentage cap on repair-and-deduct, and any court-escrow filing deadline must be computed and cited to that state's specific statute (e.g., Minn. Stat. § 504B.385 / § 504B.425 for MN rent escrow).

### RUB-LT-19 — Security-deposit return deadline
If a tenancy has ended, the state's post-move-out deposit-return/itemization deadline (commonly 14–45 days depending on state) must be computed from the actual move-out date and cited (e.g., Minn. Stat. § 504B.178).

### RUB-LT-20 — Statute of limitations on any damages claim
Habitability, deposit, retaliation, or discrimination damages claims each carry their own SOL (contract vs. statutory vs. tort, and FHA has its own federal/administrative timelines — typically 1 year to HUD, 2 years to federal court). Must be identified and cited even if not yet close, since it affects urgency triage.

### RUB-LT-21 — Correct-state sourcing, generally
**This rubric's deadline criteria apply identically across all 50 states.** The judge must confirm: (a) the analysis correctly identified the tenant's actual state from the facts (property address, court named, or explicit statement) — not defaulted to MN or any other state by habit; (b) every cited authority is that state's actual statute/rule/local rule/standing order (not a different state's, not a generic/national restatement, not a secondary source like a legal-aid FAQ page); (c) court-specific local rules or standing orders are checked where the state's eviction procedure is locally variable (common in housing court). A deadline that is numerically "close enough" but sourced to the wrong state's statute is a **RUB-INTAKE-09 GATE failure**, not a minor imprecision.
**MN reference set (for calibration only, not the only correct answer):** Minn. Stat. ch. 504B generally; § 504B.135 (notice), § 504B.161 (habitability), § 504B.178 (deposits), § 504B.285 / § 504B.321 (eviction actions/summons), § 504B.385 / § 504B.425 (rent escrow), § 504B.441 (retaliation).

---

## D. FOLIO concepts expected (housing/landlord-tenant branch)

The analysis's FOLIO mappings (→ RUB-INTAKE-05/06) should, where facts warrant, resolve to concepts on or near the housing/landlord-tenant branch, at minimum:

- **RUB-LT-22 — Core concept coverage:** Eviction / Unlawful Detainer; Notice to Quit (and sub-types: nonpayment, cure, no-cause, holdover); Warranty/Covenant of Habitability; Retaliatory Eviction; Security Deposit; Rent Escrow / Repair-and-Deduct; Illegal Lockout / Self-Help Eviction; Housing Court / Summary Proceeding; Defective Notice; Subsidized Housing / Housing Choice Voucher; Fair Housing / Housing Discrimination; Reasonable Accommodation.
- **Judge check:** absence of a clearly-warranted concept (e.g., no Habitability mapping despite mold facts) should be flagged against RUB-INTAKE-06 (semantic fit) or RUB-INTAKE-07 (unmappable-concept handling) as appropriate, in addition to the RUB-LT issue-spotting failure.

---

## E. Plain-language & safety notes specific to housing

Housing narratives are disproportionately likely to involve imminent, physical urgency — this compounds RUB-INTAKE-10/11.

### RUB-LT-23 — Urgency triage for imminent homelessness
Any fact suggesting the tenant may be physically displaced within days (hearing this week, lockout already occurred, notice period expiring in ≤7 days) must be flagged as **urgent/time-critical** at the top of the output, not buried after a full legal exposition. This is a housing-specific application of RUB-INTAKE-14 (referral/escalation).

### RUB-LT-24 — Lockout/utility-shutoff as immediate-action triggers
An illegal lockout or utility shutoff in progress (RUB-LT-04, RUB-LT-10) must produce a distinct "do this now" instruction (e.g., call police non-emergency line / legal aid emergency intake / tenant hotline), separate from the general next-steps list, and phrased calmly per RUB-INTAKE-11 (no panic-inducing language, but no false reassurance either).

### RUB-LT-25 — Plain-language rendering of housing jargon
Terms like "unlawful detainer," "writ of recovery," "habitability," "escrow," "constructive eviction," "quiet enjoyment" must be defined in ~6th-grade language on first use (RUB-INTAKE-10). A memo that says "you may have a habitability defense" without ever explaining what that means in plain terms fails this criterion even if legally correct.

### RUB-LT-26 — Children/health-vulnerability framing
Where facts mention a child's health condition (asthma, lead exposure) tied to housing conditions, the analysis should note this both as (a) evidence strengthening the habitability claim and (b) a safety/urgency amplifier — without being exploitative or alarmist in tone.

---

## F. Common failure modes to penalize

These are recurring, predictable ways a landlord-tenant analysis goes wrong — a judge should actively check for these, not just wait for them to surface.

### RUB-LT-27 — Treating a mid-lease eviction as lease-expiration
Confusing "the lease doesn't end until [date]" with "the eviction can't happen until then." A lease running months into the future is often a **distractor**, not the operative deadline, when the eviction is for nonpayment or a lease violation. Penalize any analysis that surfaces the lease-end date as *the* deadline when a separate eviction notice/summons is already in play. (Calibration: Danika's lease runs to Jun 30, 2026, but that is explicitly *not* the operative deadline — the 14-day notice and the Apr 1 hearing are.)

### RUB-LT-28 — Missing habitability when only eviction is named
The single most important failure mode this addendum exists to catch (→ RUB-INTAKE-01 GATE). If the narrative contains mold, no-heat, pest, or similar facts and the analysis discusses only the eviction, that is a GATE-level miss, not a minor omission.

### RUB-LT-29 — Inventing an answer deadline where the state doesn't require one
Some states' eviction procedure requires no written answer (defenses raised live at the hearing). An analysis that manufactures a generic "you must file an Answer within X days" for such a state — either by defaulting to a civil-litigation template or by wrongly importing another state's rule — is a **RUB-INTAKE-09 GATE failure** (wrong deadline stated with confidence). Equally penalize the inverse: omitting a real written-answer deadline in a state that does require one.

### RUB-LT-30 — Missing retaliation despite clear temporal proximity
Failing to connect a code complaint / repair request to a shortly-following adverse action, treating them as unrelated facts instead of building the timeline that establishes (or at least raises) a retaliation claim.

### RUB-LT-31 — Failing to reconcile inconsistent dollar amounts
Landlord-tenant narratives frequently contain conflicting figures (rent owed, deposit amount) across different parts of the story or documents. Silently picking one number without flagging the inconsistency is a fabrication-adjacent failure (→ RUB-INTAKE-04) — the analysis should surface the discrepancy as a gap/question, not resolve it by assumption.

### RUB-LT-32 — Accepting a boilerplate/vague notice as sufficient
Treating a notice that cites only "material lease violation" with no specifics as legally adequate, instead of flagging the defective-notice defense (RUB-LT-07).

### RUB-LT-33 — Defaulting to one state's rules regardless of the tenant's actual state
Because the reviewer/tester will see many personas across many states, watch specifically for analyses that reuse a previously-seen state's statutes/deadline structure (e.g., MN's no-written-answer rule, or MN's specific statute numbers) for a tenant who is actually in a different state. This is the single highest-value check for the 50-state generalization requirement in RUB-INTAKE-08/09.

### RUB-LT-34 — Treating self-help/lockout as a routine notice issue
Downgrading an already-occurred illegal lockout or utility shutoff to the same priority as a garden-variety habitability complaint, instead of flagging it as requiring immediate action (RUB-LT-24).

### RUB-LT-35 — Missing subsidized-housing or discrimination overlays
Analyzing a voucher-holder's eviction purely under state landlord-tenant law without noting the federal/PHA procedural layer (RUB-LT-08), or failing to flag a discrimination angle when protected-class facts are present but unlabeled by the client (RUB-LT-09).

---

## Summary checklist (quick-reference for a judge)

| # | Check | Ties to |
|---|---|---|
| RUB-LT-01 | Eviction/UD type correctly identified, amounts reconciled | RUB-INTAKE-01/02 |
| RUB-LT-02 | Habitability surfaced even if unnamed | RUB-INTAKE-01 GATE |
| RUB-LT-03 | Retaliation timeline built & presumption window applied | RUB-INTAKE-01 GATE |
| RUB-LT-04 | Illegal lockout/self-help flagged as urgent | RUB-INTAKE-01 GATE, RUB-INTAKE-14 |
| RUB-LT-05 | Security deposit irregularities caught | RUB-INTAKE-01 |
| RUB-LT-06 | Escrow/repair-and-deduct procedure matched to state | RUB-INTAKE-02 |
| RUB-LT-07 | Defective notice flagged | RUB-INTAKE-01 |
| RUB-LT-08 | Subsidized-housing overlay checked | RUB-INTAKE-01 |
| RUB-LT-09 | Discrimination/FHA angle checked | RUB-INTAKE-01 |
| RUB-LT-10 | Utility shutoff treated as urgent | RUB-INTAKE-14 |
| RUB-LT-11 | Lease-end date not confused with eviction deadline | RUB-INTAKE-08 |
| RUB-LT-12–15 | Elements enumerated & fact-linked | RUB-INTAKE-03 |
| RUB-LT-16–21 | Deadlines computed, correct state, primary-source cited | RUB-INTAKE-08/09 GATE |
| RUB-LT-22 | FOLIO housing concepts mapped | RUB-INTAKE-05/06/07 |
| RUB-LT-23–26 | Urgency & plain language for housing facts | RUB-INTAKE-10/11/14 |
| RUB-LT-27–35 | Common failure modes actively checked | multiple |

---

*Judging oracle only — does not bind runtime behavior. Personas continue to run practice-area-unbound per `intake-quality-v1.1` resolved question 4. Amendments to this addendum should bump to v1.1+ and note which persona findings prompted the change.*
