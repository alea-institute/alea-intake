"""Tests for DataAssembler and GapReportBuilder services.

Uses in-memory async SQLite sessions for DataAssembler integration tests
and plain data for GapReportBuilder unit tests.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

# Import models at module level so they are registered with TenantBase metadata
# BEFORE the async_engine fixture creates tables.
from app.models.analysis import (  # noqa: F401
    AnalysisClaim,
    AnalysisGap,
    AnalysisRun,
    ClaimElement,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact  # noqa: F401
from app.models.intake import Intake  # noqa: F401
from app.models.research import Authority  # noqa: F401

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures -- seed analysis data into async_session
# ---------------------------------------------------------------------------


async def _seed_full_analysis(session):
    """Seed a complete analysis scenario: run, claims, elements, mappings, gaps, questions, authorities, facts, intake."""
    from app.models.analysis import (
        AnalysisClaim,
        AnalysisGap,
        AnalysisRun,
        ClaimElement,
        FactClaimMapping,
        FollowUpQuestion,
    )
    from app.models.fact import ExtractedFact
    from app.models.intake import Intake
    from app.models.research import Authority

    # Intake
    intake = Intake(
        org_id=1,
        status="active",
        metadata_json={"title": "Smith Employment Dispute"},
    )
    session.add(intake)
    await session.flush()

    # Analysis run
    run = AnalysisRun(
        intake_id=intake.id,
        status="converged",
        trigger_type="auto",
        convergence_score=0.82,
    )
    session.add(run)
    await session.flush()

    # Claims -- two jurisdictions
    claim_ca = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        folio_iri="https://folio.openlegalstandard.org/objective001",
        jurisdiction="California",
        confidence=0.85,
        rationale="Consumer described being fired without cause",
        is_potential=False,
        iteration_discovered=1,
    )
    claim_ny = AnalysisClaim(
        run_id=run.id,
        claim_name="Wage Theft",
        claim_type="discovered",
        folio_iri="https://folio.openlegalstandard.org/objective002",
        jurisdiction="New York",
        confidence=0.70,
        rationale="Unpaid overtime mentioned",
        is_potential=False,
        iteration_discovered=1,
    )
    claim_general = AnalysisClaim(
        run_id=run.id,
        claim_name="Breach of Contract",
        claim_type="identified",
        folio_iri="https://folio.openlegalstandard.org/objective003",
        jurisdiction=None,
        confidence=0.60,
        rationale=None,
        is_potential=False,
        iteration_discovered=1,
    )
    session.add_all([claim_ca, claim_ny, claim_general])
    await session.flush()

    # Elements
    elem_employment = ClaimElement(
        claim_id=claim_ca.id,
        element_name="Employment Relationship",
        element_description="Plaintiff must prove employment existed",
        is_satisfied=True,
        satisfaction_confidence=0.92,
    )
    elem_termination = ClaimElement(
        claim_id=claim_ca.id,
        element_name="Termination Without Cause",
        is_satisfied=False,
        satisfaction_confidence=0.3,
    )
    elem_wages = ClaimElement(
        claim_id=claim_ny.id,
        element_name="Unpaid Wages",
        is_satisfied=True,
        satisfaction_confidence=0.88,
    )
    session.add_all([elem_employment, elem_termination, elem_wages])
    await session.flush()

    # Facts
    fact1 = ExtractedFact(
        intake_id=intake.id,
        message_id=1,
        assertion_text="I was employed by Acme Corp for 5 years",
        fact_type="employment",
        confidence=0.95,
        is_active=True,
    )
    fact2 = ExtractedFact(
        intake_id=intake.id,
        message_id=1,
        assertion_text="They never paid me overtime",
        fact_type="wage",
        confidence=0.90,
        is_active=True,
    )
    fact_inactive = ExtractedFact(
        intake_id=intake.id,
        message_id=1,
        assertion_text="Inactive fact",
        fact_type="other",
        confidence=0.50,
        is_active=False,
    )
    session.add_all([fact1, fact2, fact_inactive])
    await session.flush()

    # Fact-claim mappings
    mapping1 = FactClaimMapping(
        fact_id=fact1.id,
        claim_id=claim_ca.id,
        element_id=elem_employment.id,
        confidence=0.90,
        mapping_rationale="Direct employment statement",
        iteration_number=1,
    )
    mapping2 = FactClaimMapping(
        fact_id=fact2.id,
        claim_id=claim_ny.id,
        element_id=elem_wages.id,
        confidence=0.85,
        mapping_rationale="Overtime complaint maps to wages",
        iteration_number=1,
    )
    session.add_all([mapping1, mapping2])
    await session.flush()

    # Gaps
    gap1 = AnalysisGap(
        run_id=run.id,
        gap_type="unsupported_element",
        claim_id=claim_ca.id,
        element_id=elem_termination.id,
        description="No facts support termination without cause",
        priority=1,
        status="open",
        iteration_found=1,
    )
    gap2 = AnalysisGap(
        run_id=run.id,
        gap_type="weak_mapping",
        claim_id=claim_ny.id,
        description="Overtime evidence is indirect",
        priority=2,
        status="open",
        iteration_found=1,
    )
    gap_resolved = AnalysisGap(
        run_id=run.id,
        gap_type="unexplored_claim",
        description="Already resolved gap",
        priority=0,
        status="resolved",
        iteration_found=1,
        iteration_resolved=2,
    )
    session.add_all([gap1, gap2, gap_resolved])
    await session.flush()

    # Follow-up questions
    q1 = FollowUpQuestion(
        run_id=run.id,
        gap_id=gap1.id,
        question_text="When exactly were you terminated?",
        topic_group="timeline",
        priority=1,
        status="pending",
        iteration_asked=1,
    )
    q2 = FollowUpQuestion(
        run_id=run.id,
        question_text="Do you have pay stubs?",
        topic_group="evidence",
        priority=2,
        status="answered",
        iteration_asked=1,
    )
    session.add_all([q1, q2])
    await session.flush()

    # Authorities
    auth_binding = Authority(
        intake_id=intake.id,
        citation="Cal. Lab. Code 1102.5",
        title="California Labor Code Whistleblower Protection",
        authority_type="statute",
        jurisdiction="California",
        folio_iri="https://folio.openlegalstandard.org/authority001",
        claim_iri="https://folio.openlegalstandard.org/objective001",
        source_tool="courtlistener",
        relevance_score=0.95,
        verified=True,
        verification_status="verified",
    )
    auth_persuasive = Authority(
        intake_id=intake.id,
        citation="Smith v. Jones, 123 F.3d 456",
        title="Smith v. Jones",
        authority_type="case_law",
        jurisdiction="Federal",
        claim_iri="https://folio.openlegalstandard.org/objective001",
        source_tool="courtlistener",
        relevance_score=0.80,
        verified=True,
        verification_status="verified",
    )
    auth_secondary = Authority(
        intake_id=intake.id,
        citation="3 Witkin, Summary of Cal. Law (11th ed.) Employment 42",
        title="Witkin Employment Treatise",
        authority_type="secondary",
        claim_iri="https://folio.openlegalstandard.org/objective001",
        source_tool="westlaw",
        relevance_score=0.70,
        verified=False,
        verification_status="unverified",
    )
    auth_ny = Authority(
        intake_id=intake.id,
        citation="N.Y. Lab. Law 198",
        title="New York Labor Law Wage Claims",
        authority_type="statute",
        jurisdiction="New York",
        claim_iri="https://folio.openlegalstandard.org/objective002",
        source_tool="courtlistener",
        relevance_score=0.90,
        verified=True,
        verification_status="verified",
    )
    session.add_all([auth_binding, auth_persuasive, auth_secondary, auth_ny])
    await session.flush()

    return {
        "intake": intake,
        "run": run,
        "claims": [claim_ca, claim_ny, claim_general],
        "elements": [elem_employment, elem_termination, elem_wages],
        "facts": [fact1, fact2],
        "mappings": [mapping1, mapping2],
        "gaps": [gap1, gap2],
        "questions": [q1, q2],
        "authorities": [auth_binding, auth_persuasive, auth_secondary, auth_ny],
    }


# ---------------------------------------------------------------------------
# DataAssembler tests
# ---------------------------------------------------------------------------


async def test_data_assembler_returns_output_context(async_session):
    """DataAssembler.assemble returns OutputContext with claims grouped by jurisdiction."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE, OutputContext

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    assert isinstance(ctx, OutputContext)
    assert ctx.intake_id == data["intake"].id
    assert ctx.run_id == data["run"].id
    assert ctx.matter_title == "Smith Employment Dispute"


