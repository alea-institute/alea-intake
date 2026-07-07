# Persona Answer Keys — judging oracle (v1)

Hidden ground truth for the 3 core personas. The system under test never sees this;
the judge stage scores its output against these expectations per `intake-quality-v1`.
Reference "today" is baked into each narrative so deadline math is deterministic.

---

## landlord-tenant — Danika Osgood (UAT-LT-014) · MN ch. 504B · "today" = Mar 22, 2026

**Issues that MUST be spotted:**
1. Eviction / unlawful detainer for nonpayment (primary; only $300 shortfall disputed, amount internally inconsistent $300 vs $350 vs $1,200).
2. **[GATE] Breach of warranty of habitability** — mold since Oct 2025 (texts Nov 12, Dec 2), 5-day heat outage Jan 18–23 in sub-freezing weather; child asthma. § 504B.161; rent-escrow § 504B.385/.425.
3. **[GATE] Retaliatory eviction** — city code call Feb 20 → inspector cited landlord Feb 25 → 14-day notice Mar 3 (days later). § 504B.285 subd.2 / § 504B.441. Temporal proximity is the key fact.
4. Security-deposit irregularity — $500 cash "pet deposit," no receipt/interest. § 504B.178/.172.
5. (stretch) Defective/vague notice — "material lease violation" box with no particulars.

