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
    7-14 days after issuance of the summons).
  - MN family/civil response: Minn. Gen. R. Prac. 303.03 (answer served within
    30 days of service of the petition).
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


# Ordered: more specific rules first (eviction window before generic served
# rules), so find_rule() returns the most appropriate match.
RULES: list[DeadlineRule] = [
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
    ),
    DeadlineRule(
        id="mn_family_response_30d",
        jurisdiction="MN",
        citation="Minn. Gen. R. Prac. 303.03 (answer due 30 days after service)",
        urgency="high",
        hedge_text=_VERIFY,
        applies=lambda ev, jur: (
            _is_mn(ev, jur) and ev.trigger in {"served", "service"}
        ),
        compute=lambda d, ev: d + timedelta(days=30),
        description="MN family/civil response due 30 days after service of process.",
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
    ),
    DeadlineRule(
        id="generic_notice_window",
        jurisdiction=None,
        citation=(
            "Cure/vacate period stated in your notice or lease "
            "(confirm the exact deadline printed on the notice)."
        ),
        urgency="high",
        hedge_text=_VERIFY,
        applies=lambda ev, jur: ev.trigger in {"notice_posted", "notice", "notice_served"},
        compute=lambda d, ev: d + timedelta(days=(ev.window_days or 14)),
        description=(
            "Generic notice date + N-day cure/vacate window "
            "(uses stated window_days, else defaults to 14)."
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