async def test_data_assembler_jurisdiction_grouping(async_session):
    """Claims grouped by jurisdiction, None -> 'General'."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    assert "California" in ctx.claims_by_jurisdiction
    assert "New York" in ctx.claims_by_jurisdiction
    assert "General" in ctx.claims_by_jurisdiction

    ca_claims = ctx.claims_by_jurisdiction["California"]
    assert len(ca_claims) == 1
    assert ca_claims[0].claim_name == "Wrongful Termination"

    ny_claims = ctx.claims_by_jurisdiction["New York"]
    assert len(ny_claims) == 1
    assert ny_claims[0].claim_name == "Wage Theft"

    gen_claims = ctx.claims_by_jurisdiction["General"]
    assert len(gen_claims) == 1
    assert gen_claims[0].claim_name == "Breach of Contract"


async def test_data_assembler_cirac_section_elements(async_session):
    """Each CIRACSection includes elements with fact_mappings."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    ca_section = ctx.claims_by_jurisdiction["California"][0]
    assert len(ca_section.elements) == 2  # Employment Relationship + Termination Without Cause

    # Find the element with fact mappings
    emp_elem = next(e for e in ca_section.elements if e.element_name == "Employment Relationship")
    assert emp_elem.is_satisfied is True
    assert len(emp_elem.fact_mappings) == 1
    assert emp_elem.fact_mappings[0].fact_text == "I was employed by Acme Corp for 5 years"


