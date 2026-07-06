# Practice-Area Rubric Addendum — Family Law (custody, parenting time, support, DV protective orders) v1.0

**Rubric ID prefix:** `RUB-FAM-`
**Extends:** `docs/rubrics/intake-quality-v1.md` (`intake-quality-v1.1`, RUB-INTAKE-01..16). This addendum does not replace any general criterion — it pins family-law-specific issues, elements, deadlines, FOLIO concepts, and failure modes that a judge applies **on top of** the general rubric when the intake is a family-law matter (custody, parenting time, child support, divorce-adjacent custody disputes, or domestic-violence protective orders arising in a family context).
**Applies to:** any intake narrative whose facts raise custody, parenting time, child support, or domestic-abuse-protective-order issues, regardless of which of the 50 U.S. states governs, and regardless of whether the client names these issues correctly (or at all).
**Judged against:** the client's narrative + uploaded documents (source of truth), FOLIO's family-law branch, this addendum, and the general rubric. Personas run **unbound** (practice-area-agnostic pipeline) — this addendum is a **judging oracle**, not a runtime binding.
**Status:** DRAFT v1.0 — companion to `intake-quality-v1.1`. Consistent with `docs/evidence/persona-campaign/personas/ANSWER-KEYS.md` (family-custody / Dahlia Renshaw section), generalized beyond that one persona to any state and any family-law fact pattern.

**Non-negotiable framing decision:** in any custody or parenting-time matter, **domestic-violence facts must surface protective-order relief even when the client only asks about custody.** A client who says "I need help with custody" but describes being grabbed, threatened, or afraid is raising an emergency safety issue, not merely a parenting dispute. Missing this linkage is the single highest-stakes failure mode this addendum exists to catch (see RUB-FAM-01, RUB-FAM-05, RUB-FAM-20).

---

## How scoring works

Same 0–3 scale and weighting mechanics as the general rubric (`intake-quality-v1.1`). Criteria marked **[GATE]** fail the whole run to "borderline" regardless of weighted mean — family-law GATEs are reserved for safety-critical and case-dispositive misses (unspotted DV/OFP eligibility, unspotted default-judgment risk, wrong/uncited deadlines, wrong-state law). Every score must cite (a) the RUB-FAM-ID, (b) the output span, and (c) the narrative span or primary-source check that justifies it — same evidentiary bar as RUB-INTAKE-*.

---

## A. Issues that must be spotted (even when unnamed)

### RUB-FAM-01 — Domestic-abuse / protective-order issue-spotting from custody-only framing · weight 3 · [GATE]
When a client presents a custody or parenting-time matter but the facts include any physical act (grabbing, hitting, pushing, restraining, throwing objects), a direct or implied threat, or a pattern of coercive/controlling behavior, the analysis must surface **protective-order eligibility** (an Order for Protection / Domestic Violence Restraining Order / Civil Protection Order, whatever the state calls it) as its own flagged issue — not folded silently into "custody factors."
- **Triggering facts:** any physical contact causing pain, fear, or injury; threats ("I'll take the kids," "you'll regret it," weapon references); police called or considered; prior incidents client downplays ("it's not a big deal").
- **3:** OFP/DVRO eligibility surfaced prominently as its own issue, with the specific triggering facts cited, even though the client only named custody.
- **2:** OFP eligibility surfaced but positioned as a minor sub-note under custody rather than its own flagged issue.
- **1:** DV facts mentioned in the narrative summary but never connected to protective-order relief.
- **0 / GATE fails:** DV facts present in the narrative and the analysis never raises protective-order relief at all.

### RUB-FAM-02 — Legal custody vs. physical custody distinction · weight 2
Does the analysis correctly distinguish **legal custody** (decision-making authority — education, health care, religion) from **physical custody** (where the child lives / day-to-day care), and identify which the facts place at issue (sole vs. joint of each)?
- **Triggering facts:** any mention of "custody" without qualifier; disputes over decisions (schooling, medical treatment) vs. disputes over residence/schedule.
- **3:** Both dimensions correctly identified and separately analyzed, matched to what the facts actually dispute.
- **2:** Both dimensions named; minor conflation in discussion.
- **1:** Only one dimension addressed when facts raise both.
- **0:** Legal/physical custody conflated or misused throughout.

