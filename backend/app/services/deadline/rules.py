"""Small, cited, human-reviewable deadline rule table (v1).

SCOPE (locked v1 "detect + hedge"): Minnesota + a tiny generic ruleset only.
Every rule is human-reviewed and carries a statutory/procedural citation. This
is deliberately NOT a comprehensive 50-state library -- events with no matching
rule are surfaced "detected + hedged, not computed".

Each rule computes a SINGLE estimated date from a trigger date via stdlib date
math (no `dateutil` dependency -- it is not installed in the venv). Weekend /
court-holiday roll-forward is intentionally NOT applied; the hedge instructs the
reader to confirm the exact date, which is where such adjustments land.

Citations (verify before relying):
  - MN eviction summons -> hearing window: Minn. Stat. § 504B.321 (hearing set
    7-14 days after issuance of the summons). A SELF-DATED MN eviction hearing
    (date printed on the summons) carries the same § 504B.321 citation.
  - MN nonpayment pre-eviction notice: Minn. Stat. § 504B.321, subd. 1a
    (14-day written notice before filing a nonpayment eviction, eff. 2024);
    other MN notice-to-quit periods: Minn. Stat. § 504B.135.
  - MN dissolution/family response: Minn. Stat. § 518.12 (respondent's answer
    served within 30 days of service of the petition). NOTE: the earlier
    attribution to Minn. Gen. R. Prac. 303.03 was WRONG — Rule 303 governs
    family-court motion-practice timing, not the answer deadline (BUG-24).
  - Asylum one-year filing deadline: INA § 208(a)(2)(B); 8 U.S.C.
    § 1158(a)(2)(B).
  - Generic notice/cure window: the period stated in the notice or lease.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from app.services.deadline.schemas import DeadlineEvent

# The universal hedge appended to (or forming) every rule's hedge text. Also the
# passthrough hedge for detected-but-not-computed events. Keep the exact phrase
# in sync with GENERIC_HEDGE in engine.py.
_VERIFY = "Estimated — confirm the exact date with the court or a lawyer."


def _add_years(d: date, years: int) -> date:
    """Add whole years to a date, clamping Feb 29 -> Feb 28 on non-leap years."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _is_mn(event: DeadlineEvent, jurisdiction: str | None) -> bool:
    hint = f"{event.jurisdiction_hint or ''} {jurisdiction or ''}".upper()
    return "MN" in hint or "MINNESOTA" in hint


def _text(event: DeadlineEvent) -> str:
    return f"{event.event_type} {event.raw_text}".lower()


@dataclass
class DeadlineRule:
    """A single cited, deterministic deadline rule.

    Attributes:
        id: Stable identifier persisted on the Deadline row.
        jurisdiction: Jurisdiction the rule is scoped to (None = generic).
        citation: Human-readable statutory / procedural citation.
        urgency: Baseline urgency ("high" | "medium" | "low").
        hedge_text: Rule-specific hedge (always contains the _VERIFY phrase).
        applies: Predicate over (event, jurisdiction).
        compute: (trigger_date, event) -> estimated date.
        description: Human note describing the rule.
    """

    id: str
    jurisdiction: str | None
    citation: str
    urgency: str
    hedge_text: str
    applies: Callable[[DeadlineEvent, str | None], bool]
    compute: Callable[[date, DeadlineEvent], date]
    description: str = ""
    # Practice-area domain(s) this rule is scoped to (round 7, BUG-32). None =
    # domain-agnostic (fires in any domain, e.g. an immigration hearing that is
    # self-evidently immigration by its own predicate). When set, the rule fires
    # only if its domain(s) intersect the domains INFERRED from the narrative
    # (see services/analysis/domain_classifier.py) — this is what stops the
    # MN-scoped family-response rule from force-firing on a wage-theft
    # termination, a UI determination, or a POA signing. The guard is enforced
    # only when the caller passes a classified domain set to find_rule /
    # compute_deadlines; passing None (e.g. unit tests exercising pure date math)
    # keeps the legacy "no restriction" behavior.
    domains: frozenset[str] | None = None
    # When a deadline computed by this rule has already LAPSED, this text routes
    # the client to the governing exception/fallback pathway (RUB-08, Damien r2
    # 2026-07-10: a lapsed deadline must be computed, flagged, AND routed to its
    # exception pathway with the governing primary source). The engine appends it
    # to the hedge only when the computed date is in the past. None = no
    # rule-specific lapsed pathway (the generic "ALREADY PASSED" warning stands).
    lapsed_exception: str | None = None