async def test_data_assembler_authorities_ordering(async_session):
    """Authorities ordered by binding_strength (binding > persuasive > secondary) then relevance_score desc."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    ca_section = ctx.claims_by_jurisdiction["California"][0]
    # Should have 3 authorities for the CA claim (binding statute, persuasive case, secondary treatise)
    assert len(ca_section.authorities) == 3

    # Check ordering: binding first, then persuasive, then secondary
    assert ca_section.authorities[0].binding_strength == "binding"
    assert ca_section.authorities[1].binding_strength == "persuasive"
    assert ca_section.authorities[2].binding_strength == "secondary"


async def test_data_assembler_inline_gaps(async_session):
    """Each CIRACSection includes inline gaps for that claim."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    ca_section = ctx.claims_by_jurisdiction["California"][0]
    assert len(ca_section.gaps) == 1
    assert ca_section.gaps[0].gap_type == "unsupported_element"

    ny_section = ctx.claims_by_jurisdiction["New York"][0]
    assert len(ny_section.gaps) == 1
    assert ny_section.gaps[0].gap_type == "weak_mapping"


async def test_data_assembler_empty_analysis(async_session):
    """DataAssembler handles empty analysis gracefully."""
    from app.models.analysis import AnalysisRun
    from app.models.intake import Intake
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE, OutputContext

    intake = Intake(org_id=1, status="active")
    async_session.add(intake)
    await async_session.flush()

    run = AnalysisRun(
        intake_id=intake.id,
        status="running",
        trigger_type="manual",
    )
    async_session.add(run)
    await async_session.flush()

    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=run.id,
        intake_id=intake.id,
        profile=LAW_FIRM_PROFILE,
    )

    assert isinstance(ctx, OutputContext)
    assert ctx.claims_by_jurisdiction == {}
    assert ctx.action_items == []
    assert ctx.gap_report.consolidated_gaps == []
    assert ctx.completeness_score == 0.0


