"""Tests for TriageScorer and ActionItemGenerator services.

Validates multi-factor triage scoring (D-02) and gap-to-action-item
transformation with prioritization and categorization (D-03).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.output.schemas import (
    ActionItem,
    AuthorityRef,
    CIRACSection,
    ElementRef,
    GapEntry,
    GapReport,
    OutputContext,
    OutputProfile,
    TriageRecommendation,
    TriageResult,
)
from app.services.output.triage_scorer import TriageScorer
from app.services.output.action_item_generator import ActionItemGenerator


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_profile() -> OutputProfile:
    return OutputProfile(
        profile_type="law_firm",
        language_level="professional",
        sections={
            "executive_summary": True,
            "cirac_memo": True,
            "triage_routing": False,
            "action_items": True,
            "gap_appendix": True,
            "authorities_table": True,
        },
    )


def _make_claim(
    claim_id: int,
    name: str,
    claim_type: str = "civil",
    jurisdiction: str | None = "California",
    folio_iri: str | None = None,
    gaps: list[GapEntry] | None = None,
    confidence: float = 0.8,
) -> CIRACSection:
    return CIRACSection(
        claim_id=claim_id,
        claim_name=name,
        claim_type=claim_type,
        confidence=confidence,
        jurisdiction=jurisdiction,
        folio_iri=folio_iri,
        issue_statement=f"Whether {name} applies",
        authorities=[],
        elements=[],
        gaps=gaps or [],
        conclusion="Analysis pending",
    )


def _make_gap(
    gap_id: int,
    gap_type: str = "unsupported_element",
    priority: int = 5,
    claim_id: int | None = 1,
    element_id: int | None = None,
    claim_name: str | None = "Test Claim",
    element_name: str | None = None,
) -> GapEntry:
    return GapEntry(
        gap_id=gap_id,
        gap_type=gap_type,
        description=f"Gap {gap_id} description",
        priority=priority,
        claim_id=claim_id,
        element_id=element_id,
        claim_name=claim_name,
        element_name=element_name,
    )


def _make_context(
    claims_by_jurisdiction: dict[str, list[CIRACSection]] | None = None,
    gap_report: GapReport | None = None,
) -> OutputContext:
    return OutputContext(
        intake_id=1,
        run_id=1,
        org_id=1,
        matter_title="Test Matter",
        generated_at=datetime.now(timezone.utc),
        claims_by_jurisdiction=claims_by_jurisdiction or {},
        gap_report=gap_report or GapReport(),
        profile=_make_profile(),
    )


# ---------------------------------------------------------------------------
# TriageScorer tests
# ---------------------------------------------------------------------------


class TestTriageScorer:
    """TriageScorer.score produces ranked routing recommendations per D-02."""

    def test_score_returns_triage_result(self):
        """score() returns a TriageResult with recommendations ranked by score desc."""
        claims = {"California": [_make_claim(1, "Negligence", claim_type="tort")]}
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert isinstance(result, TriageResult)
        assert len(result.recommendations) >= 1
        # Sorted descending by score
        scores = [r.score for r in result.recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_practice_area_match_uses_folio_iri(self):
        """practice_area_match uses FOLIO taxonomy IRI containing AreaOfLaw."""
        claims = {
            "California": [
                _make_claim(
                    1,
                    "Wrongful Termination",
                    claim_type="employment",
                    folio_iri="https://folio.openlegalstandard.org/AreaOfLaw/Employment",
                ),
            ]
        }
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert len(result.recommendations) >= 1
        # Should identify employment practice area
        top = result.recommendations[0]
        assert top.practice_area_match > 0.0

    def test_jurisdiction_match_single_jurisdiction(self):
        """jurisdiction_match scores 1.0 when all claims share one jurisdiction."""
        claims = {
            "California": [
                _make_claim(1, "Claim A"),
                _make_claim(2, "Claim B"),
            ]
        }
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        # All claims in same jurisdiction
        for rec in result.recommendations:
            assert rec.jurisdiction_match == 1.0

    def test_jurisdiction_match_mixed_jurisdictions(self):
        """jurisdiction_match < 1.0 when claims span multiple jurisdictions."""
        claims = {
            "California": [_make_claim(1, "Claim A", jurisdiction="California")],
            "New York": [_make_claim(2, "Claim B", jurisdiction="New York")],
        }
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.primary_jurisdiction is not None
        # At least one recommendation should have jurisdiction_match < 1.0
        matches = [r.jurisdiction_match for r in result.recommendations]
        assert any(m < 1.0 for m in matches)

    def test_complexity_level_high(self):
        """complexity_level is 'high' if >5 claims or >10 gaps."""
        # 6 claims
        claims = {
            "California": [_make_claim(i, f"Claim {i}") for i in range(1, 7)]
        }
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.complexity_level == "high"

    def test_complexity_level_low(self):
        """complexity_level is 'low' if <=2 claims and <=3 gaps."""
        claims = {"California": [_make_claim(1, "Simple Claim")]}
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1), _make_gap(2)],
            completeness_score=0.8,
        )
        ctx = _make_context(claims_by_jurisdiction=claims, gap_report=gap_report)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.complexity_level == "low"

    def test_complexity_level_medium(self):
        """complexity_level is 'medium' for intermediate claim/gap counts."""
        claims = {
            "California": [_make_claim(i, f"Claim {i}") for i in range(1, 5)]
        }
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(i) for i in range(1, 6)],
            completeness_score=0.5,
        )
        ctx = _make_context(claims_by_jurisdiction=claims, gap_report=gap_report)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.complexity_level == "medium"

    def test_urgency_emergency(self):
        """urgency_level is 'emergency' if any gap.priority >= 9."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, priority=9)],
            completeness_score=0.5,
        )
        claims = {"California": [_make_claim(1, "Claim")]}
        ctx = _make_context(claims_by_jurisdiction=claims, gap_report=gap_report)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.urgency_level == "emergency"

    def test_urgency_urgent(self):
        """urgency_level is 'urgent' if any gap.priority >= 7 (but none >= 9)."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, priority=7)],
            completeness_score=0.5,
        )
        claims = {"California": [_make_claim(1, "Claim")]}
        ctx = _make_context(claims_by_jurisdiction=claims, gap_report=gap_report)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.urgency_level == "urgent"

    def test_urgency_routine(self):
        """urgency_level is 'routine' if all gap priorities < 7."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, priority=3)],
            completeness_score=0.5,
        )
        claims = {"California": [_make_claim(1, "Claim")]}
        ctx = _make_context(claims_by_jurisdiction=claims, gap_report=gap_report)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert result.urgency_level == "routine"

    def test_multiple_practice_areas(self):
        """Returns multiple TriageRecommendation entries for multiple practice areas."""
        claims = {
            "California": [
                _make_claim(1, "Employment Claim", claim_type="employment"),
                _make_claim(2, "Family Claim", claim_type="family"),
            ]
        }
        ctx = _make_context(claims_by_jurisdiction=claims)
        scorer = TriageScorer()
        result = scorer.score(ctx)
        assert len(result.recommendations) >= 2
        destinations = {r.destination for r in result.recommendations}
        assert len(destinations) >= 2


