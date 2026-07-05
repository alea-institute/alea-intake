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

### Cross-persona expected findings (pre-registered, for the judge)
Given the system map, expect these product gaps to surface as rubric findings:
- **Deadlines (RUB-INTAKE-08/09):** no deadline/SOL computation engine exists (`ActionItem.deadline` hardcoded None). Expect dates echoed at best, not computed. GATE risk on all 3 personas.
- **Plain language (RUB-INTAKE-10):** `LanguageAdapter._rewrite_text` is stubbed — expect professional-register memo, not 6th–8th grade.
- **Issue-spotting (RUB-INTAKE-01):** the real test — does LLM+FOLIO surface the *unspoken* GATE issues (habitability+retaliation / VAWA+U-visa / OFP) without practice-area binding?
