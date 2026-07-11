"""Tests for the deterministic rationale grounding guard (BUG-28 / RUB-04).

The guard hedges LLM-generated claim-rationale prose that asserts evidence the
fact record does not contain (the worst failure class: fabrication). It is the
deterministic backstop behind the issue-spot / explore prompt constraints.
"""

from __future__ import annotations

from app.services.analysis.rationale_guard import ground_rationale


class TestMedicalFabrication:
    """The round-4 LT fabrication: client REPORTS asthma, no doctor's note."""

    LT_FACTS = [
        "Marcus has asthma and has been coughing worse since December.",
        "There is mold in the apartment and the landlord has not fixed it.",
        "The tenant is withholding rent over the mold.",
    ]

    def test_hedges_doctors_documentation_of_x(self):
        # Exact professional-register fabrication from export_78.json round 4.
        rationale = (
            "The landlord's inaction regarding the mold could create liability "
            "for health issues experienced by the responder's son, especially "
            "given the doctor's documentation of asthma."
        )
        out, hedges = ground_rationale(rationale, self.LT_FACTS)
        assert hedges, "guard should fire on an unsupported medical-doc assertion"
        assert "doctor's documentation" not in out
        assert "the reported asthma" in out
        # The grounded subject (asthma) survives; only the false evidence claim goes.
        assert "asthma" in out

    def test_hedges_doctor_has_noted_that(self):
        rationale = (
            "This matters particularly because the doctor has noted that he has "
            "asthma."
        )
        out, hedges = ground_rationale(rationale, self.LT_FACTS)
        assert hedges
        assert "the doctor has noted that" not in out
        assert "the client reports that he has asthma" in out

    def test_hedges_medical_records_show(self):
        rationale = "Medical records show that the child suffers respiratory harm."
        out, hedges = ground_rationale(rationale, self.LT_FACTS)
        assert hedges
        assert "medical records show" not in out.lower()
        assert "the client reports that" in out.lower()

    def test_does_not_hedge_when_doctor_evidence_in_record(self):
        # If a fact actually documents the doctor's finding, leave the assertion.
        facts = self.LT_FACTS + [
            "The pediatrician diagnosed Marcus with asthma and provided a written note.",
        ]
        rationale = "This is supported by the doctor's documentation of asthma."
        out, hedges = ground_rationale(rationale, facts)
        assert not hedges, "genuinely-documented matters must not be hedged"
        assert out == rationale


class TestPoliceFabrication:
    def test_hedges_police_report_confirms(self):
        facts = ["The client says her partner threatened her last week."]
        rationale = "The police report confirms that the partner made threats."
        out, hedges = ground_rationale(rationale, facts)
        assert hedges
        assert "police report confirms" not in out.lower()
        assert "the client reports that" in out.lower()

    def test_does_not_hedge_when_police_report_in_record(self):
        facts = ["The client filed a police report; officer took a statement."]
        rationale = "The police report confirms that the partner made threats."
        out, hedges = ground_rationale(rationale, facts)
        assert not hedges
        assert out == rationale


class TestNoFalsePositives:
    def test_grounded_prose_untouched(self):
        facts = ["Mold in the unit; no heat since November."]
        rationale = (
            "Mold and lack of heat constitute a breach of the implied warranty "
            "of habitability under Minnesota law."
        )
        out, hedges = ground_rationale(rationale, facts)
        assert not hedges
        assert out == rationale

    def test_empty_rationale(self):
        assert ground_rationale("", ["fact"]) == ("", [])
        assert ground_rationale(None, ["fact"]) == ("", [])

    def test_client_reports_phrasing_is_already_grounded(self):
        facts = ["Marcus has asthma."]
        rationale = "The client reports that her son has asthma."
        out, hedges = ground_rationale(rationale, facts)
        assert not hedges
        assert out == rationale
