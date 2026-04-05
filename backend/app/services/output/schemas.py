"""Pydantic schemas for the output data layer.

Defines format-neutral data contracts for output generation:
- OutputContext: unified data structure carrying the full analysis/research graph
- CIRACSection: per-claim CIRAC-format section (Issue, Rule, Application, Conclusion)
- OutputProfile: deployment-type configuration (law_firm, legal_aid, court_self_help)
- TriageResult/TriageRecommendation: multi-factor triage routing
- ActionItem: prioritized action checklist
- GapReport/GapEntry: inline + appendix gap analysis
- OrgBranding: per-org visual branding

Three built-in profile constants: LAW_FIRM_PROFILE, LEGAL_AID_PROFILE, COURT_SELF_HELP_PROFILE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Authority / Fact / Element reference models (lightweight, for embedding in CIRAC)
# ---------------------------------------------------------------------------


class AuthorityRef(BaseModel):
    """Lightweight authority reference for the CIRAC Rule section."""

    citation: str
    title: str
    authority_type: str
    jurisdiction: str | None = None
    binding_strength: Literal["binding", "persuasive", "secondary"]
    verified: bool = False
    verification_source: str | None = None
    excerpt: str | None = None
    relevance_score: float | None = None
    source_url: str | None = None


class FactMappingRef(BaseModel):
    """Fact-to-element mapping in the CIRAC Application section."""

    fact_id: int
    fact_text: str
    confidence: float
    mapping_rationale: str | None = None


class ElementRef(BaseModel):
    """Claim element with satisfaction status and supporting fact mappings."""

    element_id: int
    element_name: str
    element_description: str | None = None
    is_satisfied: bool
    satisfaction_confidence: float | None = None
    fact_mappings: list[FactMappingRef] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gap models
# ---------------------------------------------------------------------------


class GapEntry(BaseModel):
    """A single gap item -- used inline per claim and in the consolidated appendix."""

    gap_id: int
    gap_type: str
    description: str
    priority: int
    claim_id: int | None = None
    element_id: int | None = None
    claim_name: str | None = None
    element_name: str | None = None
    action_item_ref: int | None = None
    open_questions: list[str] = Field(default_factory=list)


class GapReport(BaseModel):
    """Consolidated gap report -- per-claim grouping and appendix (D-07)."""

    per_claim: dict[str, list[GapEntry]] = Field(default_factory=dict)
    consolidated_gaps: list[GapEntry] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    completeness_score: float = 0.0


# ---------------------------------------------------------------------------
# CIRAC section model
# ---------------------------------------------------------------------------


class CIRACSection(BaseModel):
    """Per-claim CIRAC section: Issue, Rule (authorities), Application (elements), Conclusion, Gaps."""

    claim_id: int
    claim_name: str
    claim_type: str
    confidence: float
    jurisdiction: str | None = None
    folio_iri: str | None = None
    issue_statement: str
    authorities: list[AuthorityRef] = Field(default_factory=list)
    elements: list[ElementRef] = Field(default_factory=list)
    gaps: list[GapEntry] = Field(default_factory=list)
    conclusion: str = ""


# ---------------------------------------------------------------------------
# Triage models
# ---------------------------------------------------------------------------


class TriageRecommendation(BaseModel):
    """A single routing recommendation with multi-factor scores."""

    destination: str
    destination_type: Literal["practice_area", "attorney", "program"]
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    practice_area_match: float = 0.0
    jurisdiction_match: float = 0.0
    complexity_score: float = 0.0


class TriageResult(BaseModel):
    """Multi-factor triage/routing result (D-02)."""

    recommendations: list[TriageRecommendation] = Field(default_factory=list)
    primary_practice_area: str | None = None
    primary_jurisdiction: str | None = None
    complexity_level: Literal["low", "medium", "high"] = "medium"
    urgency_level: Literal["routine", "urgent", "emergency"] = "routine"


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------


class ActionItem(BaseModel):
    """Prioritized action item (D-03)."""

    item_number: int
    category: Literal["documents_to_gather", "follow_up_steps", "referrals"]
    description: str
    priority: Literal["urgent", "important", "helpful"]
    deadline: str | None = None
    claim_ref: str | None = None
    element_ref: str | None = None


# ---------------------------------------------------------------------------
# Org branding
# ---------------------------------------------------------------------------


class OrgBranding(BaseModel):
    """Per-org visual branding for rendered output (D-09)."""

    logo_path: str | None = None
    primary_color: str = "#1a365d"
    secondary_color: str = "#2b6cb0"
    font_name: str = "Times New Roman"
    org_name: str | None = None


# ---------------------------------------------------------------------------
# Output profile
# ---------------------------------------------------------------------------


class OutputProfile(BaseModel):
    """Deployment-type profile controlling content, language, and sections (D-04)."""

    profile_type: Literal["law_firm", "legal_aid", "court_self_help"]
    language_level: Literal["professional", "accessible", "plain"]
    sections: dict[str, bool] = Field(default_factory=lambda: {
        "executive_summary": True,
        "cirac_memo": True,
        "triage_routing": False,
        "action_items": True,
        "gap_appendix": True,
        "authorities_table": True,
    })
    reading_grade_level: int | None = None
    org_branding: OrgBranding | None = None


# ---------------------------------------------------------------------------
# OutputContext -- the unified data structure for rendering
# ---------------------------------------------------------------------------


class OutputContext(BaseModel):
    """Unified data structure carrying the full analysis/research graph for rendering."""

    intake_id: int
    run_id: int
    org_id: int
    matter_title: str
    generated_at: datetime
    claims_by_jurisdiction: dict[str, list[CIRACSection]] = Field(default_factory=dict)
    triage: TriageResult | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    gap_report: GapReport = Field(default_factory=GapReport)
    completeness_score: float = 0.0
    executive_summary: str = ""
    profile: OutputProfile


# ---------------------------------------------------------------------------
# Built-in profile constants (D-04)
# ---------------------------------------------------------------------------

LAW_FIRM_PROFILE = OutputProfile(
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

LEGAL_AID_PROFILE = OutputProfile(
    profile_type="legal_aid",
    language_level="accessible",
    sections={
        "executive_summary": True,
        "cirac_memo": True,
        "triage_routing": True,
        "action_items": True,
        "gap_appendix": True,
        "authorities_table": False,
    },
)

COURT_SELF_HELP_PROFILE = OutputProfile(
    profile_type="court_self_help",
    language_level="plain",
    sections={
        "executive_summary": True,
        "cirac_memo": False,
        "triage_routing": True,
        "action_items": True,
        "gap_appendix": False,
        "authorities_table": False,
    },
    reading_grade_level=8,
)