# Triggers whose date STARTS a clock rather than being the deadline itself. An
# event with one of these triggers must NEVER be treated as self-dated, even if
# its snippet mentions a hearing ("the summons says a hearing will be set") --
# otherwise the identity rules hijack the offset rules and tell the client
# their deadline was the day they were served (CE review finding, session 2).
_OFFSET_TRIGGERS = {
    "served",
    "service",
    "filed",
    "summons",
    "issued",
    "incident",
    "entry",
    "notice_posted",
    "notice",
    "notice_served",
}


def _is_self_dated(event: DeadlineEvent) -> bool:
    """True when the event's own stated date IS the operative deadline.

    A scheduled hearing / court appearance, or an explicitly stated
    response/filing deadline, needs no offset math: the date the client already
    gave you is the deadline. Without this, a verbatim "August 20, 2026 hearing"
    matched no rule and surfaced as "date unclear" (BUG-12).

    Decision order: trigger wins. A self-dated trigger -> True; an offset
    trigger (served/filed/entry/notice...) -> False regardless of keywords in
    the snippet; only an unknown/blank trigger falls through to the keyword
    heuristic.
    """
    if event.trigger in {"hearing", "deadline", "appearance", "court_date"}:
        return True
    if event.trigger in _OFFSET_TRIGGERS:
        return False
    text = _text(event)
    return any(
        kw in text
        for kw in (
            "hearing",
            "court date",
            "appearance",
            "master calendar",
            "filing deadline",
            "response due",
            "answer due",
        )
    )


def _is_immigration(event: DeadlineEvent) -> bool:
    text = _text(event)
    return any(
        kw in text
        for kw in (
            "removal",
            "immigration",
            "master calendar",
            "asylum",
            "eoir",
            "deportation",
            "notice to appear",
        )
    )


def _has_court_context(event: DeadlineEvent) -> bool:
    """True when a self-dated event is genuinely a COURT date (round 7, BUG-32).

    The generic ``stated_court_date`` identity rule used to fire on ANY self-dated
    event, which mislabeled a severance-signature deadline, a realtor listing
    appointment, and an agency-appeal date as "the court's own summons". Restrict
    it to events that actually mention a court/hearing so those non-litigation
    dates fall through to the passthrough hedge instead of being asserted as a
    court deadline with a fabricated court-order citation.
    """
    if event.trigger in {"hearing", "appearance", "court_date"}:
        return True
    text = _text(event)
    return any(
        kw in text
        for kw in (
            "hearing",
            "court",
            "summons",
            "trial",
            "judge",
            "docket",
            "arraign",
            "appearance",
            "petition",
        )
    )


