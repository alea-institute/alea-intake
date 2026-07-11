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
        applies=lambda ev, jur: _is_self_dated(ev),
        compute=lambda d, ev: d,
        description=(
            "A stated hearing/court/response date is itself the operative "
            "deadline (identity compute); the governing primary authority is "
            "the court order/summons that set it."
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
        applies=lambda ev, jur: (
            _is_mn(ev, jur) and ev.trigger in {"served", "service"}
        ),
        compute=lambda d, ev: d + timedelta(days=30),
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
        applies=lambda ev, jur: (
            ev.trigger in {"notice_posted", "notice", "notice_served"}
            and not _is_immigration(ev)
        ),
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 14)),
        description=(
            "Generic notice date + N-day cure/vacate window "
            "(uses stated window_days, else defaults to 14)."
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


def find_rule(event: DeadlineEvent, jurisdiction: str | None) -> DeadlineRule | None:
    """Return the first rule whose predicate matches, or None."""
    for rule in RULES:
        try:
            if rule.applies(event, jurisdiction):
                return rule
        except Exception:  # pragma: no cover - defensive; a bad predicate must not crash
            continue
    return None
