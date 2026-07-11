"""Round 7 expansion doctrine probes + cross-domain non-bleed (D01/D07 / BUG-33).

Exercises the domain-scoped probe table against verbatim persona-narrative
excerpts. Proves each expansion probe fires on its own domain and that
family/immigration/LT probes do NOT bleed into the employment/benefits/consumer/
elder narratives (the BUG-33 contamination that fabricated DV predicates).
"""

from __future__ import annotations

from app.services.analysis.domain_classifier import classify_domains
from app.services.analysis.doctrine_probes import run_probes

ELDER = (
    "It's about my own son Dale. In December he had me sign a power of attorney "
    "paper. Dale took my debit card "
    "and there's cash coming out at the ATM every week, and a $6,400 check to a "
    "boat place, and transfers to his own account he calls caregiver pay. When I "
    "asked him he grabbed my wrist hard enough to leave a bruise and said I'll end "
    "up at Ridgeview. The bank sent a letter about unusual activity. A realtor came "
    "about listing my house. Can I undo that power of attorney paper?"
)
WAGE = (
    "my boss stole my last paychecks. rick says im an independent contractor, i got "
    "a 1099, but he sets my schedule and sites, i use his tools and company van, i "
    "cant work for anyone else. he pays straight time even when we do 56 hours a "
    "week. i asked him about overtime and that night he fired me. i demand my wages."
)
BENEFITS = (
    "i got denied for unemployment, discharged for employment misconduct over "
    "attendance. i missed work because my daughter was in the hospital with DKA and "
    "i called the charge nurse line before every shift. after the denial i stopped "
    "doing the weekly thing online. the hr lady said i could appeal through hr "
    "within 10 business days and i missed that."
)
EMPLOYMENT = (
    "i got fired because of my back, herniated disc, i have the MRI. i asked HR for "
    "a reasonable accommodation, the scan station or lift assist, and they denied it "
    "saying lifting is an essential function. they put me on unpaid leave and never "
    "said anything about FMLA. then HR emailed a severance agreement, sign by july "
    "21, release all claims, for the disability discrimination."
)
CONSUMER = (
    "these debt collector people call 6 or 7 times a day about an old credit card. "
    "they called my sister and told her i owe money. the guy says they'll garnish my "
    "wages and freeze my bank account by the end of the month. i been on social "
    "security disability since 2021, thats all i live on. i havent paid since august "
    "2020. should i pay them 50?"
)
LT_POSTING = (
    "the 14 day notice and then the court papers, the summons, showed up taped to my "
    "door. there is an eviction case and a court date. i never got handed anything in "
    "person. the landlord ignores the mold."
)


def _ids(text: str) -> set[str]:
    return {p.id for p in run_probes(text, domains=classify_domains(text))}


# -- expansion probes fire on their own domain --


def test_elder_probes_fire():
    ids = _ids(ELDER)
    assert "poa_revocation" in ids
    assert "poa_self_dealing_limit" in ids
    assert "vulnerable_adult_609_2334_maarc" in ids
    assert "elder_household_ofp" in ids  # son = family/household member OFP


def test_wage_probes_fire():
    ids = _ids(WAGE)
    assert "employee_misclassification" in ids
    assert "unpaid_overtime_mflsa" in ids
    assert "wage_theft_retaliation" in ids


def test_benefits_probes_fire():
    ids = _ids(BENEFITS)
    assert "ui_misconduct_family_care_exception" in ids
    assert "ui_weekly_request_resumption" in ids
    assert "ui_hr_appeal_red_herring" in ids


def test_employment_probes_fire():
    ids = _ids(EMPLOYMENT)
    assert "failure_to_accommodate" in ids
    assert "severance_release_trap" in ids
    assert "fmla_interference" in ids


def test_consumer_probes_fire():
    ids = _ids(CONSUMER)
    assert "fdcpa_harassment_practices" in ids
    assert "false_garnishment_threat" in ids
    assert "exempt_income_protection" in ids


def test_d07_service_by_posting_probe_fires():
    ids = _ids(LT_POSTING)
    assert "mn_service_by_posting_504b331" in ids


# -- no cross-domain bleed (BUG-33) --


def test_no_family_or_immigration_bleed_into_wage():
    ids = _ids(WAGE)
    assert "ofp_grounds" not in ids
    assert "dv_custody_best_interest_factor" not in ids
    assert "vawa_self_petition" not in ids
    assert "u_nonimmigrant_status" not in ids


def test_no_family_probe_bleed_into_consumer_or_benefits():
    for text in (CONSUMER, BENEFITS):
        ids = _ids(text)
        assert "ofp_grounds" not in ids
        assert "dv_custody_best_interest_factor" not in ids
        assert "parental_abduction_flight_risk" not in ids


def test_elder_ofp_does_not_require_spouse_or_custody():
    """The elder OFP probe covers a household member (son) without a spouse/custody
    predicate, but the family DV *custody* factor must NOT fire (no custody)."""
    ids = _ids(ELDER)
    assert "elder_household_ofp" in ids
    assert "dv_custody_best_interest_factor" not in ids


def test_lt_probes_do_not_bleed_into_employment():
    ids = _ids(EMPLOYMENT)
    assert "retaliatory_eviction_defense" not in ids
    assert "security_deposit_irregularity" not in ids
    assert "mn_service_by_posting_504b331" not in ids