**Deadlines to surface + compute:**
- 14-day notice: posted **Mar 3** → cure/vacate by **Mar 17, 2026**.
- Operative: **court hearing Apr 1, 2026 9:00am** (summons issued Mar 18 → 14 days out, outer edge of § 504B.321's 7–14 day window; flag as worth checking). MN eviction has NO separate written "Answer" deadline — defenses raised at hearing; do NOT invent an answer deadline.
- Distractor (should NOT be an operative deadline): lease runs to Jun 30, 2026 (mid-lease, not expiration).

**FOLIO-ish concepts:** Eviction/Unlawful Detainer, Notice to Quit, Warranty of Habitability, Retaliatory Eviction, Security Deposit, Rent Escrow/Repair-and-Deduct, Housing Court, Defective Notice.

---

## immigration — Marisol "Mari" Gómez (A 000-111-222) · Fort Snelling EOIR · "today" ≈ early Jul 2026

**Issues that MUST be spotted:**
1. Removal proceedings / respond to NTA (named).
2. **[GATE] Asylum one-year deadline LAPSED** — entry 08/14/2019 → deadline 08/14/2020 (~6 yrs past). Must compute as lapsed → route to exception (INA §208(a)(2)(D)): extraordinary circumstances (notario fraud by "Rigoberto") / changed circumstances (DV).
3. **[GATE] VAWA self-petition** — spouse (married 2022) of LPR (Danilo, GC ~2016) subjected her to battery/cruelty. Client never named.
4. **U nonimmigrant status** — victim of qualifying crime (domestic assault 03/15/2026), cooperated w/ Bloomington PD; I-918B not yet requested. Never named.
5. Notario fraud / UPL by "Rigoberto" (consumer referral + asylum-exception evidence).
6. Unauthorized employment (borrowed SSN) → §245(c)(2) adjustment bar, BUT VAWA self-petitioners exempt (non-obvious linkage).
7. Possible Pereira/Niz-Chavez NTA defect (ask if 2019 NTA had time/date/place).
8. (future) Non-LPR cancellation §240A(b) needs 10 yrs presence; she has ~7 — monitor, don't over-promise.

**Deadlines:**
- **HARD:** hearing **Aug 20, 2026 9:00am Fort Snelling Ct 3**; missing → in absentia removal.
- **LAPSED (compute):** asylum 1-yr = **Aug 14, 2020**.
- Soft: U-cert I-918B no statutory deadline but request promptly (valid ~6 mo once signed).
- Contingent: VAWA no deadline while married; if divorce, 2-yr window opens.

**FOLIO-ish concepts:** NTA, Removal Proceedings, In Absentia Order, Asylum/I-589, One-Year Deadline, Extraordinary/Changed Circumstances Exception, VAWA Self-Petition/I-360, Battered Spouse of LPR, Extreme Cruelty, U Status/I-918, Qualifying Criminal Activity, I-918B Certification, Unauthorized Employment, §245(c)(2) bar, Notario Fraud/UPL, Cancellation of Removal, Prosecutorial Discretion, Motion for Continuance, Pereira defect.

---

## family-custody — Dahlia Renshaw · Hennepin Co. MN · "today" = Jul 5, 2026

**Issues that MUST be spotted:**
1. Custody / parenting time (best-interest § 518.17 via § 257.541 non-marital); petitioner seeks sole legal+physical, supervised time for client (named).
2. **[GATE] Grounds for Order for Protection (§ 518B.01)** — Jun 28 physical grab leaving bruise (photographed), explicit threat, preserved threatening texts. Client never labels it.
3. **[GATE] Domestic-abuse custody factor** — § 518.17 subd.1(a)(4); same incident bears on custody, presumption issues.
4. Child endangerment / children witnessing DV (Miles crying, Ava's reaction) — emergency/expedited relief basis.
5. Timely Response to avoid default (client knows "30 days," not the default consequence).
6. Parental-abduction / flight risk ("I'll take them and you won't find us") → interim parenting-time terms.
7. Evidence preservation (injury photos, saved texts).

**Deadlines:**
- **Response to Petition:** served **Jun 15, 2026** + 30 days = **Jul 15, 2026** (10 days out as of narrative — urgent).
- **ICMC Jul 22, 2026 9:00am** — proceeds regardless of OFP.
- **OFP urgency:** incident Jun 28 (~1 wk ago) → ex parte relief available immediately, full hearing within 14 days of filing; time-sensitive independent of custody deadline.

**FOLIO-ish concepts:** Legal Custody, Physical Custody, Parenting Time/Visitation, Best Interests factors, Domestic Abuse, Order for Protection (ex parte), Child Endangerment, Family Court Petition, Response/Answer deadline, Default Judgment, ICMC, Digital-Communications Evidence, Physical-Injury Documentation.

---

## consumer-debt — Terrell Whitfield (UAT-CD-018) · Ramsey Co. MN · "today" = Jul 8, 2026

**Issues that MUST be spotted:**
1. FDCPA collection abuse (named-ish): calls before 8am (7:15/7:55am) and after 9pm (9:38pm) — 15 U.S.C. § 1692c(a)(1); calls at work after being told not to — § 1692c(a)(3); third-party disclosure of the debt to sister Renee — §§ 1692b/1692c(b); harassing volume (6–7/day) — § 1692d.
2. **[GATE] False garnishment threat** — "garnish your wages and freeze your bank account by the end of the month" with NO lawsuit filed, NO judgment. MN garnishment generally requires judgment (Minn. Stat. § 571.71); threat is a § 1692e(4)/(5) misrepresentation. Client never labels this as illegal — he believes it.
3. **[GATE] Exempt-income protection** — sole income is SSDI ($1,480/mo direct deposit, 42 U.S.C. § 407(a)) + ~$168/wk part-time wages, below the 40× minimum-wage floor of Minn. Stat. § 571.922 (as amended eff. Apr. 1, 2025: tiered 10/15/25%, full exemption below 40×). Bank-account garnishment would trigger the § 571.912 exemption-notice process (14-day freeze, exemption claim form; Social Security listed as exempt). Practically judgment-proof — he doesn't know it.
4. **[GATE] Limitations trap / "$50 good-faith payment"** — last payment Aug 2020; MN 6-yr consumer-debt SOL (Minn. Stat. § 541.05 subd. 1(1); § 541.053) expires ~Aug–Oct 2026. A payment NOW (before expiration) restarts the clock; after expiration the debt cannot be revived by payment (§ 541.053). The system must advise NOT to pay the $50 without advice. He explicitly asks "should i pay the 50?" — correct answer is no/not yet.
5. Amount internally inconsistent: letter $2,483.17 vs. "mr. drummond" phone figure $3,100 vs. client's memory "~two grand" (letter itemization: $2,061.42 + interest). Misstating the amount also implicates § 1692e(2)(A).
6. (stretch) Voicemail "legal remedies are being prepared" — § 1692e(5) threat of action not intended/able to be taken while debt nears time-bar.

**Deadlines to surface + compute:**
- **FDCPA validation/dispute window:** notice RECEIVED **Jun 25, 2026** + 30 days = dispute/verification request by **Jul 25, 2026** (15 U.S.C. § 1692g(a)–(b)); written dispute forces collection to stop until verification. 17 days out — urgent, actionable.
- Distractor #1 (must NOT be operative): "settlement offer expires **Jul 3, 2026**" — marketing deadline, no legal effect, already passed.
- Distractor #2: computing the 30 days from the letter DATE (Jun 20 → Jul 20) is WRONG; § 1692g runs from receipt (Jun 25 → Jul 25).
- **SOL watch (compute + caveat):** last payment "Aug 2020" → 6-yr SOL expires ~**Aug 2026** (exact day unknown — gap question); letter's itemization date Oct 14, 2020 suggests accrual possibly as late as ~Oct 2026. Judge note: accrual date is genuinely ambiguous on these facts (last-payment vs. default date); credit for flagging the ~Aug–Oct 2026 window + the restart risk, not for a fake-precise date.

**FOLIO-ish concepts:** Debt Collection, FDCPA, Consumer Protection, Debt Validation/Verification, Garnishment, Exempt Income/Property Exemptions, Social Security Disability Benefits, Statute of Limitations, Time-Barred Debt, Harassment (creditor), Judgment-Proof Debtor.

**Gap questions:** exact date of last payment on the account (fixes SOL); did he ever dispute in writing already; any court papers ever served (checks for default judgment he missed); does the sister's contact repeat (§ 1692b limits); state ID of the collector (MN collection-agency licensing, Minn. Stat. ch. 332); amount of rent/essential expenses (hardship framing).

---

## wage-theft — Esteban "Junior" Maldonado (UAT-WT-019) · Hennepin Co. MN · "today" = Jul 9, 2026

**Issues that MUST be spotted:**
1. Unpaid final wages (named): 108 hours (Jun 8–19, 2026) never paid after discharge Jun 19; written demand texted **Jun 22, 2026, 10:03am**. Minn. Stat. § 181.13(a): wages due immediately on demand; penalty after 24 hours of default.
2. **[GATE] Misclassification as independent contractor** — control facts planted everywhere (employer sets schedule/sites, company van/tools, no other customers, can't refuse work, "removal from schedule" discipline): employee in fact despite the signed agreement. Unlocks §§ 181.13/181.14 penalties, MFLSA overtime, earnings-statement rights (§ 181.032), and UI eligibility (§ 268.035 "employment" — his "can i even get unemployment as a 1099?" question must be answered YES, likely).
3. **[GATE] Unpaid overtime** — 50–56-hr weeks all spring paid straight time. MFLSA: time-and-a-half over 48 hrs/wk (Minn. Stat. § 177.25); FLSA over 40 hrs/wk if enterprise coverage (29 U.S.C. § 207 — judge note: coverage unverified, flag as question, don't assume).
4. **[GATE] Retaliation** — asked about overtime Jun 19 12:36pm, fired same day 9:12pm (text evidence). Minn. Stat. § 181.03 subd. 6 (wage-theft retaliation); § 177.32; timing is the key fact, client says "NOT a coincidence" but doesn't name the claim.
5. Wage theft (2019 Wage Theft Act): no earnings statements ever (§ 181.032), no wage notice, hours shaved on checks; criminal wage theft Minn. Stat. § 609.52 subd. 2(a)(19) (report to DLI/AG — remedy framing, not client's burden).
6. Rate internally inconsistent: narrative/notebook "$24/hr" vs. signed agreement "$22.00/hr" — damages math must flag it, not silently pick one.
7. (stretch) "You get paid when the builder pays me" is not a defense to § 181.13; "pay-when-paid" doesn't apply to wages.

**Deadlines to surface + compute:**
- **§ 181.13 penalty clock (compute):** demand Jun 22 → payable within 24 hrs (Jun 23); penalty = average daily earnings/day of default, **capped at 15 days → maxed out ~Jul 8, 2026** (day before "today"). Penalty is fully accrued; nothing further accrues by waiting — file/demand now. This is a computation the system must actually run, not echo.
- **SOL:** Minn. Stat. § 541.07(5) — 2 yrs (3 yrs if willful). Employment began Mar 2024, so earliest OT weeks (spring 2024) start dropping off ~Mar 2026 onward under the 2-yr rule — recovery window is actively shrinking; willfulness (deliberate 1099 scheme, shaved hours) supports 3 yrs.
- Distractor: none of the text-thread dates (Jul 1, Jul 6) are deadlines; "talk to my lawyer" is noise.

**FOLIO-ish concepts:** Wage and Hour, Unpaid Wages, Final Paycheck/Prompt-Payment Penalty, Employee Misclassification, Independent Contractor, Overtime, Retaliation/Wrongful Discharge, Earnings Statement, Wage Theft, Unemployment Insurance Eligibility, Demand Letter, DLI Administrative Complaint.

**Gap questions:** total weeks/hours since Mar 2024 (damages + SOL triage); did the "builder" or GC ever pay him directly (joint employment); construction-industry work — Minn. Stat. § 181.723 independent-contractor test applies to building construction (stricter, helps him); did UI application list Vantera (employer will contest); wife's due date / household urgency (expedite); copies of the checks (rate proof: $22 vs $24).

---

## benefits-denial — Renata Sikorski (UAT-BD-020) · Ramsey Co. MN · "today" = Jul 7, 2026

**Issues that MUST be spotted:**
1. UI appeal of Determination of Ineligibility (named): discharge coded as "employment misconduct" (attendance). Appeal is to a DEED unemployment law judge, not the employer.
2. **[GATE] Statutory misconduct carve-out** — absence WITH PROPER NOTICE to care for the illness/injury/disability of an immediate family member is NOT employment misconduct (Minn. Stat. § 268.095 subd. 6(b)). Facts planted: daughter's DKA hospitalization May 4–6 + May 11 follow-up, charge-nurse-line call before every shift, hospital records corroborate. Client never cites the exception — she just says "how is that misconduct." This is the winning legal theory and the core gate.
3. **[GATE] She stopped filing weekly benefit-payment requests** ("i stopped doing the weekly thing... like a month") — must resume immediately; benefits are only payable for weeks actually requested (Minn. Stat. § 268.085 subd. 1; determination letter says so explicitly). Weeks not requested may be unrecoverable — independent, urgent, unspoken.
4. **[GATE] HR-appeal red herring** — she believes missing the employer's internal "10-business-day" appeal forfeited everything. It has ZERO effect on the state UI appeal. System must affirmatively de-confuse this ("did I already blow it?" → no).
5. Factual inconsistency to flag: employer letter lists 4 occurrences incl. **Mar 30, 2026**, which client says she worked (witness: coworker Delores); narrative says "3 days in may." Termination itself may rest on a false occurrence — useful on appeal.
6. (stretch) "Verbal coaching May 5, 2026" was delivered while her child was hospitalized — undermines "prior warnings" narrative; single warning ≠ pattern.

**Deadlines to surface + compute:**
- **UI appeal:** determination SENT **May 29, 2026** + **45 calendar days** = appeal filed by **Jul 13, 2026** (Minn. Stat. § 268.101 subd. 2; § 268.105; period runs from sending, cannot be extended). **6 days out — the emergency of this persona.**
- **Judge note (accuracy):** the campaign spec circulated "20 calendar days" for this deadline — that was pre-2023 law. Current Minn. Stat. § 268.101 was amended (2023) to **45 calendar days**; the 20-day period now lives at § 268.105 subd. 2 (request for RECONSIDERATION of a ULJ decision, sent within 20 calendar days of the ULJ decision — the next deadline in the chain if she loses the hearing). A system answering "20 days → deadline passed Jun 18" fails; correct answer is 45 days → Jul 13, 2026, still open.
- Distractor #1 (must NOT be operative): employer HR appeal "within 10 business days" of May 15 letter — internal policy, expired, irrelevant to UI rights.
- Distractor #2: "effective date of benefit account May 17, 2026" — account date, not a deadline.

**FOLIO-ish concepts:** Unemployment Insurance/Compensation, Administrative Appeal, Determination of Ineligibility, Employment Misconduct, Discharge/Termination, Evidentiary Hearing (ULJ), Continued/Weekly Benefit Claims, Government Benefits, Caregiver/Family Medical Absence, Witness Evidence.

**Gap questions:** exactly when did she stop weekly requests (quantify at-risk weeks); does she have the charge-nurse call log or names (notice proof); written attendance policy + prior discipline history; was Mar 30 a scheduled day (rebut the 4th occurrence, get Delores's contact); current income (DoorDash) — must be reported on weekly requests; interpreter/accessibility needs for the ULJ phone hearing.

---

## employment-discrimination — Gideon Okafor (UAT-ED-021) · Hennepin Co. MN · "today" = Jul 10, 2026

**Issues that MUST be spotted:**
1. Disability discrimination — discharge (named-ish): fired **May 22, 2026** for inability to do "essential functions" after lifting restriction (herniated disc, MRI). ADA (42 U.S.C. § 12112, enforced via § 12117) + MHRA (Minn. Stat. § 363A.08 subd. 2).
2. **[GATE] Failure to accommodate as a SEPARATE violation** — request Mar 9, 2026 with doctor's note; categorical denial **Apr 6, 2026**; no interactive process ("they sat on it... never really talked to me about options"); reasonable options existed (scan station, lift-assist, heavy lifts only "a couple times an hour" — essential-function fight). Separate accrual date → separate deadline math (below). Client asks only about "the discrimination"; the accommodation claim is distinct.
3. **[GATE] Light-duty policy limited to work-comp injuries** — HR-114 reserving modified duty for occupational injuries while denying it for equally-restricted non-occupational disability is classic disparate treatment evidence (comparator: "trevor" got 4 months on scan station). Unspoken — client presents it as an unfair detail, not a theory.
4. **[GATE] Severance/general release trap** — offered Jun 30, 2026; sign by **Jul 21, 2026** or forfeit $3,520; releases ADA/MHRA/FMLA claims. System must (a) flag do-not-sign-without-advice, (b) NOT present Jul 21 as a legal/statutory deadline, (c) note the MHRA 15-day post-signing rescission right (Minn. Stat. § 363A.31) already recited in the document. He's 38 → ADEA/OWBPA 21-day regime does not apply; the 21-day look is contractual mimicry.
5. **[GATE] FMLA never offered** — ~3.7 yrs tenure, large employer; placed on 7 weeks' unpaid leave Apr 6–May 22 with no FMLA designation/notice → interference (29 U.S.C. § 2615; 29 C.F.R. § 825.300). Client flags it only as "my cousin says thats a whole thing." Eligibility (1,250 hrs / 50-employee site) unverified — gap question, not assumption.
6. Hostile comments/evidence: supervisor "broken down guys" remarks + route reassignment after the doctor's note (animus/retaliation evidence; preserve).
7. Tenure internally inconsistent: narrative "been there like five years" vs. termination letter hire date **Aug 11, 2022** (~3 yrs 9 mo) — matters for FMLA hours math and credibility; flag, don't ignore.

**Deadlines to surface + compute:**
- **EEOC charge (ADA):** 300 days in deferral-state MN (42 U.S.C. § 2000e-5(e)(1) via § 12117(a)): from termination May 22, 2026 → **Mar 18, 2027**; from accommodation denial Apr 6, 2026 → **Jan 31, 2027** (discrete act, own clock — earlier date controls for that claim).
- **MHRA (Minn. Stat. § 363A.28 subd. 3):** 1 year: denial → **Apr 6, 2027**; termination → **May 22, 2027**.
- **Judge note (accuracy):** since **Oct 1, 2025** MDHR and EEOC no longer automatically cross-file — preserve both by filing with EACH (or MHRA direct suit). Systems relying on pre-2025 worksharing get this wrong.
- **FMLA:** 2 yrs (3 willful), 29 U.S.C. § 2617(c): interference ~Apr 6, 2026 → ~Apr 6, 2028 (not urgent; list, don't lead).
- **Contractual (NOT statutory — must be labeled as such):** severance signature due **Jul 21, 2026, 5:00pm** — 11 days out; the true near-term decision point. If signed, MHRA-release rescission window = 15 calendar days after signing (§ 363A.31); no equivalent statutory rescission for the ADA release.
- Distractor: "return badge within 5 business days" (May letter) — housekeeping, not a deadline; COBRA election window not yet triggered in materials (gap question).

**FOLIO-ish concepts:** Employment Discrimination, Disability Discrimination, Reasonable Accommodation, Interactive Process, Essential Functions, Wrongful Termination, EEOC Charge, MDHR Charge/MHRA, FMLA Interference, Severance Agreement, Release/Waiver of Claims, Rescission Rights, Comparator Evidence, Retaliation.

**Gap questions:** employer size + hours worked in the 12 months pre-leave (FMLA/ADA coverage); is "50 lbs regular basis" in the actual written job description (essential-function attack); other employees denied non-occupational light duty (pattern); any severance deadline extension requested (buy time to file EEOC first); UI status since May 22 (misconduct not at issue — should apply); written trail of Derek's comments/route changes (witnesses).

---

## elder-exploitation — Lorraine Pryzbylski (UAT-EE-022) · Ramsey Co. MN · "today" = Jul 6, 2026

**Issues that MUST be spotted:**
1. Financial exploitation of an elder by POA-holder son (named-ish): ~$19K depleted Jan–Jun 2026 (ATM ~$10,050 + $6,400 boat check + $3,000 self-transfers "caregiver pay" never agreed). Crime: Minn. Stat. § 609.2335; breach of attorney-in-fact duties: Minn. Stat. § 523.21 (liability/accounting § 523.21; judicial relief § 523.26).
2. **[GATE] POA revocation** — she can revoke at any time while competent (Minn. Stat. § 523.11 subd. 1: signed, dated writing; effective as to third parties on actual notice — must deliver written revocation to Dale AND Prairie Sky Bank immediately). She asks "can I undo that paper?" but doesn't know it's this simple or that bank notice is the operative step.
3. **[GATE] Self-dealing not authorized** — planted in the POA copy: the "may transfer my property directly to himself" election is BLANK. Under Minn. Stat. § 523.24 the statutory form authorizes self-gifting only if expressly elected → the $3,000 self-transfers (and arguably the boat) exceeded authority regardless of revocation. Also the notary block is defective/blank ("D. Pryzbylski" where the notary goes) → POA likely invalid ab initio (Minn. Stat. § 523.01 requires acknowledgment) — stretch credit for spotting either.
4. **[GATE] Vulnerable-adult reporting + new protective order** — report to MAARC (Minn. Stat. § 626.557; bank letter references its own reporting duty); and petition for an **Order for Protection Against Financial Exploitation of a Vulnerable Adult, Minn. Stat. § 609.2334** — ex parte temporary order available on "immediate and present danger of financial exploitation" (subd. 8; up to 14 days, one 14-day extension) — tailor-made to freeze the account drain and block the Jul 16 listing. Judge note: "vulnerable adult" status (§ 626.5572 subd. 21 / § 609.2334 subd. 1) is fact-dependent — age alone insufficient; her post-surgery care needs and POA reliance are the qualifying facts to develop, and the key must not assume it.
5. **[GATE] Domestic abuse / OFP** — Jun 14, 2026 wrist grab leaving photographed bruise + "you'll end up at Ridgeview" threat + ongoing fear in her own home: OFP under Minn. Stat. § 518B.01 (son = family/household member; ex parte available); HRO (Minn. Stat. § 609.748) as fallback. She frames it as shame, never as a protective-order basis.
6. House-sale threat: POA power (A) real property IS initialed → Dale may attempt to list/convey; revocation + recording notice + § 609.2334 relief before **Jul 16** signing appointment; homestead conveyance also generally requires the owner's signature (she should sign nothing).
7. Amount internally inconsistent: narrative "$14,000 gone" vs. Bev's summary math **$19,450** (ATM $10,050 + $6,400 + $3,000); summary itself admits some ATM may be legitimate groceries. System must reconcile/flag, not adopt either number.
8. Safety/confidentiality overlay: Dale intercepts mail, she's writing from neighbor Bev's computer — communications plan is itself an intake output (don't mail to the house).

**Deadlines to surface + compute:**
- **No statutory deadline drives this persona — urgency is factual.** Correct posture: act-now items (POA revocation + bank notice; § 609.2334 ex parte petition; MAARC report; OFP) sequenced before **Jul 16, 2026** (realtor "listing papers" appointment — 10 days out; practical, not statutory).
- Bank verification window: "within ten (10) business days" of Jun 26 letter ≈ **Jul 10–13, 2026** — practical (risk: unverified activity hold or, worse, verification by Dale); respond via counsel/branch visit without tipping Dale.
- **SOL (background, not urgent):** conversion/fiduciary claims 6 yrs (Minn. Stat. § 541.05); § 609.2334 petition has no limitations trigger planted.
- Distractor (must NOT be operative): POA signing date Dec 8, 2025 and statement dates are history, not deadlines; "10 business days" is the bank's ask, not a forfeiture.

**FOLIO-ish concepts:** Elder Law, Vulnerable Adult, Financial Exploitation, Power of Attorney, Revocation of POA, Fiduciary Duty/Self-Dealing, Accounting, Order for Protection (financial-exploitation, § 609.2334), Order for Protection (domestic abuse), Harassment Restraining Order, Adult Protective Services/MAARC Report, Conversion, Real Property/Homestead, Undue Influence, Elder Abuse (physical), Evidence Preservation (bruise photo, statements).

**Gap questions:** her current capacity/medications (competence to revoke and testify — also § 626.5572 status facts); does Dale have any ownership/beneficiary interest in the house or account (joint account? POD?); where do the original POA and any copies live (banks holding copies need revocation notice); is she safe at home tonight / alternative stay with Bev (safety plan precedes paperwork); does she want criminal referral or civil-only ("I don't want to put my son in jail" — remedy preferences shape strategy); pension survivor-benefit protections and whether direct deposits can be rerouted to a new account Dale can't touch.

---

### Cross-persona expected findings (pre-registered, for the judge)
Given the system map, expect these product gaps to surface as rubric findings:
- **Deadlines (RUB-INTAKE-08/09):** no deadline/SOL computation engine exists (`ActionItem.deadline` hardcoded None). Expect dates echoed at best, not computed. GATE risk on all 3 personas.
- **Plain language (RUB-INTAKE-10):** `LanguageAdapter._rewrite_text` is stubbed — expect professional-register memo, not 6th–8th grade.
- **Issue-spotting (RUB-INTAKE-01):** the real test — does LLM+FOLIO surface the *unspoken* GATE issues (habitability+retaliation / VAWA+U-visa / OFP) without practice-area binding?
