"""Tests for the deterministic practice-area domain classifier (round 7, BUG-32/33).

Exercised against verbatim excerpts of the actual persona narratives so the
classifier provably infers the right domain for each expansion persona and does
NOT over-classify unrelated domains.
"""

from __future__ import annotations

from app.services.analysis.domain_classifier import classify_domains, domain_allows

# Verbatim-ish excerpts from the persona narratives (the domain-signal facts).
ELDER = (
    "In December he had me sign a power of attorney paper. Dale took my debit card "
    "and there's cash coming out at the ATM every week. He calls it his caregiver "
    "pay. The bank sent me a letter about unusual activity. A realtor came about "
    "listing papers. Can I undo that power of attorney paper?"
)
WAGE = (
    "my boss basically stole my last two paychecks. rick always said im an "
    "independent contractor, he had me sign some paper, i got a 1099 last year. "
    "he pays $24 an hour, always straight time even when we do 54, 56 hours a week. "
    "june 19 i asked him about overtime, that same night he fired me. i demand my "
    "wages, all of it."
)
BENEFITS = (
    "i got denied for unemployment. they fired me for attendance. the determination "
    "letter says im ineligible because i was discharged for employment misconduct. "
    "i stopped doing the weekly thing online. the hr lady said i could appeal "
    "through hr within 10 business days."
)
EMPLOYMENT = (
    "i got fired because of my back, herniated disc, i have the MRI. march 9 i gave "
    "HR the doctor's note and asked for a reasonable accommodation, the scan station "
    "or lift assist. april 6 they said no, lifting is an essential function. june 30 "
    "HR emailed me a severance agreement, i have to sign by july 21, it says i "
    "release all claims. nobody said one word about FMLA."
)
CONSUMER = (
    "these debt collector people call me 6 or 7 times a day about an old credit "
    "card. north star receivables. they called my sister and told her i owe money. "
    "the drummond guy says they're gonna garnish my wages and freeze my bank "
    "account. i been on social security disability since 2021. should i pay the 50?"
)
LT = (
    "the 14 day notice showed up taped to the door saying i owe back rent. there is "
    "an eviction case, court date april 1st at housing court. the landlord ignores "
    "the mold and no heat. i paid a cash pet deposit with no receipt."
)
IMM = (
    "Immigration removal case. NTA. My asylum paper. I marry my husband, he has his "
    "green card. The hearing letter say I go to the court at Fort Snelling."
)
FAMILY = (
    "I got served with custody papers. The petition asks for sole custody of our "
    "kids. parenting time. he threatened to take the kids and I'd never see them."
)


def test_elder_exploitation_classified():
    d = classify_domains(ELDER)
    assert "elder_exploitation" in d


def test_wage_theft_classified():
    d = classify_domains(WAGE)
    assert "wage_theft" in d


def test_benefits_denial_classified():
    d = classify_domains(BENEFITS)
    assert "benefits_denial" in d


def test_employment_discrimination_classified():
    d = classify_domains(EMPLOYMENT)
    assert "employment_discrimination" in d


def test_consumer_debt_classified():
    d = classify_domains(CONSUMER)
    assert "consumer_debt" in d


def test_core_domains_classified():
    assert "landlord_tenant" in classify_domains(LT)
    assert "immigration" in classify_domains(IMM)
    assert "family" in classify_domains(FAMILY)


def test_no_cross_contamination_of_family_into_employment_areas():
    """The key BUG-32/33 guard: a wage-theft / benefits / consumer narrative must
    NOT be classified as a family matter (which is what let § 518.12 and the
    OFP/custody probes bleed in)."""
    assert "family" not in classify_domains(WAGE)
    assert "family" not in classify_domains(BENEFITS)
    assert "family" not in classify_domains(CONSUMER)
    assert "family" not in classify_domains(ELDER)


def test_empty_narrative_yields_no_domains():
    assert classify_domains("") == frozenset()
    assert classify_domains("   ") == frozenset()


def test_domain_allows_helper():
    # None scope = domain-agnostic, always allowed.
    assert domain_allows(None, frozenset({"wage_theft"})) is True
    # Scoped rule fires only on intersection.
    assert domain_allows(frozenset({"family"}), frozenset({"wage_theft"})) is False
    assert domain_allows(frozenset({"family"}), frozenset({"family"})) is True