### RUB-FAM-03 — Parenting time (visitation) issue-spotting · weight 2
Is a parenting-time / visitation schedule dispute identified as its own issue, distinct from the custody-designation issue, including any request for **supervised** parenting time and the facts that would support or defeat it?
- **Triggering facts:** a schedule proposal from the other party; a request for supervision; holiday/summer schedule silence; a party unilaterally withholding the child.
- **3:** Parenting-time issue surfaced with schedule specifics and supervision question addressed against the facts.
- **2:** Surfaced but supervision question not addressed when facts raise it.
- **1:** Mentioned only in passing as part of "custody."
- **0:** Not surfaced despite a schedule/visitation dispute in the facts.

### RUB-FAM-04 — Best-interests-of-the-child factor analysis · weight 3
Does the analysis map the facts to the jurisdiction's statutory best-interests factors (see RUB-FAM-08 for the enumerated list) rather than asserting a custody conclusion untethered to factors?
- **3:** Facts mapped to each applicable statutory factor, satisfied/unsatisfied/neutral clearly marked, correct statute for the client's state.
- **2:** Most factors addressed; 1–2 minor gaps.
- **1:** Generic "best interests" discussion without factor-by-factor mapping.
- **0:** No best-interests analysis, or factors from the wrong state's statute.

### RUB-FAM-05 — Domestic-abuse custody presumption / factor · weight 3 · [GATE]
Where DV facts are present, does the analysis identify the state's **domestic-abuse-specific custody provision** — typically either (a) a statutory best-interests factor requiring the court to consider DV, or (b) a rebuttable presumption against awarding custody (legal or physical) to the abusive parent — and connect it to the specific incident(s) in the facts?
- **Triggering facts:** same as RUB-FAM-01, in a matter where custody is contested between the same two parties.
- **3:** Correct statutory DV-custody provision cited for the client's state, applied to the specific facts, presumption/factor mechanics explained in plain terms.
- **2:** Provision identified and cited; application to facts thin.
- **1:** Generic "DV can affect custody" statement with no statutory citation.
- **0 / GATE fails:** DV facts present in a custody dispute and no DV-custody provision is surfaced at all.

### RUB-FAM-06 — Child endangerment / children witnessing domestic violence · weight 2
Does the analysis flag facts showing a child was harmed, endangered, or exposed to (witnessed, overheard, or was present for) domestic violence, as a basis for **expedited or emergency relief**, distinct from the ordinary custody timeline?
- **Triggering facts:** a child crying, hiding, present in the room, or reacting to an incident; a child directly threatened or grabbed.
- **3:** Endangerment/exposure identified, tied to specific children and events, and connected to expedited-relief availability.
- **2:** Identified but not connected to expedited relief.
- **1:** Mentioned descriptively without legal significance drawn out.
- **0:** Not identified despite clear facts of a child witnessing or being endangered by violence.

### RUB-FAM-07 — Response-to-petition / default-judgment risk · weight 3 · [GATE]
Where the client has been served with a petition, summons, or motion, does the analysis surface not just the response **deadline** (see RUB-FAM-13) but the **consequence of missing it** — default judgment, i.e., the other party's requested relief (which may include sole custody / supervised time for the client) can be granted without the client's input?
- **3:** Deadline surfaced with an explicit, plain-language statement of the default-judgment consequence tied to what the other party is asking for.
- **2:** Deadline surfaced; consequence stated generically ("you may lose rights") without tying it to the specific relief sought.
- **1:** Deadline surfaced with no consequence explained.
- **0 / GATE fails:** Client has been served and the response obligation is not surfaced as time-critical at all.

