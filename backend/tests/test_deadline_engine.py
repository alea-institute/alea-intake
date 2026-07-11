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
    # BUG-24: correct authority is Minn. Stat. § 518.12 (NOT Rule 303.03, which
    # governs family-court motion timing, not the answer deadline).
    assert d.citation is not None and "518.12" in d.citation
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


def test_asylum_lapsed_routes_to_208a2D_exception_pathway():
    """RUB-08 (Damien r2): a lapsed asylum one-year bar must be ROUTED to the
    exception pathway with the governing authority INA § 208(a)(2)(D)."""
    ev = DeadlineEvent(
        event_type="asylum_entry",
        raw_text="I entered the U.S. on August 14, 2019.",
        trigger="entry",
        date=date(2019, 8, 14),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.urgency == "lapsed"
    # The exception pathway and its governing primary source are surfaced.
    assert "208(a)(2)(D)" in d.hedge
    assert "1158(a)(2)(D)" in d.hedge
    # Both flavors of the exception are named for the reviewing attorney/client.
    assert "changed circumstances" in d.hedge.lower()
    assert "extraordinary circumstances" in d.hedge.lower()


def test_non_lapsed_asylum_deadline_omits_exception_pathway():
    """A still-live asylum deadline should NOT carry the lapsed-exception text —
    the exception routing is conditioned on the deadline actually being past."""
    ev = DeadlineEvent(
        event_type="asylum_entry",
        raw_text="I entered the U.S. recently.",
        trigger="entry",
        date=date(2026, 3, 1),  # +1yr = 2027-03-01, future vs TODAY 2026-07-05
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.urgency != "lapsed"
    assert "208(a)(2)(D)" not in d.hedge


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


# ---------------------------------------------------------------------------
# Q5 (RUB-09) — provisional tiered citation standard (Damien 2026-07-08):
#   codified-law deadlines carry the correct primary-source citation;
#   uncited/no-rule events are hedged (never bare authoritative dates).
# ---------------------------------------------------------------------------


def test_q5_codified_rules_carry_correct_primary_source_citations():
    """Every codified-law deadline computes WITH its correct statutory citation."""
    cases = [
        (DeadlineEvent(event_type="asylum_entry", trigger="entry",
                       date=date(2024, 1, 2), jurisdiction_hint="US"),
         None, "208(a)(2)(B)"),
        (DeadlineEvent(event_type="custody_response", trigger="served",
                       date=date(2026, 6, 15), jurisdiction_hint="MN"),
         "MN", "518.12"),
        (DeadlineEvent(event_type="eviction_summons", trigger="served",
                       raw_text="eviction summons", date=date(2026, 7, 2),
                       jurisdiction_hint="MN"),
         "MN", "504B.321"),
    ]
    for ev, jur, needle in cases:
        d = compute_deadlines([ev], jurisdiction=jur, today=TODAY)[0]
        assert d.computed is True, ev.event_type
        assert d.citation and needle in d.citation, (ev.event_type, d.citation)
        # Never a bare authoritative date: a hedge is always attached.
        assert d.hedge and GENERIC_HEDGE in d.hedge


def test_q5_uncited_event_is_hedged_not_bare():
    """A no-rule event surfaces hedged with NO fabricated citation (uncited=hedged)."""
    ev = DeadlineEvent(
        event_type="some_state_filing",
        raw_text="I think I have to file something in Texas soon.",
        trigger="deadline",
        date=None,
    )
    d = compute_deadlines([ev], today=TODAY)[0]
    assert d.computed is False
    assert d.citation is None          # no invented authority
    assert d.hedge == GENERIC_HEDGE    # hedged, not a bare date


# ---------------------------------------------------------------------------
# r3 (RUB-09 STRICT, Damien 2026-07-10): every computed deadline must carry
# its governing primary source — LT round-4 gap: identity/notice rules echoed
# the document instead of citing the statute the LT addendum pins
# (RUB-LT-16/17: Minn. Stat. § 504B.321 / § 504B.321 subd. 1a / § 504B.135).
# ---------------------------------------------------------------------------


def test_r3_mn_eviction_stated_hearing_carries_504B321():
    """A self-dated MN eviction hearing must carry Minn. Stat. § 504B.321,
    not a bare document echo."""
    ev = DeadlineEvent(
        event_type="eviction_hearing",
        raw_text="The summons says my eviction hearing is April 1, 2026 at 9am.",
        trigger="hearing",
        date=date(2026, 4, 1),
        jurisdiction_hint="MN",
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2026, 4, 1)
    assert d.rule_id == "mn_eviction_stated_hearing"
    assert d.citation and "504B.321" in d.citation
    # MN has no separate written answer deadline — say so (RUB-LT-17).
    assert "no separate written answer" in d.hedge


def test_r3_mn_eviction_notice_window_carries_504B321_subd_1a():
    """The MN 14-day nonpayment notice cure window must cite
    Minn. Stat. § 504B.321, subd. 1a — not just echo the notice."""
    ev = DeadlineEvent(
        event_type="notice_to_vacate",
        raw_text="Landlord posted a 14-day notice about the rent on March 3.",
        trigger="notice_posted",
        date=date(2026, 3, 3),
        jurisdiction_hint="MN",
    )
    d = _one([ev])
    assert d.computed is True
    assert d.computed_date == date(2026, 3, 17)
    assert d.rule_id == "mn_eviction_notice_window"
    assert d.citation and "504B.321, subd. 1a" in d.citation


def test_r2_every_rule_carries_lapsed_exception_routing():
    """BUG-29 (RUB-08 r2): EVERY rule in the table must route a lapsed deadline
    to a what-now/exception pathway — not just flag it as passed."""
    from app.services.deadline.rules import RULES

    for rule in RULES:
        assert rule.lapsed_exception, f"rule {rule.id} has no lapsed routing"


def test_r2_lapsed_mn_eviction_hearing_routes_to_vacate_and_expungement():
    """A lapsed MN eviction hearing must route to motion-to-vacate +
    expungement (Minn. Stat. § 484.014) in the hedge the memo renders."""
    ev = DeadlineEvent(
        event_type="eviction_hearing",
        raw_text="my eviction hearing was April 1, 2026",
        trigger="hearing",
        date=date(2026, 4, 1),
        jurisdiction_hint="MN",
    )
    d = _one([ev])  # TODAY = 2026-07-05 -> lapsed
    assert d.urgency == "lapsed"
    assert "484.014" in d.hedge
    assert "vacate" in d.hedge.lower()


def test_r2_lapsed_immigration_hearing_routes_to_motion_to_reopen():
    """A lapsed immigration hearing must route to the in-absentia motion to
    reopen (INA § 240(b)(5)(C))."""
    ev = DeadlineEvent(
        event_type="removal_hearing",
        raw_text="my immigration court hearing was January 10, 2026",
        trigger="hearing",
        date=date(2026, 1, 10),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    assert d.urgency == "lapsed"
    assert "240(b)(5)(C)" in d.hedge
    assert "reopen" in d.hedge.lower()


def test_immigration_hearing_letter_never_computes_cure_window():
    """IMM round-4 gap: the NTA/hearing letter got a fabricated 14-day
    'cure/vacate' deadline via generic_notice_window (wrong deadline —
    RUB-09 0/GATE). Immigration events must never take a notice-window rule."""
    ev = DeadlineEvent(
        event_type="notice_to_vacate",  # mis-typed by the extractor
        raw_text="the immigration hearing letter came end of June",
        trigger="notice_posted",
        date=date(2026, 7, 2),
        jurisdiction_hint="US",
    )
    d = _one([ev])
    # No rule may compute a cure window from an immigration letter.
    assert d.rule_id not in {"generic_notice_window", "mn_eviction_notice_window"}
    assert d.computed is False  # detected + hedged only


def test_r3_non_mn_notice_still_uses_generic_window():
    """A non-MN notice keeps the generic notice rule (no wrong-state cite)."""
    ev = DeadlineEvent(
        event_type="notice_to_vacate",
        raw_text="I got a notice to vacate.",
        trigger="notice_posted",
        date=date(2026, 6, 1),
        jurisdiction_hint="TX",
    )
    d = _one([ev])
    assert d.rule_id == "generic_notice_window"
    assert "504B" not in (d.citation or "")