# ---------------------------------------------------------------------------
# ActionItemGenerator tests
# ---------------------------------------------------------------------------


class TestActionItemGenerator:
    """ActionItemGenerator transforms gaps to categorized action items per D-03."""

    def test_generate_returns_sorted_action_items(self):
        """generate() returns list[ActionItem] sorted by priority then category."""
        gap_report = GapReport(
            consolidated_gaps=[
                _make_gap(1, gap_type="unsupported_element", priority=8),
                _make_gap(2, gap_type="unexplored_claim", priority=5),
            ],
            completeness_score=0.5,
        )
        claims_by_jurisdiction = {"California": [_make_claim(1, "Claim A")]}
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, claims_by_jurisdiction)
        assert isinstance(items, list)
        assert all(isinstance(i, ActionItem) for i in items)
        # Sorted by priority ordering: urgent before important
        priorities = [i.priority for i in items]
        priority_order = {"urgent": 0, "important": 1, "helpful": 2}
        assert [priority_order[p] for p in priorities] == sorted(priority_order[p] for p in priorities)

    def test_unsupported_element_maps_to_documents_to_gather(self):
        """gap_type 'unsupported_element' -> category 'documents_to_gather'."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, gap_type="unsupported_element", priority=5)],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items[0].category == "documents_to_gather"

    def test_unexplored_claim_maps_to_follow_up_steps(self):
        """gap_type 'unexplored_claim' -> category 'follow_up_steps'."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, gap_type="unexplored_claim", priority=5)],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items[0].category == "follow_up_steps"

    def test_procedural_requirement_maps_to_follow_up_steps(self):
        """gap_type 'procedural_requirement' -> category 'follow_up_steps'."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, gap_type="procedural_requirement", priority=5)],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items[0].category == "follow_up_steps"

    def test_referrals_from_low_completeness_area(self):
        """Creates 'referrals' items from gaps in areas with low completeness."""
        # Build a claim with many gaps and low confidence
        claim = _make_claim(
            1, "Complex Claim", claim_type="immigration", confidence=0.2,
            gaps=[_make_gap(i, priority=3) for i in range(1, 6)],
        )
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(i, priority=3, claim_name="Complex Claim") for i in range(1, 6)],
            per_claim={"Complex Claim": [_make_gap(i, priority=3) for i in range(1, 6)]},
            completeness_score=0.2,
        )
        claims_by_jurisdiction = {"General": [claim]}
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, claims_by_jurisdiction)
        referrals = [i for i in items if i.category == "referrals"]
        assert len(referrals) >= 1

    def test_priority_mapping_urgent(self):
        """Gap priorities are 0-100: >=80 urgent, >=50 important, <50 helpful.
        (The old >=8 threshold made EVERY gap [URGENT] — round-4c defect.)"""
        gap_report = GapReport(
            consolidated_gaps=[
                _make_gap(1, priority=85),
                _make_gap(2, priority=50),
                _make_gap(3, priority=8),
            ],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        by_priority = sorted(i.priority for i in items)
        assert by_priority == ["helpful", "important", "urgent"]

    def test_priority_mapping_important(self):
        """gap priority >= 5 (but < 8) -> action priority 'important'."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, priority=55)],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items[0].priority == "important"

    def test_priority_mapping_helpful(self):
        """gap priority < 5 -> action priority 'helpful'."""
        gap_report = GapReport(
            consolidated_gaps=[_make_gap(1, priority=3)],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items[0].priority == "helpful"

    def test_cross_links_action_item_ref(self):
        """Cross-links action_item_ref back to GapEntry."""
        gap = _make_gap(1, priority=5)
        gap_report = GapReport(
            consolidated_gaps=[gap],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        # After generation, the gap_report's gaps should have action_item_ref set
        assert gap_report.consolidated_gaps[0].action_item_ref == items[0].item_number

    def test_sequential_numbering(self):
        """Items numbered sequentially starting at 1."""
        gap_report = GapReport(
            consolidated_gaps=[
                _make_gap(1, priority=8),
                _make_gap(2, priority=5),
                _make_gap(3, priority=3),
            ],
            completeness_score=0.5,
        )
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        numbers = [i.item_number for i in items]
        assert numbers == list(range(1, len(items) + 1))

    def test_empty_gap_report(self):
        """Empty gap_report produces empty action_items list."""
        gap_report = GapReport(completeness_score=1.0)
        gen = ActionItemGenerator()
        items = gen.generate(gap_report, {})
        assert items == []


# ---------------------------------------------------------------------------
# BUG-25: triage practice-area must NOT leak the claim_type provenance enum
# ---------------------------------------------------------------------------


def _claim(name, claim_type="identified", folio_iri=None):
    return CIRACSection(
        claim_id=1, claim_name=name, claim_type=claim_type, confidence=0.8,
        jurisdiction="MN", folio_iri=folio_iri, issue_statement="x",
    )


def test_extract_practice_areas_never_leaks_claim_type():
    """BUG-25: 'identified'/'discovered' must never appear as a practice area."""
    claims = [
        _claim("Eviction Defense", "identified"),
        _claim("Warranty of Habitability", "discovered"),
        _claim("Child Custody Modification", "identified"),
        _claim("Asylum Application", "discovered"),
        _claim("Wrongful Termination", "identified"),
    ]
    areas = TriageScorer._extract_practice_areas(claims)
    assert "identified" not in areas
    assert "discovered" not in areas
    assert "Landlord-Tenant / Housing" in areas
    assert "Family Law" in areas
    assert "Immigration" in areas
    assert "Employment" in areas


def test_classify_practice_area_unknown_is_general_not_enum():
    """An unrecognized claim classifies to 'General Civil', never claim_type."""
    area = TriageScorer._classify_practice_area(_claim("Zorbnak Widget Dispute", "discovered"))
    assert area == "General Civil"
