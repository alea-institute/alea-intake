"""Reference-date anchoring for dates a visitor gave without a year.

Visitors write "march 3rd" or "april 1", not "March 3, 2026". The extraction
model has to pick a year, and in live runs it drifted a year into the future
(a notice posted "march 3rd" in a story told in spring 2026 came back as
2027-03-03). These pure helpers anchor such dates to the intake's reference
date (the visitor's message date, falling back to today in UTC):

  - an event that already HAPPENED (a notice posted, papers served, an
    incident) cannot sit in the future, so it resolves to the most recent
    past occurrence;
  - a forward-looking date (a hearing or a stated deadline) may sit a few
    months ahead, but not further than ``FORWARD_WINDOW_DAYS``.

``anchor_event_date`` only ever moves a model-chosen date BACK by whole years,
and only when the visitor's own words state no year. A date the visitor gave
with a year is never touched, and a past date is never pushed forward (a story
told about last winter keeps its winter).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

# How far ahead a yearless hearing/deadline date may plausibly fall.
FORWARD_WINDOW_DAYS = 120
# Slack for a past event dated "today" or "tomorrow" across time zones.
PAST_EVENT_SLACK_DAYS = 2

# Triggers describing an act that has already happened when the visitor writes.
PAST_TRIGGERS = frozenset(
    {
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
)

_EXPLICIT_YEAR = re.compile(
    r"\b(?:19|20)\d{2}\b"  # 2026
    r"|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"  # 3/3/26, 03-03-2026
    r"|'\d{2}\b"  # march '26
)


def utc_today() -> date:
    """Today's date in UTC (the fallback reference date)."""
    return datetime.now(timezone.utc).date()


def reference_date_from(value: datetime | date | str | None) -> date:
    """Turn a stored timestamp into a reference date; naive values count as UTC."""
    if isinstance(value, str):  # some drivers return aggregates as text
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            value = None
    if value is None:
        return utc_today()
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.date()
    return value


def has_explicit_year(text: str | None) -> bool:
    """True when the visitor's own words state a year (or a full numeric date)."""
    return bool(text) and bool(_EXPLICIT_YEAR.search(text))


def _on(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:  # Feb 29 in a non-leap year
        return None


def resolve_yearless_date(
    month: int, day: int, reference: date, *, past_event: bool
) -> date:
    """Resolve a month/day with no year against ``reference``.

    Returns the latest occurrence that is not later than ``reference`` plus
    the allowed lead (a couple of days for past events, ``FORWARD_WINDOW_DAYS``
    for forward-looking dates). "march 3rd" against 2026-03-10 is 2026-03-03.
    """
    lead = PAST_EVENT_SLACK_DAYS if past_event else FORWARD_WINDOW_DAYS
    latest = reference + timedelta(days=lead)
    for year in range(reference.year + 1, reference.year - 9, -1):
        candidate = _on(year, month, day)
        if candidate is not None and candidate <= latest:
            return candidate
    raise ValueError(f"cannot resolve month={month} day={day}")


def anchor_event_date(
    model_date: date | None,
    raw_text: str | None,
    trigger: str | None,
    reference: date,
) -> date | None:
    """Correct a model-chosen year that drifted past the reference date.

    Only applies when ``raw_text`` states no year. Moves the date back by whole
    years when it falls later than the story allows; never moves it forward.
    """
    if model_date is None or has_explicit_year(raw_text):
        return model_date
    past_event = (trigger or "").strip().lower() in PAST_TRIGGERS
    try:
        resolved = resolve_yearless_date(
            model_date.month, model_date.day, reference, past_event=past_event
        )
    except ValueError:
        return model_date
    return resolved if resolved < model_date else model_date
