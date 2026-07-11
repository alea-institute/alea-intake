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
        id="defective_eviction_notice",
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
]


def run_probes(narrative_text: str) -> list[DoctrineProbe]:
    """Return every probe whose fact pattern the narrative fairly raises."""
    t = (narrative_text or "").lower()
    if not t.strip():
        return []
    out: list[DoctrineProbe] = []
    for p in PROBES:
        try:
            if p.applies(t):
                out.append(p)
        except Exception:  # pragma: no cover — a bad predicate must not crash
            continue
    return out
