"""Tests for TemplateEngine, Jinja2 templates, and LanguageAdapter.

Validates Markdown rendering through Jinja2 templates with profile-based
section visibility (D-01, D-04) and LLM-driven language adaptation (D-05).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.output.schemas import (
    ActionItem,
    AuthorityRef,
    CIRACSection,
    ElementRef,
    FactMappingRef,
    GapEntry,
    GapReport,
    OrgBranding,
    OutputContext,
    OutputProfile,
    TriageRecommendation,
    TriageResult,
    LAW_FIRM_PROFILE,
    LEGAL_AID_PROFILE,
    COURT_SELF_HELP_PROFILE,
)
from app.services.output.template_engine import TemplateEngine
from app.services.output.language_adapter import LanguageAdapter


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_authority(
    citation: str = "Smith v. Jones, 123 F.3d 456 (9th Cir. 2020)",
    binding: str = "binding",
    verified: bool = True,
) -> AuthorityRef:
    return AuthorityRef(
        citation=citation,
        title="Smith v. Jones",
        authority_type="case_law",
        jurisdiction="California",
        binding_strength=binding,
        verified=verified,
        excerpt="The court held that employment discrimination claims require...",
        relevance_score=0.85,
    )


def _make_element(
    element_id: int = 1,
    name: str = "Protected Class Membership",
    satisfied: bool = True,
    confidence: float = 0.9,
) -> ElementRef:
    return ElementRef(
        element_id=element_id,
        element_name=name,
        element_description="Member of a protected class under Title VII",
        is_satisfied=satisfied,
        satisfaction_confidence=confidence,
        fact_mappings=[
            FactMappingRef(
                fact_id=1,
                fact_text="Client is a 45-year-old Hispanic woman",
                confidence=0.92,
                mapping_rationale="Age, race, and gender are protected classes",
            )
        ],
    )


def _make_gap(
    gap_id: int = 1,
    gap_type: str = "unsupported_element",
    priority: int = 7,
) -> GapEntry:
    return GapEntry(
        gap_id=gap_id,
        gap_type=gap_type,
        description="No documentation of adverse employment action",
        priority=priority,
        claim_id=1,
        claim_name="Employment Discrimination",
        element_name="Adverse Employment Action",
        action_item_ref=1,
    )


def _make_claim(
    claim_id: int = 1,
    name: str = "Employment Discrimination",
    jurisdiction: str = "California",
    has_gaps: bool = True,
) -> CIRACSection:
    gaps = [_make_gap()] if has_gaps else []
    return CIRACSection(
        claim_id=claim_id,
        claim_name=name,
        claim_type="employment",
        confidence=0.85,
        jurisdiction=jurisdiction,
        folio_iri="https://folio.openlegalstandard.org/AreaOfLaw/Employment",
        issue_statement="Whether the employer engaged in unlawful employment discrimination",
        authorities=[
            _make_authority(),
            _make_authority(
                citation="42 U.S.C. ss 2000e",
                binding="binding",
                verified=True,
            ),
            _make_authority(
                citation="Treatise on Employment Law ss 5.2",
                binding="secondary",
                verified=False,
            ),
        ],
        elements=[
            _make_element(1, "Protected Class Membership", True, 0.9),
            _make_element(2, "Adverse Employment Action", False, 0.3),
        ],
        gaps=gaps,
        conclusion="1 of 2 elements supported (60% confidence)",
    )


def _make_triage() -> TriageResult:
    return TriageResult(
        recommendations=[
            TriageRecommendation(
                destination="Employment Law",
                destination_type="practice_area",
                score=0.85,
                rationale="employment practice area (100% of claims); single jurisdiction",
                practice_area_match=1.0,
                jurisdiction_match=1.0,
                complexity_score=0.5,
            ),
        ],
        primary_practice_area="Employment Law",
        primary_jurisdiction="California",
        complexity_level="medium",
        urgency_level="urgent",
    )


def _make_action_items() -> list[ActionItem]:
    return [
        ActionItem(
            item_number=1,
            category="documents_to_gather",
            description="Obtain termination letter or notice",
            priority="urgent",
            claim_ref="Employment Discrimination",
            element_ref="Adverse Employment Action",
        ),
        ActionItem(
            item_number=2,
            category="follow_up_steps",
            description="Confirm date of last employment",
            priority="important",
            claim_ref="Employment Discrimination",
        ),
    ]


def _make_gap_report() -> GapReport:
    return GapReport(
        per_claim={
            "Employment Discrimination": [_make_gap()],
        },
        consolidated_gaps=[_make_gap()],
        open_questions=[
            "What was the stated reason for termination?",
            "Were there any written warnings prior to termination?",
        ],
        completeness_score=0.65,
    )


def _make_context(
    profile: OutputProfile | None = None,
    include_triage: bool = True,
    include_action_items: bool = True,
    include_gaps: bool = True,
    executive_summary: str = "This matter involves an employment discrimination claim.",
) -> OutputContext:
    return OutputContext(
        intake_id=100,
        run_id=50,
        org_id=1,
        matter_title="Garcia v. Acme Corp",
        generated_at=datetime(2026, 4, 5, 10, 30, 0, tzinfo=timezone.utc),
        claims_by_jurisdiction={
            "California": [_make_claim()],
        },
        triage=_make_triage() if include_triage else None,
        action_items=_make_action_items() if include_action_items else [],
        gap_report=_make_gap_report() if include_gaps else GapReport(completeness_score=1.0),
        completeness_score=0.65,
        executive_summary=executive_summary,
        profile=profile or LAW_FIRM_PROFILE,
    )


# ---------------------------------------------------------------------------
# TemplateEngine tests
# ---------------------------------------------------------------------------


class TestTemplateEngine:
    """TemplateEngine renders OutputContext through Jinja2 templates per profile."""

    def test_render_full_returns_markdown(self):
        """render_full() returns complete Markdown string with all enabled sections."""
        ctx = _make_context()
        engine = TemplateEngine()
        result = engine.render_full(ctx, ctx.profile)
        assert isinstance(result, str)
        assert len(result) > 100
        # Should contain the matter title
        assert "Garcia v. Acme Corp" in result

    def test_profile_sections_control_visibility(self):
        """Disabled sections are omitted from output."""
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={
                "executive_summary": False,
                "cirac_memo": True,
                "triage_routing": False,
                "action_items": False,
                "gap_appendix": False,
                "authorities_table": False,
            },
        )
        ctx = _make_context(profile=profile)
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        # Should have CIRAC memo content but no action items or triage
        assert "Employment Discrimination" in result
        # Should not have triage or action items sections
        assert "Triage" not in result
        assert "Action Items" not in result

    def test_cirac_heading_hierarchy(self):
        """CIRAC memo: H1=title, H2=jurisdiction, H3=claim, H4=Issue/Rule/Application/Conclusion."""
        ctx = _make_context()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={
                "executive_summary": False,
                "cirac_memo": True,
                "triage_routing": False,
                "action_items": False,
                "gap_appendix": False,
                "authorities_table": False,
            },
        )
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        # H1 = title
        assert "# Garcia v. Acme Corp" in result
        # H2 = jurisdiction
        assert "## California" in result
        # H3 = claim
        assert "### Employment Discrimination" in result
        # H4 = IRAC sections
        assert "#### Issue" in result
        assert "#### Rule" in result
        assert "#### Application" in result
        assert "#### Conclusion" in result

    def test_cirac_authorities_binding_indicators(self):
        """Rule section shows authorities with binding/persuasive/secondary indicators."""
        ctx = _make_context()
        engine = TemplateEngine()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"cirac_memo": True, "executive_summary": False,
                       "triage_routing": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        result = engine.render_full(ctx, profile)
        # Should show binding strength indicators
        assert "[Binding]" in result or "[binding]" in result.lower()
        assert "[Secondary]" in result or "[secondary]" in result.lower()
        # Should show verification flags
        assert "(Verified)" in result or "Verified" in result
        assert "(Unverified)" in result or "Unverified" in result

    def test_cirac_application_element_satisfaction(self):
        """Application section shows element satisfaction with confidence percentages."""
        ctx = _make_context()
        engine = TemplateEngine()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"cirac_memo": True, "executive_summary": False,
                       "triage_routing": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        result = engine.render_full(ctx, profile)
        # Should show element names and satisfaction status
        assert "Protected Class Membership" in result
        assert "Adverse Employment Action" in result
        # Should show confidence percentage
        assert "90%" in result or "0.9" in result

    def test_cirac_gaps_subsection_present_when_gaps(self):
        """Gaps subsection appears only when claim has gaps."""
        ctx = _make_context()
        engine = TemplateEngine()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"cirac_memo": True, "executive_summary": False,
                       "triage_routing": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        result = engine.render_full(ctx, profile)
        assert "Gaps" in result

    def test_cirac_no_gaps_subsection_when_no_gaps(self):
        """Gaps subsection absent when claim has no gaps."""
        claim = _make_claim(has_gaps=False)
        ctx = _make_context(include_gaps=False)
        ctx.claims_by_jurisdiction = {"California": [claim]}
        engine = TemplateEngine()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"cirac_memo": True, "executive_summary": False,
                       "triage_routing": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        result = engine.render_full(ctx, profile)
        # Should not have Gaps & Open Questions H4
        assert "#### Gaps" not in result

    def test_triage_report_shows_recommendations(self):
        """Triage report shows ranked recommendations with scores and rationale."""
        ctx = _make_context()
        profile = OutputProfile(
            profile_type="legal_aid",
            language_level="accessible",
            sections={"triage_routing": True, "executive_summary": False,
                       "cirac_memo": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        assert "Employment Law" in result
        assert "0.85" in result or "85" in result

    def test_action_items_grouped_by_category(self):
        """Action items template groups by category with priority indicators."""
        ctx = _make_context()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"action_items": True, "executive_summary": False,
                       "cirac_memo": False, "triage_routing": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        assert "Documents to Gather" in result or "documents_to_gather" in result.lower()
        assert "Follow-up Steps" in result or "follow_up_steps" in result.lower()
        # Priority indicators
        assert "[URGENT]" in result or "URGENT" in result

    def test_gap_appendix_shows_completeness(self):
        """Gap appendix shows per-claim gap grouping, open questions, and completeness score."""
        ctx = _make_context()
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"gap_appendix": True, "executive_summary": False,
                       "cirac_memo": False, "triage_routing": False,
                       "action_items": False, "authorities_table": False},
        )
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        assert "Gap Report" in result or "gap" in result.lower()
        # Completeness score
        assert "65%" in result or "0.65" in result
        # Open questions
        assert "What was the stated reason for termination?" in result

    def test_executive_summary_included(self):
        """Executive summary placeholder included at top when non-empty."""
        ctx = _make_context(executive_summary="This is a test summary.")
        profile = OutputProfile(
            profile_type="law_firm",
            language_level="professional",
            sections={"executive_summary": True, "cirac_memo": False,
                       "triage_routing": False, "action_items": False,
                       "gap_appendix": False, "authorities_table": False},
        )
        engine = TemplateEngine()
        result = engine.render_full(ctx, profile)
        assert "This is a test summary." in result

    def test_law_firm_profile_no_triage(self):
        """law_firm profile renders full CIRAC memo without triage."""
        ctx = _make_context(profile=LAW_FIRM_PROFILE)
        engine = TemplateEngine()
        result = engine.render_full(ctx, LAW_FIRM_PROFILE)
        assert "Employment Discrimination" in result
        assert "#### Issue" in result
        # triage_routing is False for law_firm
        assert "Triage & Routing" not in result

    def test_legal_aid_profile_renders_triage(self):
        """legal_aid profile renders triage + simplified memo."""
        ctx = _make_context(profile=LEGAL_AID_PROFILE)
        engine = TemplateEngine()
        result = engine.render_full(ctx, LEGAL_AID_PROFILE)
        # triage_routing is True for legal_aid
        assert "Triage" in result or "Routing" in result
        # cirac_memo is True for legal_aid
        assert "Employment Discrimination" in result

    def test_court_self_help_profile_no_cirac(self):
        """court_self_help profile renders action items without CIRAC memo."""
        ctx = _make_context(profile=COURT_SELF_HELP_PROFILE)
        engine = TemplateEngine()
        result = engine.render_full(ctx, COURT_SELF_HELP_PROFILE)
        # action_items is True for court_self_help
        assert "Action Items" in result or "action" in result.lower()
        # cirac_memo is False for court_self_help
        assert "#### Issue" not in result


# ---------------------------------------------------------------------------
# LanguageAdapter tests
# ---------------------------------------------------------------------------


class TestLanguageAdapter:
    """LanguageAdapter adapts language complexity per profile (D-05)."""

    @pytest.mark.asyncio
    async def test_professional_skips_llm(self):
        """LanguageAdapter skips adaptation for 'professional' language_level."""
        ctx = _make_context(profile=LAW_FIRM_PROFILE)
        llm_service = MagicMock()
        adapter = LanguageAdapter()
        result = await adapter.adapt(ctx, LAW_FIRM_PROFILE, llm_service)
        # Should return context unchanged, no LLM calls
        assert result.executive_summary == ctx.executive_summary
        # LLM should not be called
        assert not hasattr(llm_service, "_called") or not llm_service._called

    @pytest.mark.asyncio
    async def test_adapt_rewrites_text(self):
        """adapt() returns adapted context with rewritten text (mock LLM)."""
        ctx = _make_context(profile=LEGAL_AID_PROFILE)
        mock_llm = AsyncMock()
        mock_llm.get_client_config.return_value = {"provider": "openai", "model": "gpt-4"}

        # Mock the LLM call to return simplified text
        async def mock_rewrite(text, system_prompt):
            return f"Simplified: {text[:50]}"

        adapter = LanguageAdapter()
        with patch.object(adapter, "_rewrite_text", side_effect=mock_rewrite):
            result = await adapter.adapt(ctx, LEGAL_AID_PROFILE, mock_llm)
        assert result.executive_summary.startswith("Simplified:")

    @pytest.mark.asyncio
    async def test_preserves_citations(self):
        """Citations are preserved verbatim (not rewritten by LLM) per pitfall 3."""
        ctx = _make_context(profile=LEGAL_AID_PROFILE)
        original_citations = []
        for sections in ctx.claims_by_jurisdiction.values():
            for section in sections:
                for auth in section.authorities:
                    original_citations.append(auth.citation)

        mock_llm = AsyncMock()

        async def mock_rewrite(text, system_prompt):
            # Simulate LLM that might mangle citations
            return text.replace("123 F.3d 456", "one-two-three F third four-five-six")

        adapter = LanguageAdapter()
        with patch.object(adapter, "_rewrite_text", side_effect=mock_rewrite):
            result = await adapter.adapt(ctx, LEGAL_AID_PROFILE, mock_llm)

        # All original citations must be present in the result's authorities
        for sections in result.claims_by_jurisdiction.values():
            for section in sections:
                for auth in section.authorities:
                    assert auth.citation in original_citations