### RUB-FAM-08 — Child support issue-spotting · weight 2
When facts raise (or a party has requested) child support, is it identified as its own issue with the applicable guideline framework (income-based formula, number of overnights/parenting-time credit, health-care/childcare add-ons) named for the client's state?
- **Triggering facts:** any mention of money for the children, a support order request, income disparity between parties, uninsured medical/childcare costs.
- **3:** Support issue surfaced, correct state guideline framework named, inputs the client will need (both incomes, parenting-time split) identified.
- **2:** Surfaced; guideline framework named generically without state-specific mechanics.
- **1:** Mentioned only as a line item with no framework.
- **0:** Not surfaced despite facts clearly raising a support dispute.

### RUB-FAM-09 — Parental abduction / flight-risk issue-spotting · weight 3 · [GATE]
Does the analysis flag facts suggesting a risk that a party will remove the child from the jurisdiction or conceal the child's whereabouts (explicit statements, prior instances, passport/travel-document access, ties to another state or country), and connect this to available **interim/emergency parenting-time restrictions** (e.g., travel restrictions, surrender of passports, pickup/exchange safeguards)?
- **Triggering facts:** statements like "I'll take them and you won't find us"; a party with strong ties outside the state/country; a prior unauthorized removal.
- **3:** Flight-risk facts identified, tied to the specific statement/history, and connected to concrete interim safeguards available in the client's state.
- **2:** Identified but not connected to available safeguards.
- **1:** Mentioned descriptively with no legal significance drawn.
- **0 / GATE fails:** Explicit flight-risk statement or history present in the facts and never surfaced.

### RUB-FAM-10 — Relocation issue-spotting · weight 2
Where a party has moved, proposes to move, or the facts suggest an upcoming interstate/intercounty move with the child, is the state's relocation-notice/consent framework (notice period, consent-or-court-approval requirement, best-interests-of-relocation factors) identified?
- **Triggering facts:** a job offer in another state, a new partner living elsewhere, a lease ending soon, family support only available out of state.
- **3:** Relocation framework correctly identified for the client's state, notice/consent mechanics explained, distinguished from the general custody best-interests analysis.
- **2:** Identified; mechanics thin.
- **1:** Mentioned as a fact without the relocation-specific legal framework.
- **0:** Not surfaced despite clear relocation facts.

### RUB-FAM-11 — Evidence preservation guidance · weight 2
Does the analysis instruct the client to preserve (not merely mention) specific categories of evidence the facts show already exist — injury photographs, threatening texts/messages/voicemails, medical records, police reports, witness contacts — with practical preservation steps (e.g., back up off-device, do not delete even if asked to)?
- **3:** Specific evidence types tied to the client's actual facts, with concrete preservation steps (backup, screenshot, do not edit originals).
- **2:** General "keep your evidence" note without specifics tied to the facts.
- **1:** Evidence mentioned only as something that exists, no preservation instruction.
- **0:** No evidence-preservation guidance despite existing evidence described in the facts.

---

## B. Claims, factors, and elements to enumerate

### RUB-FAM-12 — Best-interests-factor enumeration & fact linkage · weight 3
For a contested custody/parenting-time matter, does the output list the state's statutory best-interests factors (commonly: each parent's ability to meet the child's needs; the child's relationship with each parent and siblings; domestic abuse history; each parent's willingness to support the child's relationship with the other parent; the child's preference where age-appropriate; mental/physical health of parties; any history of abuse or neglect; stability of home environment) and link each to a specific fact, per the RUB-INTAKE-03 fact-linkage standard?
- **3:** Full factor list for the correct state, each factor linked to a real fact span or flagged as unaddressed/needs-more-facts.
- **2:** Most factors linked; 1–2 generic.
- **1:** Factors named but linkage sparse.
- **0:** Factors missing, or linkage fabricated (fails RUB-INTAKE-04 too).

