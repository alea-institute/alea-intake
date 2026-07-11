"""Round 7 domain-scoped deadline rules + cross-domain guards (D01 / BUG-32/34).

Pure date-math against the cited rule table with narrative-inferred domains.
Proves (a) each expansion rule computes with its governing primary-source cite
and routes a lapsed date to its exception pathway (Damien r2/r3), and (b) the
MN family-response / generic-notice / stated-court rules NO LONGER fire on
foreign-domain events (the BUG-32 contamination).
"""

from datetime import date

from app.services.deadline.engine import compute_deadlines
from app.services.deadline.schemas import DeadlineEvent

WAGE = frozenset({"wage_theft"})
BENEFITS = frozenset({"benefits_denial"})
CONSUMER = frozenset({"consumer_debt"})
EMPLOYMENT = frozenset({"employment_discrimination"})
ELDER = frozenset({"elder_exploitation"})
FAMILY = frozenset({"family"})


def _one(events, today, **kw):
    r = compute_deadlines(events, today=today, **kw)
    assert len(r) == 1
    return r[0]


# --------------------------------------------------------------------------
# BUG-32: the MN family-response rule must NOT fire cross-domain.
# --------------------------------------------------------------------------


def test_family_rule_does_not_fire_on_wage_termination():
    """A wage-theft termination served in MN must not become a § 518.12 answer."""
    ev = DeadlineEvent(
        event_type="termination",
        raw_text="my boss fired me and never paid my final wages",
        trigger="served",
        date=date(2026, 6, 19),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 9), jurisdiction="MN", domains=WAGE)
    assert d.rule_id != "mn_family_response_30d"
    if d.citation:
        assert "518.12" not in d.citation


def test_family_rule_does_not_fire_on_ui_determination():
    ev = DeadlineEvent(
        event_type="ui_determination",
        raw_text="determination of ineligibility for unemployment misconduct",
        trigger="served",
        date=date(2026, 5, 29),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 7), jurisdiction="MN", domains=BENEFITS)
    assert d.rule_id != "mn_family_response_30d"


def test_family_rule_does_not_fire_on_poa_signing():
    ev = DeadlineEvent(
        event_type="poa_signing",
        raw_text="I signed a power of attorney paper at the kitchen table",
        trigger="served",
        date=date(2025, 12, 8),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 6), jurisdiction="MN", domains=ELDER)
    assert d.rule_id != "mn_family_response_30d"


def test_family_rule_still_fires_on_real_family_service():
    """Guard must not over-correct: a genuine MN custody service still computes."""
    ev = DeadlineEvent(
        event_type="custody_response",
        raw_text="I was served with custody papers (the petition) on June 15",
        trigger="served",
        date=date(2026, 6, 15),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 5), jurisdiction="MN", domains=FAMILY)
    assert d.rule_id == "mn_family_response_30d"
    assert d.computed_date == date(2026, 7, 15)
    assert "518.12" in d.citation


def test_generic_notice_does_not_fire_on_collection_letter():
    """A debt-collection letter must not get a fabricated 14-day cure window."""
    ev = DeadlineEvent(
        event_type="collection_letter",
        raw_text="the letter says i owe $2,483 to the debt collector",
        trigger="notice",
        date=date(2026, 6, 25),
    )
    d = _one([ev], today=date(2026, 7, 8), domains=CONSUMER)
    # It should take the FDCPA rule (cited), NOT the generic tenancy cure window.
    assert d.rule_id != "generic_notice_window"
    assert d.rule_id == "fdcpa_validation_30d"


def test_stated_court_date_does_not_mislabel_severance_deadline():
    """A severance 'sign by' date has no court context -> not a court deadline."""
    ev = DeadlineEvent(
        event_type="severance_signature",
        raw_text="i have to sign the severance agreement by july 21 to get the pay",
        trigger="deadline",
        date=date(2026, 7, 21),
    )
    d = _one([ev], today=date(2026, 7, 10), domains=EMPLOYMENT)
    assert d.rule_id != "stated_court_date"
    # Falls through to passthrough: detected + hedged, not asserted as a court date.
    assert d.computed is False


