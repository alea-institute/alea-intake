"""Deterministic tests for the deadline computation engine (v1 "detect + hedge").

No LLM, no DB -- pure date math against the cited rule table. Covers the three
persona cases plus passthrough (detected-but-not-computed) behavior.
"""

from datetime import date

from app.services.deadline.engine import GENERIC_HEDGE, compute_deadlines
from app.services.deadline.schemas import DeadlineEvent

TODAY = date(2026, 7, 5)


def _one(events, **kw):
    result = compute_deadlines(events, today=TODAY, **kw)
    assert len(result) == 1
    return result[0]


def test_mn_family_response_served_plus_30():
    """Persona: served 2026-06-15 -> +30 days = 2026-07-15 (MN family response)."""
    ev = DeadlineEvent(
        event_type="custody_response",
        raw_text="I was served with custody papers on June 15, 2026.",
        trigger="served",
        date=date(2026, 6, 15),
        jurisdiction_hint="MN",
    )
    d = _one([ev], jurisdiction="MN")
    assert d.computed is True
    assert d.computed_date == date(2026, 7, 15)
    assert d.rule_id == "mn_family_response_30d"
    assert d.citation is not None and "303.03" in d.citation
    assert d.urgency == "high"
    assert GENERIC_HEDGE in d.hedge


def test_generic_notice_plus_14():
    """Persona: notice 2026-03-03 + 14 days = 2026-03-17 (generic cure/vacate window)."""
    ev = DeadlineEvent(
        event_type="notice_to_vacate",
        raw_text="Landlord posted a 14-day notice on March 3, 2026.",
        trigger="notice_posted",
        date=date(2026, 3, 3),
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2026, 3, 17)
    assert d.rule_id == "generic_notice_window"
    # 2026-03-17 is before TODAY (2026-07-05) -> lapsed.
    assert d.urgency == "lapsed"
    assert GENERIC_HEDGE in d.hedge


def test_generic_notice_explicit_window_days():
    """An explicit window overrides the 14-day default."""
    ev = DeadlineEvent(
        event_type="notice_to_cure",
        raw_text="7-day notice to cure served 2026-07-01.",
        trigger="notice_posted",
        date=date(2026, 7, 1),
        window_days=7,
    )
    d = _one([ev])
    assert d.computed_date == date(2026, 7, 8)
    assert d.urgency == "high"  # future, not lapsed


def test_asylum_one_year_lapsed():
    """Persona: asylum entry 2019-08-14 + 1yr = 2020-08-14, LAPSED as of 2026-07-05."""
    ev = DeadlineEvent(
        event_type="asylum_entry",
        raw_text="I entered the U.S. on August 14, 2019.",
        trigger="entry",
        date=date(2019, 8, 14),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2020, 8, 14)
    assert d.rule_id == "asylum_one_year"
    assert d.urgency == "lapsed"
    assert "ALREADY PASSED" in d.hedge
    assert GENERIC_HEDGE in d.hedge


def test_asylum_leap_day_clamps():
    """Feb 29 entry clamps to Feb 28 the following (non-leap) year."""
    ev = DeadlineEvent(
        event_type="asylum_entry",
        raw_text="entered 2020-02-29",
        trigger="entry",
        date=date(2020, 2, 29),
    )
    d = _one([ev])
    assert d.computed_date == date(2021, 2, 28)


def test_mn_eviction_hearing_window_earliest_edge():
    """MN eviction summons -> hearing: earliest edge = trigger + 7 days, cited."""
    ev = DeadlineEvent(
        event_type="eviction_summons",
        raw_text="Served an eviction summons on 2026-07-02.",
        trigger="served",
        date=date(2026, 7, 2),
        jurisdiction_hint="MN",
    )
    d = _one([ev], jurisdiction="MN")
    assert d.computed is True
    assert d.computed_date == date(2026, 7, 9)
    assert d.rule_id == "mn_eviction_hearing_window"
    assert "504B.321" in d.citation
    assert "7–14" in d.hedge or "7-14" in d.hedge


