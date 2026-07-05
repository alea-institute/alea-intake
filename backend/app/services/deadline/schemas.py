"""Data contracts for the deadline detection engine.

Two layers:
  - DeadlineEvent / ComputedDeadline: plain dataclasses used by the pure,
    deterministic engine (`engine.py`). Dates are ``datetime.date`` objects.
  - DeadlineEventSchema / DeadlineExtractionResult: Pydantic models for
    validating the (probabilistic) LLM event-extraction output before it is
    normalized into DeadlineEvent dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field


@dataclass
class DeadlineEvent:
    """A normalized time-sensitive event fed into the deterministic engine.

    Attributes:
        event_type: Coarse category, e.g. "eviction_summons", "custody_response",
            "notice_to_vacate", "asylum_entry", "removal_hearing".
        raw_text: Verbatim narrative snippet the event was detected from.
        trigger: The triggering act, e.g. "served", "notice_posted", "hearing",
            "filed", "incident", "entry".
        date: The trigger date, or None if the narrative did not state one.
        jurisdiction_hint: Free-text jurisdiction hint (e.g. "MN", "Minnesota").
        window_days: Optional explicit cure/response window stated in a notice.
        source_message_id / source_start / source_end: Provenance, if known.
    """

    event_type: str = ""
    raw_text: str = ""
    trigger: str = ""
    date: date | None = None
    jurisdiction_hint: str | None = None
    window_days: int | None = None
    source_message_id: int | None = None
    source_start: int | None = None
    source_end: int | None = None


@dataclass
class ComputedDeadline:
    """Engine output: a detected event with an optionally computed deadline.

    ``computed`` is True only when a verified rule applied and a date was
    computed. Otherwise the event is "detected + hedged only". ``hedge`` always
    carries a "verify the exact date" caveat.
    """

    event_text: str
    event_type: str
    trigger: str
    trigger_date: date | None
    computed_date: date | None
    rule_id: str | None
    citation: str | None
    computed: bool
    urgency: str
    hedge: str
    jurisdiction: str | None = None
    window_days: int | None = None
    source_message_id: int | None = None
    source_start: int | None = None
    source_end: int | None = None


class DeadlineEventSchema(BaseModel):
    """Validated shape of a single LLM-extracted event."""

    event_type: str = ""
    raw_text: str = ""
    trigger: str = ""
    date: str | None = None  # ISO 8601 date, or null
    jurisdiction_hint: str | None = None
    window_days: int | None = None
    source_start: int | None = None
    source_end: int | None = None


class DeadlineExtractionResult(BaseModel):
    """Complete LLM event-extraction result for one intake."""

    events: list[DeadlineEventSchema] = Field(default_factory=list)
