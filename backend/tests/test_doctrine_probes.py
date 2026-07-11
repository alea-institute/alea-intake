"""Deterministic doctrine-probe backstop tests (RUB-01, Damien r1 2026-07-10).

Predicates are exercised against verbatim excerpts of the actual persona
narratives so the backstop provably fires on the campaign's gate facts.
"""

from __future__ import annotations

from app.services.analysis.doctrine_probes import PROBES, run_probes

# Verbatim excerpts from the persona narratives (the gate facts).
IMM_EXCERPT = """
I came to this country August 14, 2019, cross by the river near Eagle Pass
Texas. Immigration catch us the next morning, give me some papers, NTA I think
it say. A man, not a lawyer, his name Rigoberto, charge me six hundred dollars,
say he file my asylum paper for me, I never got nothing back after, no receipt
even. I marry my husband Danilo in 2022, he already have his green card ten
years now, he hit me first time last year, then again March 15 this year, I
call the Bloomington police that night, they arrest him, there was a police
report. Officer say I was cooperating good with them. I work cleaning houses,
a friend give me a social number that's not really mine to get the job, I
still working there now. The hearing letter say I have to go to the court at
Fort Snelling, August twenty, this year, 2026. Immigration removal case.
"""

FC_EXCERPT = """
I got served with custody papers June 15. On June 28 he grab my arm hard
enough it left a bruise (I have pictures) and he was screaming that if I
"tried anything" with the custody case he'd take the kids and I'd "never see
them again". My husband and I married in 2019. The petition asks for sole
custody of our kids.
"""

LT_EXCERPT = """
I called the city on feb 20 to report the mold and no-heat thing and someone
from the city actually came out feb 25 and i guess wrote him up for it. then
on march 3 there was a 14 day notice taped to my door saying i have to pay or
get out, and now there is an eviction case with a court date.
"""


def _ids(text: str) -> set[str]:
    return {p.id for p in run_probes(text)}


def test_immigration_narrative_fires_all_five_immigration_probes():
    ids = _ids(IMM_EXCERPT)
    assert "vawa_self_petition" in ids
    assert "u_nonimmigrant_status" in ids
    assert "adjustment_bar_245c_vawa_exemption" in ids
    assert "pereira_nta_defect" in ids
    assert "asylum_one_year_bar_exception" in ids


def test_family_custody_narrative_fires_dv_and_flight_probes():
    ids = _ids(FC_EXCERPT)
    assert "ofp_grounds" in ids
    assert "dv_custody_best_interest_factor" in ids
    assert "parental_abduction_flight_risk" in ids


def test_landlord_tenant_narrative_fires_retaliation_probe():
    assert "retaliatory_eviction_defense" in _ids(LT_EXCERPT)


def test_lt_narrative_does_not_fire_immigration_probes():
    ids = _ids(LT_EXCERPT)
    assert not ids & {
        "vawa_self_petition",
        "u_nonimmigrant_status",
        "adjustment_bar_245c_vawa_exemption",
        "pereira_nta_defect",
        "asylum_one_year_bar_exception",
    }


def test_benign_narrative_fires_nothing():
    assert run_probes("I want to review a business contract for my bakery.") == []
    assert run_probes("") == []
    assert run_probes(None) == []


def test_every_probe_carries_authority_and_question():
    for p in PROBES:
        assert p.authority.strip(), p.id
        assert "?" in p.question, p.id  # phrased as a question (RUB-01 form)
        assert p.priority >= 80  # survives the question-gen batch cap


def test_pereira_probe_does_not_fire_on_maintain_substring():
    """Round-4b false positive: 'mai-NTA-in(tenance)' in lease documents
    triggered the NTA-defect probe in a landlord-tenant matter."""
    t = "The tenant agrees to maintain the premises. Maintenance requests go to the landlord. There is an eviction case."
    assert "pereira_nta_defect" not in _ids(t)


def test_pereira_probe_requires_immigration_context():
    """A bare 'NTA' acronym without immigration context must not fire."""
    assert "pereira_nta_defect" not in _ids("The NTA form was attached to the lease.")
    assert "pereira_nta_defect" in _ids(
        "Immigration gave me papers, NTA it say, about my removal proceeding."
    )


LT_DEPOSIT_NOTICE_EXCERPT = """
the notice just had a box checked saying "material lease violation" which i
have no clue what that even means, i never violated anything?? also side note
when we moved in july 2025 he made us pay an extra $500 CASH for having our
cat, no receipt or nothing, just handed it to him. now there is an eviction
case against me and my landlord wants me out.
"""


def test_lt_deposit_and_defective_notice_probes_fire():
    """Round-5a LT RUB-01 residual: the $500 cash pet deposit (504B.178) and
    the vague 'material lease violation' notice surfaced in NO form. Both
    probes must fire on the verbatim narrative wording."""
    ids = _ids(LT_DEPOSIT_NOTICE_EXCERPT)
    assert "security_deposit_irregularity" in ids
    assert "defective_eviction_notice" in ids


def test_deposit_probe_does_not_fire_without_rental_context():
    assert "security_deposit_irregularity" not in _ids(
        "I paid cash with no receipt for a used car."
    )