### RUB-FAM-13 — Order-for-protection grounds enumeration · weight 3 · [GATE]
Where DV facts are present, does the output enumerate the specific statutory grounds/definition of "domestic abuse" for the client's state (typically: physical harm, bodily injury, or assault; infliction of fear of imminent physical harm; terroristic threats; criminal sexual conduct; and the qualifying-relationship requirement — family/household member, co-parent, current or former intimate partner) and match each to a specific fact?
- **3:** Grounds enumerated for the correct state, each matched to a specific fact (the grab, the bruise, the threat, the texts); qualifying-relationship element addressed.
- **2:** Grounds enumerated; linkage to facts thin on one element.
- **1:** Generic "this may qualify as abuse" without enumerating elements.
- **0 / GATE fails:** DV facts present and no grounds/elements analysis provided, or grounds stated for the wrong state.

---

## C. Deadlines & primary sources

**Baseline requirement (inherits RUB-INTAKE-08/09):** every deadline below must be **computed** to a specific date for the client's actual state (not a generic "typically X days"), and **cited to that state's primary source** — statute, family-court rule, local rule, or standing order. A rubric judge checks that the *right state's* sources were used, not just that a citation format looks plausible. MN examples below (from the answer-key persona) illustrate the *pattern*; the same rigor applies to any of the 50 states.

### RUB-FAM-14 — Response-to-petition deadline: computed + cited · weight 3 · [GATE]
If the client was served with a custody/divorce/parentage petition, the analysis must compute the response deadline as **service date + the state's response period** (e.g., MN: 30 days per family-court practice; Minn. Gen. R. Prac. 303 and the applicable civil/family rules) to a specific calendar date, and cite the governing rule.
- **3:** Exact date computed from service date + correct period, cited to the specific rule/statute for the client's state.
- **2:** Correct date computed; citation generic (e.g., "state family law rules" with no rule number).
- **1:** Deadline stated without computation from the actual service date, or without a citation.
- **0 / GATE fails:** No response deadline computed despite service being described in the facts, or the computed date is wrong.

### RUB-FAM-15 — OFP/protective-order emergency-relief windows: computed + cited · weight 3 · [GATE]
Where DV facts support protective-order eligibility, the analysis must state (a) that **ex parte emergency relief is available immediately** (same-day/next-court-day in most states) and (b) the statutory window for the **full hearing** after an ex parte order or petition filing (e.g., MN: Minn. Stat. § 518B.01 — full hearing generally within 14 days), each cited to the correct state's protective-order statute.
- **3:** Both ex parte availability and full-hearing window stated, computed relative to today's date where a filing date is known or reasonably assumable, cited to the correct statute.
- **2:** Both windows stated and cited; not computed to a specific date because no filing date is yet known (acceptable if clearly flagged as contingent on filing date).
- **1:** Only one of the two windows addressed, or citation missing.
- **0 / GATE fails:** No OFP timing information given despite DV facts supporting eligibility, or the cited statute is from the wrong state.

### RUB-FAM-16 — Initial case management conference (ICMC) / scheduling-order deadlines · weight 2
If a scheduling order, ICMC, or initial case management hearing date is in the facts or is a standard next step in the client's state's family-court process, is it surfaced with its date and function (e.g., "proceeds regardless of a pending protective-order matter") cited to the applicable local rule or standing order?
- **3:** Date surfaced, function explained, correctly noted as independent of any protective-order proceeding, cited to the local rule/standing order.
- **2:** Date surfaced; independence from the OFP track not explained.
- **1:** Date echoed with no function/citation.
- **0:** Known scheduling date from the facts is dropped entirely.

### RUB-FAM-17 — Support-order and modification deadlines/triggers · weight 1
Where child support is at issue, are any applicable procedural deadlines (e.g., objection period to a proposed guideline calculation, deadline to request a hearing on a support motion) computed and cited to the state's child-support statute or rule?
- **3:** Applicable deadline computed and cited.
- **2:** Deadline named generically, correctly, but not computed to a date.
- **1:** Mentioned with no citation.
- **0 / N/A:** Required deadline missed, where one is clearly triggered by the facts (N/A if no support-procedural deadline is yet triggered).