def test_no_rule_passthrough_detected_and_hedged():
    """Events with no matching rule pass through as computed=False, still hedged."""
    ev = DeadlineEvent(
        event_type="removal_hearing",
        raw_text="I have a removal hearing but I do not know the date.",
        trigger="hearing",
        date=None,
    )
    d = _one([ev])
    assert d.computed is False
    assert d.computed_date is None
    assert d.rule_id is None
    assert d.urgency == "unknown"
    assert d.hedge == GENERIC_HEDGE


def test_rule_without_date_passes_through():
    """A matching rule but no trigger date cannot compute -> passthrough."""
    ev = DeadlineEvent(
        event_type="custody_response",
        raw_text="I was served but cannot recall when.",
        trigger="served",
        date=None,
        jurisdiction_hint="MN",
    )
    d = _one([ev], jurisdiction="MN")
    assert d.computed is False
    assert d.computed_date is None


def test_results_sorted_lapsed_first():
    """Lapsed/high urgency deadlines sort ahead of unknown passthroughs."""
    future = DeadlineEvent(
        event_type="custody_response", trigger="served",
        date=date(2026, 6, 15), jurisdiction_hint="MN",
    )
    unknown = DeadlineEvent(event_type="misc", trigger="hearing", date=None)
    lapsed = DeadlineEvent(
        event_type="asylum_entry", trigger="entry", date=date(2019, 8, 14),
    )
    result = compute_deadlines([unknown, future, lapsed], jurisdiction="MN", today=TODAY)
    urgencies = [r.urgency for r in result]
    assert urgencies[0] == "lapsed"
    assert urgencies[-1] == "unknown"


def test_immigration_hearing_verbatim_date_is_computed():
    """BUG-12 regression: a verbatim Aug-20-2026 removal hearing must surface as a
    COMPUTED deadline on that exact date (not 'date unclear'), cited to the EOIR
    hearing notice, and NOT flagged lapsed relative to a July-2026 'today'.
    """
    ev = DeadlineEvent(
        event_type="removal_hearing",
        raw_text="My immigration court removal hearing is scheduled for August 20, 2026.",
        trigger="hearing",
        date=date(2026, 8, 20),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2026, 8, 20)
    assert d.rule_id == "immigration_hearing_date"
    assert d.citation is not None and ("1003.18" in d.citation or "EOIR" in d.citation)
    assert d.urgency == "high"  # future hearing -> high, not "lapsed"


def test_generic_stated_court_date_is_computed():
    """BUG-12 regression: a plain stated hearing date (no immigration/eviction
    context) still computes to itself with a generic court-notice citation."""
    ev = DeadlineEvent(
        event_type="hearing",
        raw_text="My court hearing is on September 3, 2026.",
        trigger="hearing",
        date=date(2026, 9, 3),
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2026, 9, 3)
    assert d.rule_id == "stated_court_date"
    assert d.citation is not None


def test_served_summons_mentioning_hearing_uses_offset_rule():
    """CE-review regression: a SERVED eviction summons whose snippet mentions a
    hearing must still use the MN offset rule (service + 7d), never the
    self-dated identity rule (which would claim the deadline already passed)."""
    ev = DeadlineEvent(
        event_type="eviction_summons",
        raw_text="sheriff served me the eviction summons; it says a hearing will be set",
        trigger="served",
        date=date(2026, 7, 1),
        jurisdiction_hint="MN",
    )
    d = _one([ev], jurisdiction="MN")
    assert d.rule_id == "mn_eviction_hearing_window"
    assert d.computed_date == date(2026, 7, 8)
    assert d.urgency == "high"  # NOT lapsed


def test_asylum_entry_mentioning_notice_to_appear_uses_one_year_rule():
    """CE-review regression: an asylum ENTRY event whose snippet mentions a
    notice to appear must still compute entry + 1 year, not identity."""
    ev = DeadlineEvent(
        event_type="asylum_entry",
        raw_text="I entered the US in 2025; later I got a notice to appear",
        trigger="entry",
        date=date(2025, 9, 1),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.rule_id == "asylum_one_year"
    assert d.computed_date == date(2026, 9, 1)
