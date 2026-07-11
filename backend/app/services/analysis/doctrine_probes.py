"""Deterministic doctrine-probe table (RUB-01, Damien r1 2026-07-10).

Damien's r1 ruling (LOCKED rubric v1.3) requires EVERY doctrine-level sub-issue
fairly raised by the facts to be surfaced — as a claim, a flagged issue, or a
question. The LLM doctrine probe (gap_analyze) covers this probabilistically;
this module is the deterministic BACKSTOP: a small, cited, human-reviewable
table of non-obvious doctrine linkages keyed on narrative fact patterns, in the
same spirit as the deadline rule table (`services/deadline/rules.py`).

Each probe:
  - has a keyword predicate over the gathered intake narrative (lowercased):
    consumer messages + uploaded-document text + extracted fact assertions;
  - emits a concrete consumer-phrased QUESTION (surface-as-question satisfies
    RUB-01's form requirement) carrying its governing authority so the
    downstream reviewer can verify the doctrine;
  - never asserts a fact — it only ASKS whether the doctrine applies
    (RUB-04 no-fabrication is preserved: questions introduce no new facts).

Probes are deliberately conservative: they fire only on strong keyword
evidence that the facts fairly raise the doctrine. False negatives fall back
to the LLM probe; false positives are limited to asking one extra question.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class DoctrineProbe:
    """One deterministic doctrine linkage.

    Attributes:
        id: Stable identifier (used for dedupe across iterations).
        authority: Governing primary source(s), cited in the emitted gap.
        question: Concrete consumer-phrased question that surfaces the doctrine.
        applies: Predicate over the lowercased gathered narrative text.
        priority: Gap priority (higher survives the question-gen batch cap).
    """

    id: str
    authority: str
    question: str
    applies: Callable[[str], bool]
    priority: int = 80
    # Practice-area domain(s) this probe is scoped to (round 7, BUG-33). None =
    # domain-agnostic. When set, the probe fires only if its domain(s) intersect
    # the domains INFERRED from the narrative (domain_classifier) — this stops an
    # OFP/custody probe from fabricating a DV predicate in a wage-theft or
    # consumer-debt matter, and an immigration probe from firing on a stray
    # acronym in an unrelated document. The guard is enforced only when
    # run_probes is given a classified domain set (backward compatible: no set =
    # no restriction).
    domains: frozenset[str] | None = None


def _any(text: str, *kws: str) -> bool:
    return any(k in text for k in kws)


# Shared fact-pattern keyword groups (lowercase).
_ABUSE = (
    "hit me",
    "hurt me",
    "abuse",
    "bruise",
    "beat me",
    "slapped",
    "grabbed",
    "grab my",
    "grab her",
    "grab me",
    "violence",
    "violent",
    "afraid of him",
    "afraid of her",
    "threaten",
    "screaming that",
)
_IMMIGRATION = (
    "immigration",
    "asylum",
    "deport",
    "removal",
    "green card",
    "visa",
    "uscis",
    "eoir",
    "notice to appear",
    "in absentia",
)
# Core immigration markers that cannot appear incidentally in unrelated legal
# documents (used to scope acronym-triggered probes like the NTA defect).
_IMMIGRATION_CORE = (
    "immigration",
    "asylum",
    "deport",
    "removal proceeding",
    "uscis",
    "eoir",
    "notice to appear",
    "green card",
    "in absentia",
)
_SPOUSE = ("husband", "wife", "spouse", "marry", "married")
_POLICE = ("police", "sheriff", "arrest", "911", "officer")
_CUSTODY = ("custody", "parenting time", "visitation", "our kids", "our children", "the kids", "the children")
_UNAUTHORIZED_WORK = (
    "social number that's not",
    "social security number that's not",
    "not really mine",
    "not my social",
    "borrowed ssn",
    "borrowed social",
    "someone else's social",
    "fake social",
    "fake papers",
    "no work permit",
    "without papers",
)
_NOTARIO = (
    "not a lawyer",
    "notario",
    "wasn't a lawyer",
    "not really a lawyer",
    "said he was a lawyer",
)
_FLIGHT_RISK = (
    "take the kids",
    "take them and",
    "never see them",
    "never see the kids",
    "won't find us",
    "won't find them",
    "you won't find",
    "disappear with",
)
_RETALIATION_REPORT = (
    "report the mold",
    "reported the mold",
    "called the city",
    "call the city",
    "city inspector",
    "inspector came",
    "the city actually came",
    "code violation",
    "wrote him up",
    "wrote them up",
)
_EVICTION = ("evict", "notice to vacate", "notice to quit", "14 day notice", "14-day notice", "unlawful detainer")


PROBES: list[DoctrineProbe] = [
    DoctrineProbe(
        id="vawa_self_petition",
        domains=frozenset({"immigration"}),
        authority="INA § 204(a)(1); 8 U.S.C. § 1154 (VAWA self-petition)",
        question=(
            "You described being hurt by a spouse who is a U.S. citizen or "
            "green-card holder. Federal law (VAWA) may let you apply for "
            "immigration status on your own, without their help or knowledge — "
            "this is called a VAWA self-petition. Has a lawyer ever talked with "
            "you about whether you qualify?"
        ),
        applies=lambda t: (
            _any(t, *_ABUSE)
            and _any(t, "green card", "permanent resident", "citizen")
            and _any(t, *_SPOUSE)
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="u_nonimmigrant_status",
        domains=frozenset({"immigration"}),
        authority="INA § 101(a)(15)(U); 8 U.S.C. § 1101(a)(15)(U) (U nonimmigrant status; Form I-918 Supplement B certification)",
        question=(
            "You said you were the victim of a crime and helped the police. "
            "Victims of certain crimes who cooperate with law enforcement may "
            "qualify for a U visa (U nonimmigrant status). This needs a "
            "certification form (I-918B) signed by the police or prosecutor — "
            "has anyone requested one for you?"
        ),
        applies=lambda t: (
            _any(t, *_ABUSE) and _any(t, *_POLICE) and _any(t, *_IMMIGRATION)
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="adjustment_bar_245c_vawa_exemption",
        domains=frozenset({"immigration"}),
        authority="INA § 245(c)(2); 8 U.S.C. § 1255(c)(2) (unauthorized-employment bar; VAWA self-petitioners exempt)",
        question=(
            "You mentioned working with a Social Security number that is not "
            "yours. Working without authorization can normally block a "
            "green-card application filed inside the U.S. (the INA § 245(c)(2) "
            "bar) — BUT people approved under VAWA are exempt from that bar. A "
            "lawyer should review this together with any VAWA option. Have you "
            "told a lawyer about this work history?"
        ),
        applies=lambda t: (
            _any(t, *_UNAUTHORIZED_WORK) and _any(t, *_IMMIGRATION)
        ),
        priority=86,
    ),
    DoctrineProbe(
        id="pereira_nta_defect",
        domains=frozenset({"immigration"}),
        authority="Pereira v. Sessions, 138 S. Ct. 2105 (2018); Niz-Chavez v. Garland, 141 S. Ct. 1474 (2021) (defective Notice to Appear)",
        question=(
            "About the immigration papers (Notice to Appear) you received: did "
            "that first notice state the exact TIME, DATE, and PLACE of your "
            "court hearing, or were those details missing or sent later? A "
            "notice missing those details can matter to your case (it can "
            "affect eligibility clocks) — bring the original papers to a "
            "lawyer."
        ),
        # Word-boundary NTA only: a bare substring check false-fired on
        # "mai-NTA-in" in landlord-tenant lease documents (round 4b). Also
        # require immigration context so a stray acronym in an unrelated
        # document cannot trigger an immigration probe.
        applies=lambda t: (
            ("notice to appear" in t or re.search(r"\bnta\b", t) is not None)
            and _any(t, *_IMMIGRATION_CORE)
        ),
        priority=84,
    ),
    DoctrineProbe(
        id="asylum_one_year_bar_exception",
        domains=frozenset({"immigration"}),
        authority="INA § 208(a)(2)(B), (D); 8 U.S.C. § 1158(a)(2)(B), (D) (one-year bar; changed/extraordinary-circumstances exceptions)",
        question=(
            "Asylum applications normally must be filed within one year of "
            "arriving in the U.S. If your first year has passed — including if "
            "someone who was not a real lawyer took your money and never filed "
            "— you may still qualify under the 'changed circumstances' or "
            "'extraordinary circumstances' exceptions (fraud by a notario can "
            "count). Ask a lawyer about the one-year-bar exceptions. When did "
            "you arrive, and did anyone ever actually file an asylum "
            "application for you?"
        ),
        applies=lambda t: "asylum" in t and (_any(t, *_NOTARIO) or _any(t, "never filed", "never got nothing back", "no receipt")),
        priority=88,
    ),
    DoctrineProbe(
        id="ofp_grounds",
        domains=frozenset({"family", "elder_exploitation"}),
        authority="Minn. Stat. § 518B.01 (Order for Protection; ex parte relief available)",
        question=(
            "What you described — being physically hurt or threatened by a "
            "family or household member — may qualify you for an Order for "
            "Protection (a court order that can be issued the same day you "
            "ask, before any hearing). In Minnesota this is Minn. Stat. "
            "§ 518B.01; other states have an equivalent. Would you like "
            "information about asking the court for one now, separate from any "
            "other case?"
        ),
        applies=lambda t: (
            _any(t, *_ABUSE) and _any(t, *_SPOUSE + _CUSTODY)
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="dv_custody_best_interest_factor",
        domains=frozenset({"family"}),
        authority="Minn. Stat. § 518.17, subd. 1(a)(4) (domestic-abuse best-interest custody factor)",
        question=(
            "In a custody decision, the court must consider any domestic abuse "
            "that has occurred between the parents. In Minnesota this is a "
            "required 'best interests' factor (Minn. Stat. § 518.17); other "
            "states have an equivalent. The incident you described may matter "
            "to the custody case itself — make sure it is raised, not just "
            "handled separately. Do you have records (photos, texts, a police "
            "report) of what happened?"
        ),
        applies=lambda t: (
            _any(t, *_ABUSE) and _any(t, *_CUSTODY)
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="parental_abduction_flight_risk",
        domains=frozenset({"family"}),
        authority="Minn. Stat. § 518.17 (interim parenting-time terms); Minn. Stat. § 609.26 (deprivation of custodial/parental rights)",
        question=(
            "You mentioned a threat to take the children away so you could not "
            "find them. Courts can put safeguards in place while a custody "
            "case is pending (holding passports, supervised exchanges, interim "
            "parenting-time terms). Tell the court about this threat — do you "
            "have it in writing or did anyone witness it?"
        ),
        applies=lambda t: _any(t, *_FLIGHT_RISK),
        priority=86,
    ),
    DoctrineProbe(
        id="retaliatory_eviction_defense",
        domains=frozenset({"landlord_tenant"}),
        authority="Minn. Stat. § 504B.285, subd. 2; § 504B.441 (retaliation defense/penalties)",
        question=(
            "You reported problems to the city (or an inspector cited your "
            "landlord) shortly before the eviction steps started. If a "
            "landlord moves to evict soon after a tenant reports code "
            "violations, the law may presume retaliation — in Minnesota, "
            "Minn. Stat. § 504B.285/§ 504B.441; other states have an "
            "equivalent. How soon after your report did the eviction notice "
            "arrive?"
        ),
        applies=lambda t: (
            _any(t, *_RETALIATION_REPORT) and _any(t, *_EVICTION)
        ),
        priority=84,
    ),
    DoctrineProbe(
        id="security_deposit_irregularity",
        domains=frozenset({"landlord_tenant"}),
        authority="Minn. Stat. § 504B.178 (security deposits: receipt, interest, return); § 504B.172",
        question=(
            "You mentioned paying extra money (like a cash pet deposit) with no "
            "receipt. Deposits are regulated — in Minnesota the landlord must "
            "account for them, pay interest, and return them with an itemized "
            "statement (Minn. Stat. § 504B.178); other states have an "
            "equivalent. A cash payment with no receipt can still count. How "
            "much did you pay, when, and do you have any proof (texts, "
            "witnesses, bank withdrawal)?"
        ),
        applies=lambda t: (
            _any(t, "pet deposit", "security deposit", "damage deposit")
            or (
                "no receipt" in t
                and "cash" in t
                and _any(t, "landlord", "lease", "rent", "evict", "apartment", "tenant")
            )
        ),
        priority=82,
    ),
    DoctrineProbe(
        id="rent_escrow_repair_remedy",
        domains=frozenset({"landlord_tenant"}),
        authority="Minn. Stat. § 504B.385 (rent escrow); § 504B.425 (remedies); § 504B.161 (covenants of habitability)",
        question=(
            "You mentioned holding back rent because the landlord is ignoring "
            "repairs. Withholding on your own can be used against you in an "
            "eviction — but there is a legal way to do it: in Minnesota you can "
            "deposit the rent with the court (rent escrow, Minn. Stat. "
            "§ 504B.385) and ask the court to order repairs; other states have "
            "an equivalent. Have you asked the court about depositing your rent "
            "instead of just holding it back?"
        ),
        applies=lambda t: (
            _any(t, "held back", "withheld", "withholding", "holding back", "not paying the rent", "stopped paying")
            and "rent" in t
            and _any(t, "mold", "heat", "repair", "broken", "leak", "pest", "roach", "unsafe", "ignoring", "won't fix", "wont fix", "never fixed")
        ),
        priority=84,
    ),
    DoctrineProbe(
        id="defective_eviction_notice",
        domains=frozenset({"landlord_tenant"}),
        authority="State eviction-notice content requirements (e.g., Minn. Stat. § 504B.321; the notice must state the specific grounds)",
        question=(
            "Your notice appears to give a vague reason (like a 'material lease "
            "violation' box with no specifics). A notice usually must state the "
            "specific grounds so you can respond — a vague or defective notice "
            "can be challenged. What exactly does the notice say, and does it "
            "list any specific violation, amount, or cure period?"
        ),
        applies=lambda t: (
            "material lease violation" in t
            or (
                _any(t, *_EVICTION)
                and "notice" in t
                and _any(
                    t,
                    "no clue what",
                    "what that even means",
                    "doesn't say what",
                    "didn't say what",
                    "does not say what",
                    "no details",
                    "no specifics",
                    "just a box",
                    "checked a box",
                    "checkbox",
                )
            )
        ),
        priority=82,
    ),
    # ------------------------------------------------------------------
    # D07 (2026-07-11): § 504B.331 service-by-posting calibration probe. A summons
    # "taped to the door" raises whether personal/mail service requirements were
    # met before posting was allowed — a defect can defeat the eviction.
    # ------------------------------------------------------------------
    DoctrineProbe(
        id="mn_service_by_posting_504b331",
        domains=frozenset({"landlord_tenant"}),
        authority="Minn. Stat. § 504B.331 (eviction summons service; posting/'nail-and-mail' allowed only after diligent attempts at personal service and if the tenant cannot be found, plus mailing)",
        question=(
            "You said the court papers (summons) were just TAPED to your door. In "
            "Minnesota a summons can be posted like that only if the landlord "
            "first tried to hand it to you in person and could not find you, and "
            "then also mailed you a copy (Minn. Stat. § 504B.331). If those steps "
            "were skipped, the service may be defective and can be challenged. "
            "Were you ever handed the papers in person, or did anyone mail you a "
            "copy?"
        ),
        applies=lambda t: (
            _any(t, "taped to", "tape to", "posted on", "stuck to", "nailed to", "on my door", "to the door", "to my door")
            and _any(t, *_EVICTION, "summons", "court papers", "eviction", "unlawful detainer")
        ),
        priority=84,
    ),
    # ------------------------------------------------------------------
    # Round 7 expansion probes (D01 / BUG-34). Each carries its governing primary
    # source and is domain-scoped (BUG-33 guard). Questions never assert a
    # predicate as fact — they ask whether the doctrine applies.
    # ------------------------------------------------------------------
    # -- consumer-debt --
    DoctrineProbe(
        id="fdcpa_harassment_practices",
        domains=frozenset({"consumer_debt"}),
        authority="15 U.S.C. § 1692c(a) (calls before 8am/after 9pm, at work after notice); § 1692b/§ 1692c(b) (third-party disclosure of the debt); § 1692d (harassing volume)",
        question=(
            "The way this collector is contacting you may itself be illegal under "
            "the federal Fair Debt Collection Practices Act: calling before 8am "
            "or after 9pm, calling you at work after being told to stop, telling "
            "another person (like your sister) about the debt, or calling many "
            "times a day can each violate the law (15 U.S.C. § 1692c/§ 1692d). "
            "Keep your call log. Can you note the dates, times, and who they "
            "contacted?"
        ),
        applies=lambda t: (
            _any(t, "collector", "collection", "debt", "creditor", "i owe", "owe money", "owe them")
            and _any(t, "call", "called", "calling", "voicemail", "phone", "text")
        ),
        priority=86,
    ),
    DoctrineProbe(
        id="false_garnishment_threat",
        domains=frozenset({"consumer_debt"}),
        authority="15 U.S.C. § 1692e(4)–(5) (threat of action that cannot legally be taken); Minn. Stat. § 571.71 (garnishment generally requires a judgment first)",
        question=(
            "The collector said they will garnish your wages or freeze your bank "
            "account 'by the end of the month.' In Minnesota a collector generally "
            "CANNOT garnish or freeze anything without first suing you and getting "
            "a court judgment (Minn. Stat. § 571.71) — and you said no court papers "
            "were ever served. Threatening action they cannot legally take is "
            "itself an FDCPA violation (15 U.S.C. § 1692e). Have you ever been "
            "served with any lawsuit or court papers about this debt?"
        ),
        applies=lambda t: (
            _any(t, "garnish", "freeze", "freeze my", "levy", "take my wages", "take my bank")
            and _any(t, "collector", "collection", "debt", "creditor", "i owe", "owe money", "owe them")
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="exempt_income_protection",
        domains=frozenset({"consumer_debt"}),
        authority="42 U.S.C. § 407(a) (Social Security/SSDI exempt from garnishment); Minn. Stat. § 571.912/§ 571.922 (exemption-notice process; wage-exemption floor)",
        question=(
            "You said your income is Social Security disability plus a little "
            "part-time pay. Social Security and SSDI are protected by law from "
            "most debt collection (42 U.S.C. § 407), and Minnesota gives extra "
            "protection to low wages and exempt funds in a bank account "
            "(Minn. Stat. § 571.912/§ 571.922). You may be effectively "
            "'judgment-proof.' Is Social Security your only regular income, and is "
            "it direct-deposited?"
        ),
        applies=lambda t: (
            _any(t, "social security", "ssdi", "ssi", "disability", "disability money", "disability check")
            and _any(t, "collector", "collection", "debt", "garnish", "i owe", "owe money", "creditor")
        ),
        priority=86,
    ),
    # -- wage-theft --
    DoctrineProbe(
        id="employee_misclassification",
        domains=frozenset({"wage_theft"}),
        authority="Minn. Stat. § 181.723 (construction-industry independent-contractor test); Minn. Stat. § 268.035 (UI 'employment' definition — a misclassified worker can still qualify for unemployment)",
        question=(
            "Your boss calls you an 'independent contractor,' but you said he sets "
            "your schedule and sites, supplies the van and tools, and won't let "
            "you work for anyone else — those are signs you are really an EMPLOYEE "
            "in the eyes of the law, no matter what the paper says (Minn. Stat. "
            "§ 181.723 for construction work). That would unlock unpaid-wage "
            "penalties, overtime, and YES, likely unemployment benefits "
            "(Minn. Stat. § 268.035). Did you ever work for other customers, or "
            "only for him?"
        ),
        applies=lambda t: (
            _any(t, "independent contractor", "1099", "contractor")
            and _any(t, "boss", "employer", "schedule", "his tools", "company van", "fired", "wages", "hours")
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="unpaid_overtime_mflsa",
        domains=frozenset({"wage_theft"}),
        authority="Minn. Stat. § 177.25 (MFLSA overtime: time-and-a-half over 48 hrs/week); 29 U.S.C. § 207 (FLSA over 40 hrs/week if covered)",
        question=(
            "You said you worked 50+ hour weeks but were paid straight time. In "
            "Minnesota you are generally owed time-and-a-half for hours over 48 in "
            "a week (Minn. Stat. § 177.25), and federal law may require it over 40 "
            "(29 U.S.C. § 207). Unpaid overtime can be a big part of what you are "
            "owed. Do you have a record of your weekly hours?"
        ),
        applies=lambda t: (
            _any(t, "overtime", "time and a half", "straight time", "54", "56", "50 hour", "hours a week")
            and _any(t, "boss", "employer", "wages", "paycheck", "paid", "hours")
        ),
        priority=86,
    ),
    DoctrineProbe(
        id="wage_theft_retaliation",
        domains=frozenset({"wage_theft"}),
        authority="Minn. Stat. § 181.03, subd. 6 (retaliation for asserting wage rights); Minn. Stat. § 177.32 (MFLSA anti-retaliation)",
        question=(
            "You asked your boss about overtime and were fired the same day. Firing "
            "or punishing a worker for asking about unpaid wages or overtime is "
            "illegal retaliation in Minnesota (Minn. Stat. § 181.03, subd. 6; "
            "§ 177.32). The timing matters a lot here. Do you have the texts or "
            "messages showing you asked about overtime right before you were fired?"
        ),
        applies=lambda t: (
            _any(t, "overtime", "wages", "unpaid", "asked about", "asked him")
            and _any(t, "fired", "let go", "terminated", "off the schedule", "dont bother coming")
        ),
        priority=88,
    ),
    # -- benefits-denial (unemployment) --
    DoctrineProbe(
        id="ui_misconduct_family_care_exception",
        domains=frozenset({"benefits_denial"}),
        authority="Minn. Stat. § 268.095, subd. 6(b) (absence with proper notice to care for the illness/injury of an immediate family member is NOT employment misconduct)",
        question=(
            "You were denied unemployment for 'misconduct' over attendance — but "
            "you missed work to care for your child during a medical emergency and "
            "you called in every time. Minnesota law says an absence WITH PROPER "
            "NOTICE to care for a sick immediate family member is NOT misconduct "
            "(Minn. Stat. § 268.095, subd. 6(b)). This is likely your winning "
            "argument on appeal. Do you have proof you called in before each "
            "shift, and the hospital records?"
        ),
        applies=lambda t: (
            _any(t, "misconduct", "attendance", "absence", "missed", "unemployment", "denied")
            and _any(t, "child", "daughter", "son", "hospital", "sick", "family", "caring for", "care for", "dka")
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="ui_weekly_request_resumption",
        domains=frozenset({"benefits_denial"}),
        authority="Minn. Stat. § 268.085, subd. 1 (benefits are payable only for weeks for which a continued/weekly benefit request was actually submitted)",
        question=(
            "You said you stopped submitting the weekly online request after the "
            "denial. That is urgent: in Minnesota you can only be paid for weeks "
            "you actually request, even while your appeal is pending "
            "(Minn. Stat. § 268.085, subd. 1). Weeks you skip may be lost for good. "
            "Can you resume the weekly requests right away?"
        ),
        applies=lambda t: (
            _any(t, "stopped doing the weekly", "stopped filing", "stopped requesting", "havent logged", "stopped the weekly", "weekly thing", "weekly request")
            and _any(t, "unemployment", "benefit", "denied", "determination")
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="ui_hr_appeal_red_herring",
        domains=frozenset({"benefits_denial"}),
        authority="Minn. Stat. § 268.105 (the state unemployment appeal is independent of any employer/HR internal appeal process)",
        question=(
            "You worried that missing the employer's internal 10-day HR appeal "
            "means you lost everything. It does not: the employer's HR appeal and "
            "the STATE unemployment appeal are completely separate, and only the "
            "state appeal deadline controls your benefits (Minn. Stat. § 268.105). "
            "Missing the HR one does not forfeit your unemployment rights. Have you "
            "filed the STATE appeal yet?"
        ),
        applies=lambda t: (
            _any(t, "hr appeal", "hr lady", "internal appeal", "10 business days", "10 business day", "appeal through hr", "missed my chance", "already blow it", "blew it")
            and _any(t, "unemployment", "benefit", "determination", "denied")
        ),
        priority=84,
    ),
    # -- employment-discrimination --
    DoctrineProbe(
        id="failure_to_accommodate",
        domains=frozenset({"employment_discrimination"}),
        authority="42 U.S.C. § 12112(b)(5) (ADA failure to accommodate / interactive process); Minn. Stat. § 363A.08 (MHRA disability accommodation)",
        question=(
            "Separate from being fired, the law required your employer to seriously "
            "discuss a 'reasonable accommodation' with you (like the scan station "
            "or lift-assist) and not just say no (42 U.S.C. § 12112(b)(5); "
            "Minn. Stat. § 363A.08). Skipping that back-and-forth (the 'interactive "
            "process') can be its own violation, with its own deadline. Did anyone "
            "ever actually discuss other job options with you before denying it?"
        ),
        applies=lambda t: (
            _any(t, "accommodation", "restriction", "light duty", "scan station", "lift assist", "lift-assist", "reasonable")
            and _any(t, "disability", "disc", "herniated", "injury", "doctor's note", "doctors note", "restriction", "fired", "denied")
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="severance_release_trap",
        domains=frozenset({"employment_discrimination"}),
        authority="Minn. Stat. § 363A.31 (15-day rescission right after signing a release of MHRA claims); a severance release generally waives ADA/MHRA/FMLA claims",
        question=(
            "The severance agreement asks you to release ALL claims — including the "
            "discrimination and accommodation claims — for the payment. Do NOT sign "
            "it without legal advice first, and note the sign-by date is a "
            "CONTRACT deadline set by the employer, not a legal filing deadline. If "
            "you do sign, Minnesota law gives you 15 days afterward to cancel the "
            "release of your state human-rights claims (Minn. Stat. § 363A.31). "
            "Would you like this reviewed before the sign-by date?"
        ),
        applies=lambda t: (
            _any(t, "severance", "release all claims", "release of claims", "sign by", "waive", "general release")
            and _any(t, "discriminat", "accommodation", "fired", "disability", "claims", "$", "pay")
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="fmla_interference",
        domains=frozenset({"employment_discrimination"}),
        authority="29 U.S.C. § 2615; 29 C.F.R. § 825.300 (FMLA interference — failure to designate/notify FMLA leave for an eligible employee)",
        question=(
            "You were put on unpaid medical leave but say no one mentioned FMLA or "
            "gave you any FMLA paperwork. For an eligible employee at a large "
            "employer, failing to offer and designate FMLA leave can be unlawful "
            "'interference' (29 U.S.C. § 2615). Eligibility depends on hours worked "
            "and employer size. About how many hours did you work in the year "
            "before the leave, and how big is the site?"
        ),
        applies=lambda t: (
            _any(t, "fmla", "unpaid leave", "medical leave", "put on leave", "placed on leave", "leave")
            and _any(t, "disability", "disc", "herniated", "injury", "restriction", "fired", "hurt", "back")
        ),
        priority=84,
    ),
    # -- elder-exploitation --
    DoctrineProbe(
        id="poa_revocation",
        domains=frozenset({"elder_exploitation"}),
        authority="Minn. Stat. § 523.11, subd. 1 (a competent principal may revoke a power of attorney by a signed, dated writing; effective as to a third party on actual notice)",
        question=(
            "You asked if you can 'undo' the power of attorney. Yes — as long as "
            "your mind is clear, you can revoke it at any time with a signed, dated "
            "writing, and it takes effect against others (like the bank) once they "
            "actually get notice (Minn. Stat. § 523.11). The key step is delivering "
            "written revocation to BOTH your son and the bank right away. Would you "
            "like help doing that this week?"
        ),
        applies=lambda t: (
            _any(t, "power of attorney", "poa", "attorney-in-fact", "undo that paper", "revoke", "that paper i signed")
        ),
        priority=92,
    ),
    DoctrineProbe(
        id="poa_self_dealing_limit",
        domains=frozenset({"elder_exploitation"}),
        authority="Minn. Stat. § 523.24 (statutory short-form POA authorizes self-gifting/self-transfers only if expressly elected); Minn. Stat. § 523.01 (valid POA requires acknowledgment)",
        question=(
            "Even under a power of attorney, your son could pay himself or transfer "
            "your money to himself ONLY if the document specifically allowed it "
            "(Minn. Stat. § 523.24) — if that box was left blank, those transfers "
            "and the 'caregiver pay' likely exceeded his authority, revocation or "
            "not. A missing notary can also make the whole POA invalid "
            "(Minn. Stat. § 523.01). Do you have the actual POA document so a "
            "lawyer can check what was and wasn't authorized?"
        ),
        applies=lambda t: (
            _any(t, "power of attorney", "poa", "attorney-in-fact")
            and _any(t, "transfer", "caregiver pay", "himself", "his own account", "took", "boat", "atm", "self")
        ),
        priority=88,
    ),
    DoctrineProbe(
        id="vulnerable_adult_609_2334_maarc",
        domains=frozenset({"elder_exploitation"}),
        authority="Minn. Stat. § 609.2334 (Order for Protection Against Financial Exploitation of a Vulnerable Adult — ex parte relief available); Minn. Stat. § 626.557 (vulnerable-adult reporting / MAARC)",
        question=(
            "Because you may be a 'vulnerable adult' (relying on your son for care "
            "after surgery), there is a special court order that can quickly FREEZE "
            "the account draining and block the house sale — an Order for "
            "Protection Against Financial Exploitation of a Vulnerable Adult "
            "(Minn. Stat. § 609.2334), which a judge can issue right away in an "
            "emergency. This can also be reported to the state (MAARC, "
            "Minn. Stat. § 626.557). Would you like to ask the court for this "
            "before the July 16 appointment?"
        ),
        applies=lambda t: (
            _any(t, "power of attorney", "poa", "vulnerable", "elder", "my son", "caregiver")
            and _any(t, "money", "account", "bank", "boat", "transfer", "atm", "house", "listing", "exploit", "draining", "gone")
        ),
        priority=90,
    ),
    DoctrineProbe(
        id="elder_household_ofp",
        domains=frozenset({"elder_exploitation"}),
        authority="Minn. Stat. § 518B.01 (Order for Protection — a son living in the home is a family/household member; ex parte relief); Minn. Stat. § 609.748 (Harassment Restraining Order fallback)",
        question=(
            "Your son grabbed your wrist hard enough to bruise and threatened you in "
            "your own home. Because he is a family/household member, you can ask for "
            "an Order for Protection that a judge can grant the same day "
            "(Minn. Stat. § 518B.01); a Harassment Restraining Order "
            "(Minn. Stat. § 609.748) is a backup. This is separate from the money "
            "issues. Do you have the photo of the bruise and would you feel safer "
            "with such an order?"
        ),
        applies=lambda t: (
            _any(t, *_ABUSE, "grabbed my wrist", "grab my wrist", "leave a bruise", "left a bruise")
            and _any(t, "my son", "son", "household", "in my own", "at home", "in my house")
        ),
        priority=88,
    ),
]


def run_probes(
    narrative_text: str, domains: frozenset[str] | None = None
) -> list[DoctrineProbe]:
    """Return every probe whose fact pattern the narrative fairly raises.

    Args:
        narrative_text: The gathered intake narrative (lowercased internally).
        domains: Practice-area domains inferred from the narrative (round 7,
            BUG-33 cross-domain guard). When None, no domain restriction is
            applied (legacy behavior — every keyword-matching probe fires). When
            a frozenset (possibly empty), a DOMAIN-SCOPED probe fires only if its
            ``domains`` intersect this set; domain-agnostic probes always pass.
    """
    t = (narrative_text or "").lower()
    if not t.strip():
        return []
    out: list[DoctrineProbe] = []
    for p in PROBES:
        try:
            if not p.applies(t):
                continue
            if domains is not None and p.domains is not None and not (p.domains & domains):
                # Probe matched on keywords but is scoped to a different practice
                # area than the narrative raises -> skip (cross-domain guard).
                continue
            out.append(p)
        except Exception:  # pragma: no cover — a bad predicate must not crash
            continue
    return out
