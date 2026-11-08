"""Plain-language labels, headings, and de-duplication for memo deadlines.

The memo's deadline headings used to be the visitor's raw words ("march 3rd,
thats when the 14 day notice showed up taped to the door"). Headings now come
from structured fields -- a short label for the event type plus the normalized
date ("Notice to vacate — March 3, 2026") -- and the visitor's words, when
shown, sit in the body. Pure functions over primitives so ``schemas`` can use
them without an import cycle.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Protocol, TypeVar

# Ordered (keywords-all-present, label) pairs matched against event_type.
_TYPE_LABELS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("pay", "quit"), "Notice to pay rent or quit"),
    (("nonpayment",), "Notice to pay rent or quit"),
    (("notice", "vacate"), "Notice to vacate"),
    (("notice", "quit"), "Notice to quit"),
    (("notice", "cure"), "Notice to cure"),
    (("eviction", "summons"), "Eviction summons"),
    (("eviction", "hearing"), "Eviction hearing"),
    (("eviction", "notice"), "Eviction notice"),
    (("master", "calendar"), "Immigration court hearing"),
    (("removal", "hearing"), "Immigration court hearing"),
    (("asylum",), "U.S. entry (asylum one-year clock)"),
    (("custody",), "Custody papers"),
    (("dissolution",), "Divorce papers"),
    (("divorce",), "Divorce papers"),
    (("summons",), "Court summons"),
    (("hearing",), "Court hearing"),
    (("filing", "deadline"), "Filing deadline"),
    (("response", "deadline"), "Response deadline"),
    (("injury",), "Injury"),
)

_TRIGGER_LABELS = {
    "hearing": "Court hearing",
    "appearance": "Court appearance",
    "court_date": "Court date",
    "deadline": "Stated deadline",
    "served": "Papers served",
    "service": "Papers served",
    "summons": "Court summons",
    "notice_posted": "Notice posted",
    "notice": "Notice received",
    "notice_served": "Notice served",
    "filed": "Filing",
    "issued": "Document issued",
    "incident": "Incident",
    "entry": "Entry into the U.S.",
}

_FALLBACK_LABEL = "Time-sensitive item"


def deadline_label(event_type: str | None, trigger: str | None) -> str:
    """A short, human label for a deadline from its structured fields."""
    etype = (event_type or "").strip().lower()
    if etype:
        words = set(re.split(r"[^a-z0-9]+", etype)) - {""}
        for keywords, label in _TYPE_LABELS:
            if all(any(w.startswith(k) for w in words) for k in keywords):
                return label
    trig = (trigger or "").strip().lower()
    if trig in _TRIGGER_LABELS:
        return _TRIGGER_LABELS[trig]
    if etype:
        text = re.sub(r"[_\-]+", " ", etype).strip()
        return text[:1].upper() + text[1:]
    return _FALLBACK_LABEL


def format_long_date(iso: str | None) -> str | None:
    """'2026-03-03' -> 'March 3, 2026'; None or unparseable -> None."""
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return None
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def deadline_heading(
    event_type: str | None,
    trigger: str | None,
    trigger_date: str | None,
    computed_date: str | None,
) -> str:
    """Label plus the event's normalized date (trigger date, else computed date)."""
    label = deadline_label(event_type, trigger)
    when = format_long_date(trigger_date) or format_long_date(computed_date)
    return f"{label} — {when}" if when else label


class _DeadlineLike(Protocol):
    event_text: str
    event_type: str | None
    trigger: str | None
    trigger_date: str | None
    computed_date: str | None


D = TypeVar("D", bound=_DeadlineLike)


def _quote_key(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


# Labels that can name several different things on one day (two incidents on
# the same date are not necessarily the same incident).
_LOOSE_LABELS = {"incident", "injury", "filing", "document issued", _FALLBACK_LABEL.lower()}


def _same_event(a: _DeadlineLike, b: _DeadlineLike, label: str) -> bool:
    qa, qb = _quote_key(a.event_text), _quote_key(b.event_text)
    if qa and qb and (qa in qb or qb in qa):
        return True
    dated = bool(a.trigger_date or a.computed_date)
    return dated and label not in _LOOSE_LABELS


def dedupe_deadlines(deadlines: list[D]) -> list[D]:
    """Drop repeats of the same event on the same date, keeping the first.

    Callers sort by urgency first, so the most urgent copy survives. Items
    match when their label and dates agree and either the visitor's quoted
    words overlap or the label names one specific event (a hearing, a notice).
    """
    kept: dict[tuple, list[D]] = {}
    out: list[D] = []
    for d in deadlines:
        label = deadline_label(d.event_type, d.trigger).lower()
        key = (label, d.trigger_date, d.computed_date)
        bucket = kept.setdefault(key, [])
        if any(_same_event(prev, d, label) for prev in bucket):
            continue
        bucket.append(d)
        out.append(d)
    return out