# Ordered: more specific rules first (self-dated court dates, then eviction
# window before generic served rules), so find_rule() returns the most
# appropriate match.
RULES: list[DeadlineRule] = [
    DeadlineRule(
        id="immigration_hearing_date",
        jurisdiction="US",
        citation=(
            "The hearing date on your Notice to Appear / EOIR hearing notice "
            "(8 C.F.R. § 1003.18; INA § 239). Failure to appear can result in an "
            "in-absentia removal order."
        ),
        urgency="high",
        hedge_text=(
            "This is the hearing date printed on your immigration court notice — "
            "you must appear. " + _VERIFY
        ),
        applies=lambda ev, jur: _is_self_dated(ev) and _is_immigration(ev),
        compute=lambda d, ev: d,
        domains=frozenset({"immigration"}),
        description=(
            "Immigration-court hearing/appearance: the stated date IS the "
            "operative deadline (identity compute)."
        ),
        lapsed_exception=(
            "If this hearing date has already passed and you did not appear, you "
            "may have been ordered removed 'in absentia' (in your absence). That "
            "order can sometimes be REOPENED — for example if you never properly "
            "received the notice or exceptional circumstances prevented you from "
            "appearing (motion to reopen, INA § 240(b)(5)(C); 8 U.S.C. "
            "§ 1229a(b)(5)(C)). Contact an immigration lawyer immediately."
        ),
    ),
    DeadlineRule(
        id="mn_eviction_stated_hearing",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 504B.321 (Minnesota eviction summons/hearing "
            "procedure); the hearing date printed on your summons or hearing "
            "notice."
        ),
        urgency="high",
        hedge_text=(
            "This is the eviction hearing date printed on your court papers — "
            "you must appear; in Minnesota your defenses are raised at this "
            "hearing (there is no separate written answer deadline). " + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_self_dated(ev) and _is_mn(ev, jur) and "evict" in _text(ev)
        ),
        compute=lambda d, ev: d,
        domains=frozenset({"landlord_tenant"}),
        description=(
            "MN eviction hearing: the stated date IS the operative deadline "
            "(identity compute), cited to Minn. Stat. § 504B.321 — the statute "
            "governing the eviction summons/hearing window (RUB-09 strict "
            "primary-source gate, Damien r3 2026-07-10)."
        ),
        lapsed_exception=(
            "If this hearing date has already passed, contact the housing court "
            "immediately. If a judgment was entered against you, ask about a "
            "motion to vacate the judgment and about expungement of the eviction "
            "record (Minn. Stat. § 484.014) — missing the hearing does not always "
            "end your options."
        ),
    ),
    DeadlineRule(
        id="stated_court_date",
        jurisdiction=None,
        citation=(
            "The court's own summons, hearing notice, or scheduling order "
            "setting this date — a court's order or summons is the governing "
            "primary authority for a court-scheduled appearance (confirm the "
            "date against the document itself)."
        ),
        urgency="high",
        hedge_text=(
            "This is a date the court gave you directly (a hearing, court date, "
            "or stated deadline). " + _VERIFY
        ),
        # Round 7 (BUG-32): require genuine court context so a severance-signature
        # deadline, a realtor listing appointment, or an agency-appeal date is NOT
        # mislabeled as "the court's own summons" with a fabricated court-order
        # citation. Non-court self-dated events fall through to the passthrough
        # hedge (detected + "confirm the exact date", computed=False).
        applies=lambda ev, jur: _is_self_dated(ev) and _has_court_context(ev),
        compute=lambda d, ev: d,
        description=(
            "A stated hearing/court/response date is itself the operative "
            "deadline (identity compute); the governing primary authority is "
            "the court order/summons that set it. Fires only with genuine court "
            "context (round 7 BUG-32 guard)."
        ),
        lapsed_exception=(
            "If this date has already passed, contact the court right away — a "
            "default judgment or order may have been entered in your absence. "
            "Ask the court clerk (or a lawyer) whether you can move to vacate or "
            "reopen it; acting quickly matters."
        ),
    ),
    DeadlineRule(
        id="mn_eviction_hearing_window",
        jurisdiction="MN",
        citation="Minn. Stat. § 504B.321",
        urgency="high",
        hedge_text=(
            "Minnesota eviction hearings are typically held 7–14 days after the "
            "summons issues, so your hearing could be as early as this date. "
            + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and "evict" in _text(ev)
            and ev.trigger in {"served", "filed", "summons", "issued"}
        ),
        compute=lambda d, ev: d + timedelta(days=7),
        domains=frozenset({"landlord_tenant"}),
        description=(
            "MN eviction summons -> hearing: 7–14 day window; earliest edge "
            "(trigger + 7d) computed, full range flagged in hedge."
        ),
        lapsed_exception=(
            "If this hearing window has already passed, contact the housing "
            "court immediately. If a judgment was entered against you, ask about "
            "a motion to vacate the judgment and about expungement of the "
            "eviction record (Minn. Stat. § 484.014)."
        ),
    ),
    DeadlineRule(
        id="mn_family_response_30d",
        jurisdiction="MN",
        citation="Minn. Stat. § 518.12 (respondent's answer due 30 days after service of the petition)",
        urgency="high",
        hedge_text=(
            "In a Minnesota dissolution/family matter the answer is generally due "
            "30 days after you were served with the petition. " + _VERIFY
        ),
        # Round 7 (BUG-32): the original predicate fired on ANY MN served event,
        # so § 518.12 force-fired on employment terminations, UI determinations,
        # and POA signings. Now double-guarded: (1) domains={family} so the
        # narrative-inferred domain must be a family matter, AND (2) a family-
        # context text check so a bare "served" event in an unclassified path
        # still cannot be mislabeled a dissolution answer.
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and ev.trigger in {"served", "service"}
            and any(
                kw in _text(ev)
                for kw in (
                    "custody",
                    "dissolution",
                    "divorce",
                    "parenting",
                    "petition",
                    "family",
                    "marriage",
                    "child support",
                    "paternity",
                )
            )
        ),
        compute=lambda d, ev: d + timedelta(days=30),
        domains=frozenset({"family"}),
        description="MN dissolution/family response due 30 days after service of the petition (Minn. Stat. § 518.12).",
        lapsed_exception=(
            "If more than 30 days have passed since you were served and you have "
            "not answered, contact the court right away — a default could be "
            "entered against you. Ask about filing a late answer or moving to "
            "set aside a default (Minn. R. Civ. P. 60.02); courts can excuse a "
            "late response for good reason."
        ),
    ),
    DeadlineRule(
        id="asylum_one_year",
        jurisdiction="US",
        citation="INA § 208(a)(2)(B); 8 U.S.C. § 1158(a)(2)(B) (one-year filing deadline)",
        urgency="high",
        hedge_text=(
            "Asylum applications generally must be filed within one year of "
            "arrival in the United States. " + _VERIFY
        ),
        applies=lambda ev, jur: "asylum" in _text(ev),
        compute=lambda d, ev: _add_years(d, 1),
        domains=frozenset({"immigration"}),
        description="Asylum one-year filing deadline measured from date of entry.",
        lapsed_exception=(
            "Because this one-year asylum deadline appears to have already passed, "
            "you may still be able to apply if an EXCEPTION applies: 'changed "
            "circumstances' that materially affect eligibility, or 'extraordinary "
            "circumstances' that excuse the late filing (for example serious "
            "illness, or ineffective assistance / fraud by a notario or non-lawyer). "
            "This exception pathway is governed by INA § 208(a)(2)(D); "
            "8 U.S.C. § 1158(a)(2)(D). Ask an immigration lawyer whether one of these "
            "exceptions applies to you — the late deadline may not be the end of your "
            "asylum claim."
        ),
    ),
    DeadlineRule(
        id="mn_eviction_notice_window",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 504B.321, subd. 1a (14-day written notice required "
            "before an eviction action for nonpayment of rent); for other "
            "Minnesota notice-to-quit periods see Minn. Stat. § 504B.135. The "
            "period printed on your notice controls if longer."
        ),
        urgency="high",
        hedge_text=(
            "Minnesota requires a written notice period before a nonpayment "
            "eviction can be filed; the cure/vacate date is computed from the "
            "day the notice was given. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and not _is_immigration(ev)
            and ev.trigger in {"notice_posted", "notice", "notice_served"}
            and ("evict" in _text(ev) or "rent" in _text(ev) or "vacate" in _text(ev) or "quit" in _text(ev))
        ),
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 14)),
        domains=frozenset({"landlord_tenant"}),
        description=(
            "MN eviction/nonpayment notice: notice date + stated window (default "
            "14d per Minn. Stat. § 504B.321 subd. 1a), cited to the governing "
            "statute (RUB-09 strict primary-source gate, Damien r3 2026-07-10)."
        ),
        lapsed_exception=(
            "If this notice period has already passed, an eviction case may have "
            "been filed — but that is not the end: in Minnesota you can still "
            "raise your defenses at the eviction hearing (including paying what "
            "is owed to redeem in a nonpayment case, Minn. Stat. § 504B.291). If "
            "a judgment was already entered, ask about vacating it and about "
            "expungement (Minn. Stat. § 484.014)."
        ),
    ),
    # ------------------------------------------------------------------
    # Round 7 expansion domain-rule sets (D01 / BUG-34). Each rule is
    # domain-scoped (BUG-32 guard), carries its governing PRIMARY SOURCE cite
    # (Damien r3: an uncited computed deadline is a GATE fail), and routes a
    # lapsed date to its exception pathway (Damien r2). Human-reviewed; verify
    # cites before relying.
    # ------------------------------------------------------------------
    # -- consumer-debt --
    DeadlineRule(
        id="fdcpa_validation_30d",
        jurisdiction="US",
        citation=(
            "15 U.S.C. § 1692g(a)–(b) (FDCPA debt-validation period: 30 days "
            "from RECEIPT of the collector's initial written notice; a timely "
            "written dispute forces collection to cease until the debt is "
            "verified)."
        ),
        urgency="high",
        hedge_text=(
            "Under the federal Fair Debt Collection Practices Act you generally "
            "have 30 days from when you RECEIVED the collector's first letter to "
            "dispute or demand verification of the debt in writing (this window "
            "runs from the date you received the letter, not the date printed on "
            "it). A written dispute mailed in time forces the collector to stop "
            "until they verify the debt. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            ev.trigger in {"notice_posted", "notice", "notice_served", "received"}
            and not _is_immigration(ev)
            and any(
                kw in _text(ev)
                for kw in ("debt", "collect", "collection", "creditor", "owe", "validation")
            )
        ),
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 30)),
        domains=frozenset({"consumer_debt"}),
        description=(
            "FDCPA 30-day validation/dispute window measured from receipt of the "
            "collector's initial notice (15 U.S.C. § 1692g)."
        ),
        lapsed_exception=(
            "If more than 30 days have passed since you received the collection "
            "letter, you can STILL dispute the debt in writing at any time — you "
            "just lose the automatic pause on collection that a dispute within 30 "
            "days gives you (15 U.S.C. § 1692g(b)). You can also still demand "
            "verification and, if the debt is near or past its statute of "
            "limitations, raise that. Talk to a lawyer before paying anything."
        ),
    ),
    DeadlineRule(
        id="debt_sol_6yr_restart_trap",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 541.05, subd. 1(1) (6-year limitations period on a "
            "contract/credit-card debt); Minn. Stat. § 541.053 (a payment or "
            "written acknowledgment can restart the clock — but cannot revive a "
            "debt already time-barred)."
        ),
        urgency="high",
        hedge_text=(
            "In Minnesota a credit-card/contract debt generally becomes "
            "time-barred about 6 years after your last payment or default — after "
            "that, the collector can ask but cannot force you to pay. WARNING: "
            "making even a small payment (or admitting the debt in writing) BEFORE "
            "that date can RESTART the whole 6-year clock. Do NOT pay or promise "
            "anything until a lawyer confirms the exact limitations date. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            any(
                kw in _text(ev)
                for kw in (
                    "last payment",
                    "last paid",
                    "stopped paying",
                    "since august",
                    "default",
                    "charge-off",
                    "charge off",
                    "havent paid",
                    "haven't paid",
                    "old credit card",
                )
            )
        ),
        compute=lambda d, ev: _add_years(d, 6),
        domains=frozenset({"consumer_debt"}),
        description=(
            "Consumer-debt 6-year statute of limitations from last "
            "payment/default (Minn. Stat. § 541.05/.053); flags the restart trap."
        ),
        lapsed_exception=(
            "If this 6-year period has ALREADY passed, the debt is likely "
            "time-barred: the collector cannot win a lawsuit to force payment, and "
            "a NEW payment cannot revive a debt that is already time-barred "
            "(Minn. Stat. § 541.053). This is a powerful defense — do not restart "
            "the clock; get advice before responding."
        ),
    ),
    # -- wage-theft --
    DeadlineRule(
        id="mn_final_wage_penalty_181_13",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 181.13(a) (upon a discharged employee's demand, unpaid "
            "wages are due within 24 hours; a penalty of the employee's average "
            "daily wage accrues for each day the employer is in default, capped at "
            "15 days)."
        ),
        urgency="high",
        hedge_text=(
            "In Minnesota, once you were fired and DEMANDED your unpaid wages, the "
            "employer had to pay within 24 hours (Minn. Stat. § 181.13(a)). After "
            "that, a penalty equal to your average daily pay adds up for each day "
            "they don't pay — up to a maximum of 15 days. That penalty maxes out "
            "about 15 days after your demand, so waiting longer does not add more; "
            "make your written demand and file now. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and any(
                kw in _text(ev)
                for kw in ("wage", "paycheck", "final pay", "demand", "unpaid", "owed me", "owes me")
            )
        ),
        compute=lambda d, ev: d + timedelta(days=1),
        domains=frozenset({"wage_theft"}),
        description=(
            "MN final-wages prompt-payment penalty clock: wages due 24h after "
            "demand; penalty accrues daily, capped at 15 days (§ 181.13(a))."
        ),
        lapsed_exception=(
            "The 24-hour deadline for the employer to pay has passed, which means "
            "the § 181.13 penalty has been running — good for you, not bad: the "
            "penalty (up to 15 days of average pay) is likely fully accrued. Bring "
            "your hours record and the demand text to a lawyer or file a wage "
            "claim with the Minnesota DLI; nothing is lost by the deadline "
            "passing, but do not keep waiting."
        ),
    ),
    # -- benefits-denial (unemployment) --
    DeadlineRule(
        id="mn_ui_appeal_45d",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 268.101, subd. 2, and § 268.105 (appeal of a "
            "determination of ineligibility to an unemployment-law judge must be "
            "filed within 45 calendar days of the date the determination was "
            "SENT; the period runs from sending and generally cannot be extended)."
        ),
        urgency="high",
        hedge_text=(
            "Your unemployment denial can be appealed to a state unemployment-law "
            "judge — and this is separate from any employer/HR appeal. You "
            "generally have 45 calendar days from the date the determination was "
            "SENT to file (Minn. Stat. § 268.101, subd. 2; § 268.105). This clock "
            "runs from the mailing date and usually cannot be extended, so file "
            "the appeal right away. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and any(
                kw in _text(ev)
                for kw in ("determination", "ineligible", "unemployment", "misconduct", "benefit")
            )
        ),
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 45)),
        domains=frozenset({"benefits_denial"}),
        description=(
            "MN unemployment appeal window: determination sent + 45 calendar days "
            "(Minn. Stat. § 268.101 subd. 2 / § 268.105)."
        ),
        lapsed_exception=(
            "If the 45-day appeal window appears to have passed, do NOT assume it "
            "is hopeless: confirm the exact SENT date on the determination (the "
            "clock runs from sending, and the mailed date may be later than you "
            "think), and ask immediately about any good-cause exception. Contact "
            "a legal-aid or unemployment-law attorney the same day."
        ),
    ),
    # -- employment-discrimination --
    DeadlineRule(
        id="eeoc_charge_300d",
        jurisdiction="US",
        citation=(
            "42 U.S.C. § 2000e-5(e)(1), applied to ADA claims via 42 U.S.C. "
            "§ 12117(a) (in a deferral state such as Minnesota, an EEOC charge "
            "must be filed within 300 days of the discriminatory act; each "
            "discrete act — a denial of accommodation, a discharge — has its own "
            "clock)."
        ),
        urgency="high",
        hedge_text=(
            "To sue for disability discrimination under federal law (the ADA), you "
            "usually must first file a charge with the EEOC within 300 days of the "
            "discriminatory act in Minnesota (42 U.S.C. § 2000e-5(e)(1); "
            "§ 12117(a)). Each separate act — being denied an accommodation, being "
            "fired — starts its own 300-day clock, so the EARLIEST act controls "
            "for that claim. Note: since Oct. 1, 2025 the state (MDHR) and the "
            "EEOC no longer automatically cross-file, so protect BOTH by filing "
            "with each. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            any(
                kw in _text(ev)
                for kw in (
                    "fired",
                    "terminated",
                    "termination",
                    "discharge",
                    "accommodation",
                    "denied",
                    "denial",
                    "discriminat",
                    "let go",
                )
            )
        ),
        compute=lambda d, ev: d + timedelta(days=300),
        domains=frozenset({"employment_discrimination"}),
        description=(
            "EEOC charge deadline: discriminatory act + 300 days in a deferral "
            "state (42 U.S.C. § 2000e-5(e)(1) via § 12117(a))."
        ),
        lapsed_exception=(
            "If 300 days appear to have passed since this act, you may still have "
            "options: a MORE RECENT discrete act (e.g. the termination itself) may "
            "have its own live clock, and the Minnesota Human Rights Act gives a "
            "separate 1-year window (Minn. Stat. § 363A.28, subd. 3). See an "
            "employment lawyer right away to preserve whatever remains."
        ),
    ),
    # -- elder-exploitation: no STATUTORY deadline drives this persona; urgency
    #    is factual (POA revocation, § 609.2334 ex parte petition, MAARC report,
    #    OFP — all surfaced as doctrine probes, not computed deadlines). The
    #    background conversion/fiduciary SOL is 6 years; we compute it only when
    #    an exploitation event carries a date so a stale claim is flagged, never
    #    to manufacture urgency from the realtor/bank distractor dates.
    DeadlineRule(
        id="mn_fiduciary_conversion_sol_6yr",
        jurisdiction="MN",
        citation=(
            "Minn. Stat. § 541.05, subd. 1 (6-year limitations period for "
            "conversion and breach of fiduciary duty, e.g. by an attorney-in-fact "
            "under a power of attorney)."
        ),
        urgency="medium",
        hedge_text=(
            "Claims to recover money taken by misuse of a power of attorney "
            "(conversion, breach of fiduciary duty) generally must be brought "
            "within 6 years in Minnesota (Minn. Stat. § 541.05). This is "
            "background timing — the urgent steps here are factual (revoking the "
            "power of attorney and notifying the bank, seeking a protective "
            "order), not this limitations date. " + _VERIFY
        ),
        applies=lambda ev, jur: (
            _is_mn(ev, jur)
            and any(
                kw in _text(ev)
                for kw in ("power of attorney", "poa", "attorney-in-fact", "exploitation", "self-transfer", "caregiver pay")
            )
        ),
        compute=lambda d, ev: _add_years(d, 6),
        domains=frozenset({"elder_exploitation"}),
        description=(
            "Elder financial-exploitation / fiduciary conversion SOL: 6 years "
            "(Minn. Stat. § 541.05) — background, non-urgent."
        ),
        lapsed_exception=(
            "Even if some of the oldest transfers fall outside the 6-year window, "
            "more recent ones are still within it, and criminal financial-"
            "exploitation and protective-order remedies do not depend on this "
            "civil limitations date. Get advice promptly."
        ),
    ),
    DeadlineRule(
        id="generic_notice_window",
        jurisdiction=None,
        citation=(
            "The cure/vacate period stated in your written notice or lease — the "
            "notice/lease term is the operative source of this period (confirm "
            "the exact deadline printed on the notice; your state's "
            "landlord-tenant statute governs the minimum period)."
        ),
        urgency="high",
        hedge_text=_VERIFY,
        # An immigration hearing letter / NTA is NOT a cure-window notice — a
        # fabricated "cure/vacate" deadline on an immigration matter is a wrong
        # deadline (RUB-09 0/GATE). Immigration events never take this rule.
        # Round 7 (BUG-32): scope to landlord_tenant so a debt-collection letter,
        # a bank "unusual activity" letter, or an agency notice never receives a
        # fabricated 14-day "cure/vacate" window citing "notice or lease". A
        # collection/benefits/employment notice now falls through to passthrough
        # (or to its own domain rule) rather than being force-fit as a tenancy
        # cure period.
        applies=lambda ev, jur: (
            ev.trigger in {"notice_posted", "notice", "notice_served"}
            and not _is_immigration(ev)
        ),
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 14)),
        domains=frozenset({"landlord_tenant"}),
        description=(
            "Generic notice date + N-day cure/vacate window "
            "(uses stated window_days, else defaults to 14); scoped to "
            "landlord_tenant (round 7 BUG-32 guard)."
        ),
        lapsed_exception=(
            "If this notice period has already passed, act now rather than "
            "assume it is over: depending on your state you may still be able to "
            "cure, raise defenses at any hearing, or ask the court to vacate a "
            "judgment entered against you. Contact the court or a lawyer "
            "immediately."
        ),
    ),
]


def find_rule(
    event: DeadlineEvent,
    jurisdiction: str | None,
    domains: frozenset[str] | None = None,
) -> DeadlineRule | None:
    """Return the first rule whose predicate matches and whose domain is allowed.

    Args:
        event: The normalized deadline event.
        jurisdiction: Jurisdiction context (event hint wins inside predicates).
        domains: Practice-area domains inferred from the narrative (round 7,
            BUG-32). When None (e.g. pure date-math unit tests), no domain
            restriction is applied — legacy behavior. When a frozenset (possibly
            empty), a DOMAIN-SCOPED rule fires only if its ``domains`` intersect
            this set; domain-agnostic rules (``rule.domains is None``) always
            pass the domain guard.
    """
    for rule in RULES:
        try:
            if not rule.applies(event, jurisdiction):
                continue
            if domains is not None and rule.domains is not None and not (rule.domains & domains):
                # Rule matched on facts but is scoped to a different practice
                # area than the narrative raises -> skip (cross-domain guard).
                continue
            return rule
        except Exception:  # pragma: no cover - defensive; a bad predicate must not crash
            continue
    return None