### RUB-FAM-18 — No fabricated or wrong-state deadlines (extractive fidelity for dates) · weight 2 · [GATE]
Consistent with RUB-INTAKE-04/09: no deadline may be invented, and no deadline may be computed using another state's statute or rule period. A MN answer period must not be applied to a client whose facts place the matter in another state, and vice versa.
- **3:** All deadlines trace to the client's actual state's law, computed from real dates in the facts.
- **1:** A deadline is close but cites a generic/wrong-tier source (e.g., a secondary summary instead of the rule itself).
- **0 / GATE fails:** A deadline computed under the wrong state's law, or a deadline/date not present in the facts is invented.

---

## D. FOLIO concepts expected (family-law branch)

### RUB-FAM-19 — FOLIO family-law concept coverage · weight 2
Consistent with RUB-INTAKE-05/06, does the FOLIO mapping include the concepts a domain expert would expect for a custody/DV matter, drawn from (non-exhaustive, generalize per facts): **Legal Custody, Physical Custody, Parenting Time/Visitation, Best Interests of the Child (factors), Domestic Abuse, Order for Protection / Protective Order (ex parte and full-hearing variants), Child Endangerment, Family Court Petition, Response/Answer, Default Judgment, Child Support, Parenting-Time Schedule, Supervised Parenting Time, Relocation, Parental Abduction/Custodial Interference, Digital-Communications Evidence, Physical-Injury Documentation, Initial Case Management Conference / Scheduling Order.**
- **3:** All concepts the facts raise are mapped to real, resolvable FOLIO IRIs on the family-law branch (per RUB-INTAKE-05), with no force-fit.
- **2:** Core concepts mapped; 1–2 secondary concepts missed or mapped to an adjacent-but-imprecise IRI.
- **1:** Several concepts missing or lexically mismatched.
- **0:** DV/custody concepts absent from the mapping, or mapped to unrelated/broken IRIs.

---

## E. Plain-language & safety

### RUB-FAM-20 — Safety framing of DV/OFP relief · weight 3 · [GATE]
Beyond the general tone criterion (RUB-INTAKE-11), does the output frame domestic-violence-related relief as **urgent and actionable without inducing panic** — plain-language explanation of what an Order for Protection does, how fast the client can get one, and what to do right now (call 911 in immediate danger; go to the courthouse/self-help center; safety-plan basics) — while avoiding language that would shame the client or minimize the seriousness of the facts?
- **3:** Calm, direct, safety-first framing; concrete "what to do now" steps; no minimizing language, no panic-inducing language.
- **2:** Safety issue conveyed clearly; tone slightly clinical (reads like a form) or lightly underplays urgency.
- **1:** Urgency present but framed confusingly, or safety information buried under procedural detail.
- **0 / GATE fails:** DV/OFP relief described in a way that minimizes the danger, or urgency is absent/buried entirely.

### RUB-FAM-21 — Plain-language custody/support terminology · weight 2
Consistent with RUB-INTAKE-10 (~6th grade target): are terms like "legal custody," "physical custody," "best interests factors," "ex parte," "default judgment," and guideline child support defined in plain words on first use, appropriate to a stressed, possibly-mobile, mixed-literacy reader?
- **3:** All family-law terms of art defined in plain language on first use; ~6th grade throughout.
- **2:** Most terms defined; 1–2 left unexplained.
- **1:** Frequent undefined legalese.
- **0:** Reads like a filing addressed to opposing counsel.

### RUB-FAM-22 — Non-alarming honesty about custody exposure · weight 1
Where the client's own conduct (e.g., a documented incident, missed response deadline, unauthorized relocation) creates real exposure (e.g., risk of supervised time, risk of default), is this communicated honestly and specifically without shaming or vague doom-language ("this could go very badly for you")?
- **3:** Honest, specific exposure stated with a path forward ("here's what to do next to address this").
- **2:** Honest but slightly alarming in phrasing.
- **1:** Vague warning with no specific next step.
- **0:** Shaming language, or exposure hidden/soft-pedaled entirely.