async def test_data_assembler_completeness_from_convergence(async_session):
    """completeness_score comes from run.convergence_score."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    data = await _seed_full_analysis(async_session)
    assembler = DataAssembler(async_session)
    ctx = await assembler.assemble(
        run_id=data["run"].id,
        intake_id=data["intake"].id,
        profile=LAW_FIRM_PROFILE,
    )

    assert ctx.completeness_score == 0.82  # matches run.convergence_score


# ---------------------------------------------------------------------------
# GapReportBuilder tests (unit tests, no DB needed)
# ---------------------------------------------------------------------------


def test_gap_report_builder_per_claim_grouping():
    """GapReportBuilder.build groups gaps by claim_id -> claim_name."""
    from app.services.output.gap_report_builder import GapReportBuilder

    gaps = [
        SimpleNamespace(id=1, gap_type="unsupported_element", description="Gap A", priority=1, claim_id=10, element_id=None, status="open"),
        SimpleNamespace(id=2, gap_type="weak_mapping", description="Gap B", priority=2, claim_id=10, element_id=None, status="open"),
        SimpleNamespace(id=3, gap_type="unexplored_claim", description="Gap C", priority=3, claim_id=20, element_id=None, status="open"),
    ]
    questions = [
        SimpleNamespace(question_text="Q1?", status="pending"),
        SimpleNamespace(question_text="Q2?", status="answered"),
    ]
    claims = {10: "Wrongful Termination", 20: "Wage Theft"}
    elements = {}

    report = GapReportBuilder.build(gaps, questions, claims, elements, convergence_score=0.75)

    assert "Wrongful Termination" in report.per_claim
    assert len(report.per_claim["Wrongful Termination"]) == 2
    assert "Wage Theft" in report.per_claim
    assert len(report.per_claim["Wage Theft"]) == 1


def test_gap_report_builder_consolidated_sorted_by_priority():
    """consolidated_gaps sorted by priority desc."""
    from app.services.output.gap_report_builder import GapReportBuilder

    gaps = [
        SimpleNamespace(id=1, gap_type="a", description="Low", priority=1, claim_id=10, element_id=None, status="open"),
        SimpleNamespace(id=2, gap_type="b", description="High", priority=3, claim_id=10, element_id=None, status="open"),
        SimpleNamespace(id=3, gap_type="c", description="Med", priority=2, claim_id=10, element_id=None, status="open"),
    ]
    claims = {10: "Claim"}
    elements = {}

    report = GapReportBuilder.build(gaps, [], claims, elements, convergence_score=0.5)

    assert report.consolidated_gaps[0].priority == 3
    assert report.consolidated_gaps[1].priority == 2
    assert report.consolidated_gaps[2].priority == 1


def test_gap_report_builder_open_questions():
    """open_questions lists only pending follow-up questions."""
    from app.services.output.gap_report_builder import GapReportBuilder

    questions = [
        SimpleNamespace(question_text="Pending Q", status="pending"),
        SimpleNamespace(question_text="Answered Q", status="answered"),
        SimpleNamespace(question_text="Another pending", status="pending"),
    ]

    report = GapReportBuilder.build([], questions, {}, {}, convergence_score=0.6)

    assert len(report.open_questions) == 2
    assert "Pending Q" in report.open_questions
    assert "Another pending" in report.open_questions
    assert "Answered Q" not in report.open_questions


def test_gap_report_builder_completeness_score():
    """completeness_score comes from convergence_score, defaults to 0.0 if None."""
    from app.services.output.gap_report_builder import GapReportBuilder

    report1 = GapReportBuilder.build([], [], {}, {}, convergence_score=0.88)
    assert report1.completeness_score == 0.88

    report2 = GapReportBuilder.build([], [], {}, {}, convergence_score=None)
    assert report2.completeness_score == 0.0


def test_gap_entry_action_item_ref_default_none():
    """GapEntry.action_item_ref is None by default."""
    from app.services.output.gap_report_builder import GapReportBuilder

    gaps = [
        SimpleNamespace(id=1, gap_type="a", description="Gap", priority=1, claim_id=10, element_id=None, status="open"),
    ]
    claims = {10: "Claim"}

    report = GapReportBuilder.build(gaps, [], claims, {}, convergence_score=0.5)

    assert report.consolidated_gaps[0].action_item_ref is None


# ---------------------------------------------------------------------------
# BUG-23 (RUB-15 GATE): executive_summary must be substantive, not empty
# ---------------------------------------------------------------------------


def _section(name, conf, jur="MN"):
    from app.services.output.schemas import CIRACSection

    return CIRACSection(
        claim_id=1,
        claim_name=name,
        claim_type="identified",
        confidence=conf,
        jurisdiction=jur,
        issue_statement=f"Whether {name} applies",
    )


def test_build_executive_summary_is_nonempty_with_issues():
    """An analysis with claims yields a non-empty, factual summary (BUG-23)."""
    from app.services.output.data_assembler import build_executive_summary
    from app.services.output.schemas import GapReport

    summary = build_executive_summary(
        claims_by_jurisdiction={"MN": [_section("Warranty of Habitability", 0.9),
                                        _section("Retaliatory Eviction", 0.7)]},
        additional_by_jurisdiction={},
        deadlines=[],
        safety_alerts=[],
        gap_report=GapReport(open_questions=["Q1", "Q2"]),
        completeness_score=0.75,
    )
    assert summary.strip()
    assert "2 potential legal issues" in summary
    assert "Warranty of Habitability" in summary  # strongest named first
    assert "75%" in summary
    assert "2 follow-up questions" in summary


def test_build_executive_summary_surfaces_lapsed_deadline_with_citation():
    """A lapsed deadline is called out up-front and keeps its citation (BUG-23/Q2/Q5)."""
    from app.services.output.data_assembler import build_executive_summary
    from app.services.output.schemas import DeadlineRef, GapReport

    lapsed = DeadlineRef(
        event_text="Asylum one-year filing deadline",
        computed_date="2020-08-14",
        citation="INA § 208(a)(2)(B)",
        computed=True,
        urgency="lapsed",
    )
    summary = build_executive_summary(
        claims_by_jurisdiction={"US": [_section("Asylum", 0.8, jur="US")]},
        additional_by_jurisdiction={},
        deadlines=[lapsed],
        safety_alerts=[],
        gap_report=GapReport(),
        completeness_score=0.5,
    )
    assert "already" in summary.lower() and "passed" in summary.lower()
    assert "2020-08-14" in summary
    assert "INA § 208(a)(2)(B)" in summary  # citation preserved verbatim


def test_build_executive_summary_no_issues_still_nonempty():
    """Even with zero claims the summary is non-empty (never fails the gate blank)."""
    from app.services.output.data_assembler import build_executive_summary
    from app.services.output.schemas import GapReport

    summary = build_executive_summary(
        claims_by_jurisdiction={},
        additional_by_jurisdiction={},
        deadlines=[],
        safety_alerts=[],
        gap_report=GapReport(open_questions=["Need more info"]),
        completeness_score=0.0,
    )
    assert summary.strip()
    assert "No legal issues" in summary


# ---------------------------------------------------------------------------
# BUG-26: fact->element mappings duplicated 11-20x per element must collapse
# ---------------------------------------------------------------------------


async def test_load_mappings_dedupes_duplicate_fact_element_pairs(async_session):
    """BUG-26: N convergence iterations persist N duplicate mapping rows for the
    same (element, fact) pair; _load_mappings must collapse to one (highest
    confidence)."""
    from app.models.analysis import FactClaimMapping
    from app.services.output.data_assembler import DataAssembler

    data = await _seed_full_analysis(async_session)
    claim = data["claims"][0]
    elem = data["elements"][0]
    fact = data["facts"][0]

    # Simulate 12 convergence-iteration re-persists of the SAME pair.
    for i in range(12):
        async_session.add(
            FactClaimMapping(
                fact_id=fact.id,
                claim_id=claim.id,
                element_id=elem.id,
                confidence=0.50 + i * 0.01,  # varying; max is the last
                mapping_rationale="dup",
                iteration_number=i + 1,
            )
        )
    await async_session.flush()

    assembler = DataAssembler(async_session)
    by_element = await assembler._load_mappings([c.id for c in data["claims"]])

    rows = by_element.get(elem.id, [])
    pairs = [(m.element_id, m.fact_id) for m in rows]
    # Exactly one row for the (elem, fact) pair despite 12+ duplicates.
    assert pairs.count((elem.id, fact.id)) == 1
    kept = next(m for m in rows if m.fact_id == fact.id)
    assert kept.confidence == max(0.90, 0.50 + 11 * 0.01)  # highest-confidence kept