# --------------------------------------------------------------------------
# BUG-34: the 5 expansion rule sets compute, cite, and route lapsed dates.
# --------------------------------------------------------------------------


def test_stated_court_date_does_not_mislabel_realtor_listing_appointment():
    """Round 7 residual (BUG-32): a realtor 'listing' appointment the extractor
    tagged trigger='appearance' must NOT be asserted as 'the court's own summons'."""
    # The extractor mislabeled this realtor appointment as trigger 'appearance'
    # on one run and 'hearing' on another; NEITHER should be asserted as a court
    # date, because the TEXT carries no court word.
    for bad_trigger in ("appearance", "hearing"):
        ev = DeadlineEvent(
            event_type="appointment",
            raw_text="there is an appointment on July 16th where I sign listing papers with the realtor",
            trigger=bad_trigger,
            date=date(2026, 7, 16),
        )
        d = _one([ev], today=date(2026, 7, 6), domains=ELDER)
        assert d.rule_id != "stated_court_date", f"leaked on trigger={bad_trigger}"
        assert d.computed is False


def test_fdcpa_validation_30d_from_receipt():
    ev = DeadlineEvent(
        event_type="collection_notice",
        raw_text="collection letter received about the debt i owe",
        trigger="received",
        date=date(2026, 6, 25),
    )
    d = _one([ev], today=date(2026, 7, 8), domains=CONSUMER)
    assert d.rule_id == "fdcpa_validation_30d"
    assert d.computed_date == date(2026, 7, 25)
    assert "1692g" in d.citation


def test_debt_sol_6yr_restart_trap_lapsed_routes_to_time_barred():
    ev = DeadlineEvent(
        event_type="last_payment",
        raw_text="i havent paid on that old credit card since august, last payment then",
        trigger="incident",
        date=date(2020, 8, 15),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 12, 1), domains=CONSUMER)
    assert d.rule_id == "debt_sol_6yr_restart_trap"
    assert d.computed_date == date(2026, 8, 15)
    assert d.urgency == "lapsed"
    assert "541.053" in d.citation
    assert "time-barred" in d.hedge.lower()


def test_wage_final_pay_penalty_181_13():
    ev = DeadlineEvent(
        event_type="wage_demand",
        raw_text="i texted him formal that i demand my wages, all of it",
        trigger="demand",
        date=date(2026, 6, 22),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 9), domains=WAGE)
    assert d.rule_id == "mn_final_wage_penalty_181_13"
    assert "181.13" in d.citation
    assert d.urgency == "lapsed"  # demand+1 = Jun 23, already past by Jul 9
    assert "penalty" in d.hedge.lower()


def test_ui_appeal_45d():
    ev = DeadlineEvent(
        event_type="ui_determination",
        raw_text="determination of ineligibility, discharged for employment misconduct",
        trigger="notice",
        date=date(2026, 5, 29),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 7), domains=BENEFITS)
    assert d.rule_id == "mn_ui_appeal_45d"
    assert d.computed_date == date(2026, 7, 13)
    assert "268.101" in d.citation


def test_eeoc_charge_300d_from_termination():
    ev = DeadlineEvent(
        event_type="termination",
        raw_text="the termination letter came, i was fired for my disability",
        trigger="incident",
        date=date(2026, 5, 22),
    )
    d = _one([ev], today=date(2026, 7, 10), domains=EMPLOYMENT)
    assert d.rule_id == "eeoc_charge_300d"
    assert d.computed_date == date(2027, 3, 18)
    assert "2000e-5" in d.citation


def test_elder_fiduciary_sol_is_background_not_lapsed_urgency():
    ev = DeadlineEvent(
        event_type="exploitation",
        raw_text="he uses the power of attorney to transfer my money as caregiver pay",
        trigger="incident",
        date=date(2026, 1, 15),
        jurisdiction_hint="MN",
    )
    d = _one([ev], today=date(2026, 7, 6), domains=ELDER)
    assert d.rule_id == "mn_fiduciary_conversion_sol_6yr"
    assert d.computed_date == date(2032, 1, 15)
    assert "541.05" in d.citation
    assert d.urgency == "medium"  # background timing, not an urgency driver
