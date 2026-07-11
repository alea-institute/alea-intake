"""Pure, deterministic deadline computation engine (v1 "detect + hedge").

`compute_deadlines` takes normalized events + a jurisdiction + a reference
`today`, matches each event against the cited rule table (`rules.py`), and
produces `ComputedDeadline`s. No I/O, no LLM, no clock reads unless `today` is
omitted -- fully unit-testable.

Contract:
  - A rule match with a known trigger date -> computed=True with an estimated
    computed_date, rule_id and citation. If that date is already in the past
    relative to `today`, urgency is escalated to "lapsed" (SOL check).
  - No rule match (or no date) -> passthrough: computed=False, detected + hedged
    only. Every result carries hedge text.
"""

from __future__ import annotations

from datetime import date

from app.services.deadline.rules import find_rule
from app.services.deadline.schemas import ComputedDeadline, DeadlineEvent

# Universal hedge (kept in sync with rules._VERIFY).
GENERIC_HEDGE = "Estimated — confirm the exact date with the court or a lawyer."

# Urgency sort order (lower sorts first / more prominent).
_URGENCY_ORDER = {"lapsed": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


def compute_deadlines(
    events: list[DeadlineEvent],
    jurisdiction: str | None = None,
    today: date | None = None,
) -> list[ComputedDeadline]:
    """Compute deadlines for a list of detected events.

    Args:
        events: Normalized detected events (dates as ``datetime.date``).
        jurisdiction: Jurisdiction context for rule matching (event hint wins).
        today: Reference "now" for the lapsed-SOL check. Defaults to date.today().

    Returns:
        ComputedDeadlines sorted by urgency (lapsed/high first).
    """
    ref_today = today or date.today()
    out: list[ComputedDeadline] = []

    for ev in events:
        rule = find_rule(ev, jurisdiction)
        event_text = ev.raw_text or ev.event_type or "Time-sensitive event"
        jur = ev.jurisdiction_hint or jurisdiction

        if rule is not None and ev.date is not None:
            computed_date = rule.compute(ev.date, ev)
            lapsed = computed_date < ref_today
            urgency = "lapsed" if lapsed else rule.urgency
            hedge = rule.hedge_text
            if lapsed:
                hedge = (
                    f"WARNING: this deadline appears to have ALREADY PASSED as of "
                    f"{ref_today.isoformat()}. " + hedge
                )
                # RUB-08 (Damien r2 2026-07-10): a lapsed deadline must be routed
                # to its exception/fallback pathway, with the governing authority.
                if rule.lapsed_exception:
                    hedge = hedge + " " + rule.lapsed_exception
            out.append(
                ComputedDeadline(
                    event_text=event_text,
                    event_type=ev.event_type,
                    trigger=ev.trigger,
                    trigger_date=ev.date,
                    computed_date=computed_date,
                    rule_id=rule.id,
                    citation=rule.citation,
                    computed=True,
                    urgency=urgency,
                    hedge=hedge,
                    jurisdiction=jur,
                    window_days=ev.window_days,
                    source_message_id=ev.source_message_id,
                    source_start=ev.source_start,
                    source_end=ev.source_end,
                )
            )
        else:
            out.append(
                ComputedDeadline(
                    event_text=event_text,
                    event_type=ev.event_type,
                    trigger=ev.trigger,
                    trigger_date=ev.date,
                    computed_date=None,
                    rule_id=None,
                    citation=None,
                    computed=False,
                    urgency="unknown",
                    hedge=GENERIC_HEDGE,
                    jurisdiction=jur,
                    window_days=ev.window_days,
                    source_message_id=ev.source_message_id,
                    source_start=ev.source_start,
                    source_end=ev.source_end,
                )
            )

    out.sort(key=lambda d: _URGENCY_ORDER.get(d.urgency, 99))
    return out