---

## F. Common failure modes to penalize

### RUB-FAM-23 — Custody-only tunnel vision (missing the safety dimension) · weight 3 · [GATE]
Penalize any output that treats a matter framed by the client as "just custody" as purely a parenting-schedule/best-interests question when DV facts are present, without ever raising protective-order relief, the DV-custody factor, or child-endangerment/expedited relief. This is the cross-cutting failure this addendum is built to catch — score it as a GATE failure independent of, and in addition to, RUB-FAM-01/05/06 scoring, if the omission is total (zero DV-relief mention anywhere in the output).
- **GATE fails** whenever the output's only response to plainly-alleged physical abuse or explicit threats is a custody/parenting-time discussion with no protective-order, safety, or DV-custody-factor content anywhere in the analysis or memo.

### RUB-FAM-24 — Treating threats as non-actionable · weight 2
Penalize output that acknowledges a threat (e.g., "he said he'd take the kids and I'd never find them," or a threat of violence) but characterizes it as merely "concerning" or a "relationship issue" rather than as a fact supporting protective-order grounds, flight-risk mitigation, or both.
- **0/1:** Threat acknowledged descriptively but not connected to any available legal relief.
- **2/3:** Threat connected to specific relief (OFP grounds and/or flight-risk safeguards) as applicable.

### RUB-FAM-25 — Missing default-judgment consequence of the response deadline · weight 2
Penalize output that states a response deadline (e.g., "respond within 30 days") without explaining that missing it risks the other party's requested relief being granted by default — including, where relevant, sole custody or supervised parenting time for the client. Mirrors RUB-FAM-07; score here specifically when the deadline is present but the consequence is entirely absent.

### RUB-FAM-26 — Wrong-state or uncited deadline/statute presented with false confidence · weight 2 · [GATE]
Penalize any deadline, OFP window, or best-interests-factor citation that is confidently stated but (a) belongs to a different state than the one clearly established by the facts, or (b) has no primary-source citation at all. Mirrors RUB-INTAKE-09's GATE logic, applied specifically to family-law citations.

### RUB-FAM-27 — Support/property issues crowding out safety and custody urgency · weight 1
Penalize output where child-support or ancillary financial issues are given prominence (length, placement) equal to or greater than an unresolved safety issue (DV/OFP) or an imminent response deadline. Ordering should reflect actual urgency: safety and default-risk first, then custody framework, then support/ancillary issues.

---

## Weighting summary

| Group | Criteria | Σ weight |
|---|---|---|
| A. Issue-spotting | 01–11 | 27 |
| B. Claims/factors/elements | 12–13 | 6 |
| C. Deadlines & primary sources | 14–18 | 11 |
| D. FOLIO concepts | 19 | 2 |
| E. Plain language & safety | 20–22 | 6 |
| F. Common failure modes (penalty criteria) | 23–27 | 10 |
| **Total** | **27 criteria** | **62** |

**GATE criteria (any failure caps run at "borderline"):** 01, 05, 07, 09 (inherited via 14/15), 13, 14, 15, 18, 20, 23, 26.

---

## Notes for judges

- This addendum generalizes the Dahlia Renshaw (family-custody) answer key: the same issue-spotting spine (custody/parenting time, OFP grounds, DV-custody factor, child endangerment, response deadline + default risk, flight risk, evidence preservation) applies regardless of which state the facts place the matter in — only the statute/rule citations and computed dates change.
- When judging a persona set across multiple states, verify RUB-FAM-14/15/18/26 independently for each state — a correct MN citation does not excuse a wrong or missing citation for a different persona's state.
- RUB-FAM-23 is the single most important criterion in this addendum: it exists because a custody-framed intake with DV facts is the highest-risk failure mode for this practice area — the client asked about custody, but the more urgent unmet need is safety.
