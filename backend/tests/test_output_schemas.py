"""Tests for output Pydantic schemas, OutputDocument DB model, and OutputProfile configuration.

Verifies all Pydantic models for the output data layer (OutputContext, CIRACSection,
TriageResult, ActionItem, GapReport, OutputProfile, OrgBranding, etc.), the OutputDocument
DB model, and three built-in profile constants.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# OutputContext construction
# ---------------------------------------------------------------------------


def test_output_context_construction():
    """OutputContext can be constructed with claims grouped by jurisdiction, elements, mappings, gaps, authorities, facts."""
    from app.services.output.schemas import (
        ActionItem,
        CIRACSection,
        ElementRef,
        FactMappingRef,
        GapEntry,
        GapReport,
        OutputContext,
        OutputProfile,
        TriageResult,
    )

    section = CIRACSection(
        claim_id=1,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.85,
        jurisdiction="California",
        issue_statement="Whether Wrongful Termination applies",
        authorities=[],
        elements=[
            ElementRef(
                element_id=10,
                element_name="Employment Relationship",
                is_satisfied=True,
                satisfaction_confidence=0.9,
                fact_mappings=[
                    FactMappingRef(
                        fact_id=100,
                        fact_text="Consumer was employed by Acme Corp",
                        confidence=0.95,
                        mapping_rationale="Direct employment statement",
                    )
                ],
            )
        ],
        gaps=[
            GapEntry(
                gap_id=1,
                gap_type="unsupported_element",
                description="No facts support termination element",
                priority=1,
            )
        ],
        conclusion="1 of 1 elements supported (90% confidence)",
    )

    gap_report = GapReport(
        per_claim={"Wrongful Termination": [section.gaps[0]]},
        consolidated_gaps=section.gaps,
        open_questions=["When were you terminated?"],
        completeness_score=0.7,
    )

    profile = OutputProfile(
        profile_type="law_firm",
        language_level="professional",
    )

    ctx = OutputContext(
        intake_id=1,
        run_id=1,
        org_id=1,
        matter_title="Test Matter",
        generated_at=datetime.utcnow(),
        claims_by_jurisdiction={"California": [section]},
        triage=None,
        action_items=[],
        gap_report=gap_report,
        completeness_score=0.7,
        executive_summary="",
        profile=profile,
    )

    assert ctx.intake_id == 1
    assert "California" in ctx.claims_by_jurisdiction
    assert len(ctx.claims_by_jurisdiction["California"]) == 1
    assert ctx.claims_by_jurisdiction["California"][0].claim_name == "Wrongful Termination"


# ---------------------------------------------------------------------------
# CIRACSection
# ---------------------------------------------------------------------------


def test_cirac_section_contains_required_parts():
    """CIRACSection contains issue, rule (authorities with binding_strength), application (elements), conclusion, gaps."""
    from app.services.output.schemas import (
        AuthorityRef,
        CIRACSection,
        ElementRef,
        FactMappingRef,
        GapEntry,
    )

    section = CIRACSection(
        claim_id=1,
        claim_name="Breach of Contract",
        claim_type="identified",
        confidence=0.75,
        issue_statement="Whether a valid breach of contract occurred",
        authorities=[
            AuthorityRef(
                citation="Smith v. Jones, 123 F.3d 456",
                title="Smith v. Jones",
                authority_type="case_law",
                binding_strength="binding",
                verified=True,
            )
        ],
        elements=[
            ElementRef(
                element_id=1,
                element_name="Valid Contract",
                is_satisfied=True,
                satisfaction_confidence=0.9,
                fact_mappings=[
                    FactMappingRef(
                        fact_id=1,
                        fact_text="Signed contract on Jan 1",
                        confidence=0.95,
                    )
                ],
            )
        ],
        gaps=[
            GapEntry(
                gap_id=1,
                gap_type="weak_mapping",
                description="Breach element has low confidence",
                priority=2,
            )
        ],
        conclusion="1 of 1 elements supported",
    )

    assert section.issue_statement == "Whether a valid breach of contract occurred"
    assert len(section.authorities) == 1
    assert section.authorities[0].binding_strength == "binding"
    assert len(section.elements) == 1
    assert section.elements[0].fact_mappings[0].confidence == 0.95
    assert len(section.gaps) == 1
    assert section.conclusion == "1 of 1 elements supported"


# ---------------------------------------------------------------------------
# OutputProfile validation
# ---------------------------------------------------------------------------


def test_output_profile_validates_literals():
    """OutputProfile validates profile_type literal, language_level literal, sections dict."""
    from app.services.output.schemas import OutputProfile

    # Valid profile
    p = OutputProfile(
        profile_type="law_firm",
        language_level="professional",
        sections={"cirac_memo": True, "triage_routing": False},
    )
    assert p.profile_type == "law_firm"
    assert p.language_level == "professional"

    # Invalid profile_type
    with pytest.raises(ValidationError):
        OutputProfile(
            profile_type="invalid_type",
            language_level="professional",
        )

    # Invalid language_level
    with pytest.raises(ValidationError):
        OutputProfile(
            profile_type="law_firm",
            language_level="invalid_level",
        )


# ---------------------------------------------------------------------------
# Built-in profile constants
# ---------------------------------------------------------------------------


def test_law_firm_profile():
    """LAW_FIRM_PROFILE has cirac_memo=True, triage_routing=False."""
    from app.services.output.schemas import LAW_FIRM_PROFILE

    assert LAW_FIRM_PROFILE.profile_type == "law_firm"
    assert LAW_FIRM_PROFILE.language_level == "professional"
    assert LAW_FIRM_PROFILE.sections["cirac_memo"] is True
    assert LAW_FIRM_PROFILE.sections["triage_routing"] is False


def test_legal_aid_profile():
    """LEGAL_AID_PROFILE has triage_routing=True."""
    from app.services.output.schemas import LEGAL_AID_PROFILE

    assert LEGAL_AID_PROFILE.profile_type == "legal_aid"
    assert LEGAL_AID_PROFILE.language_level == "accessible"
    assert LEGAL_AID_PROFILE.sections["triage_routing"] is True


def test_court_self_help_profile():
    """COURT_SELF_HELP_PROFILE has reading_grade_level=8, cirac_memo=False."""
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE

    assert COURT_SELF_HELP_PROFILE.profile_type == "court_self_help"
    assert COURT_SELF_HELP_PROFILE.language_level == "plain"
    assert COURT_SELF_HELP_PROFILE.reading_grade_level == 8
    assert COURT_SELF_HELP_PROFILE.sections["cirac_memo"] is False


# ---------------------------------------------------------------------------
# OutputDocument DB model
# ---------------------------------------------------------------------------


async def test_output_document_create(async_session):
    """OutputDocument creates with run_id, intake_id, profile_type, markdown_content, rendered bytes."""
    from app.models.output import OutputDocument

    doc = OutputDocument(
        run_id=1,
        intake_id=1,
        profile_type="law_firm",
        markdown_content="# Case Memo\n\nTest content.",
        rendered_pdf=b"fake-pdf-bytes",
        rendered_docx=b"fake-docx-bytes",
        rendered_json='{"test": true}',
        metadata_json={"pages": 3},
    )
    async_session.add(doc)
    await async_session.flush()

    assert doc.id is not None
    assert doc.run_id == 1
    assert doc.intake_id == 1
    assert doc.profile_type == "law_firm"
    assert doc.markdown_content == "# Case Memo\n\nTest content."
    assert doc.rendered_pdf == b"fake-pdf-bytes"
    assert doc.rendered_docx == b"fake-docx-bytes"
    assert doc.rendered_json == '{"test": true}'
    assert doc.metadata_json == {"pages": 3}


async def test_output_document_nullable_fields(async_session):
    """OutputDocument rendered_pdf, rendered_docx, rendered_json are nullable."""
    from app.models.output import OutputDocument

    doc = OutputDocument(
        run_id=2,
        intake_id=2,
        profile_type="legal_aid",
        markdown_content="# Triage Report",
    )
    async_session.add(doc)
    await async_session.flush()

    assert doc.id is not None
    assert doc.rendered_pdf is None
    assert doc.rendered_docx is None
    assert doc.rendered_json is None
    assert doc.metadata_json is None


# ---------------------------------------------------------------------------
# TriageResult
# ---------------------------------------------------------------------------


def test_triage_result():
    """TriageResult holds ranked recommendations with scores and rationale."""
    from app.services.output.schemas import TriageRecommendation, TriageResult

    rec = TriageRecommendation(
        destination="Employment Law Division",
        destination_type="practice_area",
        score=0.92,
        rationale="Strong match on employment claims",
        practice_area_match=0.95,
        jurisdiction_match=0.90,
        complexity_score=0.65,
    )
    triage = TriageResult(
        recommendations=[rec],
        primary_practice_area="Employment Law",
        primary_jurisdiction="California",
        complexity_level="medium",
        urgency_level="routine",
    )

    assert len(triage.recommendations) == 1
    assert triage.recommendations[0].score == 0.92
    assert triage.recommendations[0].rationale == "Strong match on employment claims"
    assert triage.primary_practice_area == "Employment Law"
    assert triage.complexity_level == "medium"
    assert triage.urgency_level == "routine"


# ---------------------------------------------------------------------------
# ActionItem
# ---------------------------------------------------------------------------


def test_action_item():
    """ActionItem has priority, category, deadline optional, claim_element_ref."""
    from app.services.output.schemas import ActionItem

    item = ActionItem(
        item_number=1,
        category="documents_to_gather",
        description="Obtain employment contract",
        priority="urgent",
        deadline="Within 2 weeks",
        claim_ref="Wrongful Termination",
        element_ref="Employment Relationship",
    )

    assert item.priority == "urgent"
    assert item.category == "documents_to_gather"
    assert item.deadline == "Within 2 weeks"
    assert item.claim_ref == "Wrongful Termination"
    assert item.element_ref == "Employment Relationship"

    # Deadline is optional
    item2 = ActionItem(
        item_number=2,
        category="follow_up_steps",
        description="Contact former employer",
        priority="important",
    )
    assert item2.deadline is None
    assert item2.claim_ref is None


# ---------------------------------------------------------------------------
# GapReport
# ---------------------------------------------------------------------------


def test_gap_report():
    """GapReport has per_claim dict, consolidated_gaps list, completeness_score float."""
    from app.services.output.schemas import GapEntry, GapReport

    entry1 = GapEntry(
        gap_id=1,
        gap_type="unsupported_element",
        description="No evidence for damages element",
        priority=1,
        claim_name="Breach of Contract",
    )
    entry2 = GapEntry(
        gap_id=2,
        gap_type="weak_mapping",
        description="Low confidence on consideration element",
        priority=2,
        claim_name="Breach of Contract",
    )

    report = GapReport(
        per_claim={"Breach of Contract": [entry1, entry2]},
        consolidated_gaps=[entry1, entry2],
        open_questions=["What was the value of the contract?"],
        completeness_score=0.65,
    )

    assert "Breach of Contract" in report.per_claim
    assert len(report.per_claim["Breach of Contract"]) == 2
    assert len(report.consolidated_gaps) == 2
    assert report.completeness_score == 0.65
    assert len(report.open_questions) == 1


# ---------------------------------------------------------------------------
# OrgBranding
# ---------------------------------------------------------------------------


def test_org_branding():
    """OrgBranding has logo_path, primary_color, secondary_color, font_name optional fields."""
    from app.services.output.schemas import OrgBranding

    # With defaults
    branding = OrgBranding()
    assert branding.logo_path is None
    assert branding.primary_color == "#1a365d"
    assert branding.secondary_color == "#2b6cb0"
    assert branding.font_name == "Times New Roman"
    assert branding.org_name is None

    # Custom
    branding2 = OrgBranding(
        logo_path="/logos/firm.png",
        primary_color="#333",
        secondary_color="#666",
        font_name="Garamond",
        org_name="Smith & Associates",
    )
    assert branding2.logo_path == "/logos/firm.png"
    assert branding2.org_name == "Smith & Associates"


# ---------------------------------------------------------------------------
# OrganizationConfig output_config_json
# ---------------------------------------------------------------------------


async def test_organization_config_output_json(async_session):
    """OrganizationConfig.output_config_json column accepts JSON dict."""
    from app.models.organization import OrganizationConfig

    config = OrganizationConfig(
        org_id=888,
        llm_data_policy="cloud_optout",
        output_config_json={
            "default_profile": "law_firm",
            "branding": {"primary_color": "#000"},
        },
    )
    async_session.add(config)
    await async_session.flush()

    assert config.id is not None
    assert config.output_config_json["default_profile"] == "law_firm"


# ---------------------------------------------------------------------------
# OutputDocument re-export
# ---------------------------------------------------------------------------


async def test_output_document_reexported(async_session):
    """OutputDocument re-exported from models/__init__.py."""
    from app.models import OutputDocument

    assert OutputDocument.__tablename__ == "output_documents"
