"""Tests for the OUTPUT/ASSEMBLY bug fixes:

- BUG-16: question_gen logs the LLM failure instead of a silent zero.
- BUG-14: duplicate follow-up questions and duplicate claim sections collapse.
- BUG-15: DV narrative produces safety alerts + escalation memo section
  (SAFETY CRITICAL); a benign narrative produces none.
- RUB-10: LanguageAdapter.adapt() is invoked on the consumer/plain path and
  rewrites prose (and skips the professional attorney memo).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# Register models with TenantBase metadata before the async_engine builds tables.
from app.models.analysis import (  # noqa: F401
    AnalysisClaim,
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    ClaimElement,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact  # noqa: F401
from app.models.intake import Intake, IntakeSession, Message  # noqa: F401
from app.models.research import Authority  # noqa: F401

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_intake_with_narrative(session, narrative: str):
    """Create an intake + session + one consumer message carrying ``narrative``."""
    intake = Intake(org_id=1, status="active", metadata_json={"title": "Safety Test"})
    session.add(intake)
    await session.flush()

    isession = IntakeSession(intake_id=intake.id, status="active")
    session.add(isession)
    await session.flush()

    msg = Message(
        session_id=isession.id,
        sender_type="consumer",
        modality="text",
        content_encrypted=narrative.encode("utf-8"),
        sequence_number=1,
    )
    session.add(msg)

    run = AnalysisRun(
        intake_id=intake.id,
        status="converged",
        trigger_type="manual",
        convergence_score=0.7,
    )
    session.add(run)
    await session.flush()
    return intake, run


# ---------------------------------------------------------------------------
# BUG-15 -- safety detection (SAFETY CRITICAL)
# ---------------------------------------------------------------------------

_DV_NARRATIVE = (
    "He grabbed me and left bruises. My husband hit me before and threatened to "
    "kill me. I am afraid of partner violence and do not know what to do."
)

_BENIGN_NARRATIVE = (
    "I am starting a small bakery and want to register a trademark for my logo. "
    "I would like to understand the paperwork involved."
)


async def test_dv_narrative_produces_safety_alert(async_session):
    """A DV-style narrative surfaces >=1 safety alert with escalation contacts."""
    from app.services.output.data_assembler import gather_safety_alerts

    intake, _run = await _seed_intake_with_narrative(async_session, _DV_NARRATIVE)
    alerts = await gather_safety_alerts(async_session, intake.id)

    assert len(alerts) >= 1
    # At least one critical DV alert with real hotline resources.
    dv = next((a for a in alerts if "Domestic Violence" in a.protocol_name), None)
    assert dv is not None
    assert dv.severity_tier == "critical"
    assert any("1-800-799-7233" in str(h) for h in dv.hotlines)


async def test_benign_narrative_produces_no_safety_alert(async_session):
    """A benign narrative surfaces zero safety alerts."""
    from app.services.output.data_assembler import gather_safety_alerts

    intake, _run = await _seed_intake_with_narrative(async_session, _BENIGN_NARRATIVE)
    alerts = await gather_safety_alerts(async_session, intake.id)
    assert alerts == []


async def test_memo_includes_escalation_section_on_dv(async_session):
    """Full assemble+render: DV narrative -> memo has the safety escalation section."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE
    from app.services.output.template_engine import TemplateEngine

    intake, run = await _seed_intake_with_narrative(async_session, _DV_NARRATIVE)
    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=COURT_SELF_HELP_PROFILE
    )
    assert len(ctx.safety_alerts) >= 1

    markdown = TemplateEngine().render_full(ctx, COURT_SELF_HELP_PROFILE)
    assert "Your Safety Comes First" in markdown
    assert "741741" in markdown
    assert "1-800-799-7233" in markdown
    assert "Order for Protection" in markdown


async def test_memo_omits_escalation_section_when_benign(async_session):
    """Full assemble+render: benign narrative -> no safety section in the memo."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE
    from app.services.output.template_engine import TemplateEngine

    intake, run = await _seed_intake_with_narrative(async_session, _BENIGN_NARRATIVE)
    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=COURT_SELF_HELP_PROFILE
    )
    assert ctx.safety_alerts == []

    markdown = TemplateEngine().render_full(ctx, COURT_SELF_HELP_PROFILE)
    assert "Your Safety Comes First" not in markdown


# ---------------------------------------------------------------------------
# BUG-20 -- safety resources conditioned on the alert domain
# ---------------------------------------------------------------------------

# A lay-described DV text thread (mirrors the family-custody persona): NO literal
# phrase "domestic violence", yet unmistakable intimate-partner violence.
_LAY_DV_NARRATIVE = (
    "open the door I'm not leaving. you think you can just take my kids from me. "
    "you tried anything with that petition and I swear you will never see them "
    "again. that mark on your arm is nothing compared to what happens if you keep "
    "this up. you left a bruise on me in front of the kids. don't you dare call "
    "the cops."
)

# A stalking narrative that does NOT trip any DV keyword/regex -- fires only the
# Stalking / Harassment protocol (whose sole resource is SPARC).
_STALKING_ONLY_NARRATIVE = (
    "This person has been stalking me for weeks. He keeps following me and shows "
    "up at my workplace uninvited. I feel harassed and watched everywhere I go."
)


async def test_lay_dv_narrative_fires_dv_protocol(async_session):
    """BUG-20: a DV narrative described in lay terms (no phrase 'domestic
    violence') still fires the DV protocol so the DV hotline surfaces."""
    from app.services.output.data_assembler import gather_safety_alerts

    intake, _run = await _seed_intake_with_narrative(async_session, _LAY_DV_NARRATIVE)
    alerts = await gather_safety_alerts(async_session, intake.id)

    dv = next((a for a in alerts if "Domestic Violence" in a.protocol_name), None)
    assert dv is not None, "lay-described DV narrative must fire the DV protocol"
    assert any("1-800-799-7233" in str(h) for h in dv.hotlines)


async def test_lay_dv_narrative_does_not_fire_immigration(async_session):
    """BUG-20: a family-custody narrative full of 'office'/'police'/'notice'
    must NOT spuriously fire the immigration protocol via the 'ice' substring."""
    from app.services.output.data_assembler import gather_safety_alerts

    narrative = (
        "Personal service by the Sheriff's Office. Notice filed with the Justice "
        "Center. " + _LAY_DV_NARRATIVE
    )
    intake, _run = await _seed_intake_with_narrative(async_session, narrative)
    alerts = await gather_safety_alerts(async_session, intake.id)

    assert not any("Immigration" in a.protocol_name for a in alerts), (
        "'ice' must not fire immigration inside office/justice/notice/service"
    )


async def test_dv_domain_guarantees_dv_hotline_when_only_stalking_fires(async_session):
    """BUG-20: when only a Stalking alert fires (SPARC), the DV-advocate domain
    is still active, so the memo must be backed by the National DV Hotline."""
    from app.services.output.data_assembler import gather_safety_alerts

    intake, _run = await _seed_intake_with_narrative(
        async_session, _STALKING_ONLY_NARRATIVE
    )
    alerts = await gather_safety_alerts(async_session, intake.id)

    assert alerts, "stalking narrative should fire at least one alert"
    assert any("stalking" in a.protocol_name.lower() for a in alerts)
    # The domain guardrail injects the DV hotline so "the hotline above" resolves.
    all_hotlines = [h for a in alerts for h in a.hotlines]
    assert any("1-800-799-7233" in str(h) for h in all_hotlines), (
        "DV-advocate domain active but no DV hotline present"
    )


async def test_lay_dv_memo_renders_dv_hotline(async_session):
    """BUG-20 end-to-end: assemble+render a lay-DV narrative -> the memo's safety
    section carries the National DV Hotline, not a domain-mismatched list."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE
    from app.services.output.template_engine import TemplateEngine

    intake, run = await _seed_intake_with_narrative(async_session, _LAY_DV_NARRATIVE)
    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=COURT_SELF_HELP_PROFILE
    )
    markdown = TemplateEngine().render_full(ctx, COURT_SELF_HELP_PROFILE)
    assert "Your Safety Comes First" in markdown
    assert "1-800-799-7233" in markdown
    assert "Immigrant Women" not in markdown


# ---------------------------------------------------------------------------
# BUG-14 -- dedup of questions and claim sections
# ---------------------------------------------------------------------------


async def test_load_questions_dedups_by_normalized_text(async_session):
    """Duplicate follow-up questions (casing/whitespace/punctuation) collapse to one."""
    from app.services.output.data_assembler import DataAssembler

    intake = Intake(org_id=1, status="active", metadata_json={})
    async_session.add(intake)
    await async_session.flush()
    run = AnalysisRun(intake_id=intake.id, status="converged", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    # Three "different" rows that normalize to the same key, plus a distinct one.
    async_session.add_all([
        FollowUpQuestion(run_id=run.id, question_text="When were you fired?", topic_group="timeline", status="pending", iteration_asked=1),
        FollowUpQuestion(run_id=run.id, question_text="when were you fired", topic_group="timeline", status="pending", iteration_asked=2),
        FollowUpQuestion(run_id=run.id, question_text="  When   were you fired?  ", topic_group="timeline", status="pending", iteration_asked=3),
        FollowUpQuestion(run_id=run.id, question_text="Do you have pay stubs?", topic_group="evidence", status="pending", iteration_asked=1),
    ])
    await async_session.flush()

    questions = await DataAssembler(async_session)._load_questions(run.id)
    texts = {q.question_text.strip().lower().rstrip("?.") for q in questions}
    assert len(questions) == 2
    assert "when were you fired" in texts
    assert "do you have pay stubs" in texts


async def test_claim_sections_dedup_across_fanout(async_session):
    """The same claim (normalized name + folio_iri) renders once, not per jurisdiction."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE

    intake = Intake(org_id=1, status="active", metadata_json={})
    async_session.add(intake)
    await async_session.flush()
    run = AnalysisRun(intake_id=intake.id, status="converged", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    iri = "https://folio.openlegalstandard.org/claim001"
    # Same claim emitted three times across the per-jurisdiction fan-out.
    async_session.add_all([
        AnalysisClaim(run_id=run.id, claim_name="Wrongful Termination", claim_type="identified", folio_iri=iri, jurisdiction="California", confidence=0.8),
        AnalysisClaim(run_id=run.id, claim_name="wrongful termination", claim_type="identified", folio_iri=iri, jurisdiction="California", confidence=0.8),
        AnalysisClaim(run_id=run.id, claim_name="Wrongful Termination", claim_type="identified", folio_iri=iri, jurisdiction="California", confidence=0.8),
    ])
    await async_session.flush()

    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=LAW_FIRM_PROFILE
    )
    total_sections = sum(len(v) for v in ctx.claims_by_jurisdiction.values())
    assert total_sections == 1


# ---------------------------------------------------------------------------
# BUG-16 + BUG-14 -- question_gen logs on failure and dedups vs existing
# ---------------------------------------------------------------------------


async def test_question_gen_logs_on_llm_failure(async_session):
    """A swallowed LLM error is logged (diagnosable) but still returns 0 questions.

    Asserts on the module logger directly (not caplog): structlog reconfiguration
    by earlier tests in the full suite breaks caplog record propagation.
    """
    from unittest.mock import patch

    from app.services.analysis.stages import question_gen as qg_module
    from app.services.analysis.stages.question_gen import QuestionGenStage

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()
    iteration = AnalysisIteration(run_id=run.id, iteration_number=1, status="running")
    async_session.add(iteration)
    await async_session.flush()

    gap = AnalysisGap(run_id=run.id, gap_type="unsupported_element", description="missing proof", priority=1, status="open", iteration_found=1)
    async_session.add(gap)
    await async_session.flush()

    llm = SimpleNamespace(json_async=AsyncMock(side_effect=RuntimeError("boom")))
    stage = QuestionGenStage(llm_service=llm, db_session=async_session)

    with patch.object(qg_module, "logger", wraps=qg_module.logger) as mock_logger:
        result = await stage.execute(run, iteration, [gap])

    assert result["questions_generated"] == 0
    assert mock_logger.warning.called
    logged_msg = mock_logger.warning.call_args[0][0]
    assert "question_gen LLM call failed" in logged_msg


async def test_question_gen_dedups_against_all_existing(async_session):
    """Generated questions matching an existing (pending) question are skipped."""
    from app.services.analysis.schemas import (
        QuestionGenResult,
        QuestionGroup,
        QuestionSchema,
    )
    from app.services.analysis.stages.question_gen import QuestionGenStage

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()
    iteration = AnalysisIteration(run_id=run.id, iteration_number=2, status="running")
    async_session.add(iteration)
    await async_session.flush()

    gap = AnalysisGap(run_id=run.id, gap_type="unsupported_element", description="missing date", priority=1, status="open", iteration_found=1)
    async_session.add(gap)
    await async_session.flush()

    # An existing PENDING (not answered) question from a prior iteration.
    existing = FollowUpQuestion(run_id=run.id, question_text="When were you fired?", topic_group="timeline", status="pending", iteration_asked=1)
    async_session.add(existing)
    await async_session.flush()

    # LLM returns the same question (differently cased) plus one duplicated in-batch
    # and one genuinely new question.
    payload = QuestionGenResult(
        groups=[
            QuestionGroup(topic="timeline", questions=[
                QuestionSchema(question_text="when were you fired", priority=1),
                QuestionSchema(question_text="Do you have documents?", priority=2),
                QuestionSchema(question_text="Do you have documents?", priority=2),
            ]),
        ],
        total_questions=3,
    )
    llm = SimpleNamespace(json_async=AsyncMock(return_value=payload))
    stage = QuestionGenStage(llm_service=llm, db_session=async_session)

    result = await stage.execute(run, iteration, [gap], existing_questions=[existing])
    # Only the one genuinely-new question is persisted.
    assert result["questions_generated"] == 1


# ---------------------------------------------------------------------------
# RUB-10 -- LanguageAdapter invoked on the consumer path
# ---------------------------------------------------------------------------


def _ctx_with_prose():
    from datetime import datetime, timezone

    from app.services.output.schemas import (
        CIRACSection,
        GapReport,
        OutputContext,
        COURT_SELF_HELP_PROFILE,
    )

    section = CIRACSection(
        claim_id=1,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.8,
        jurisdiction="California",
        issue_statement="Whether the plaintiff was terminated in contravention of statutory public policy.",
        conclusion="Two of three elements are supported.",
    )
    return OutputContext(
        intake_id=1,
        run_id=1,
        org_id=1,
        matter_title="Test",
        generated_at=datetime.now(timezone.utc),
        claims_by_jurisdiction={"California": [section]},
        gap_report=GapReport(),
        executive_summary="The client likely has a viable claim.",
        profile=COURT_SELF_HELP_PROFILE,
    )


async def test_language_adapter_invoked_on_plain_profile():
    """adapt() calls the LLM and rewrites prose for the court_self_help (plain) profile."""
    from app.services.output.language_adapter import LanguageAdapter
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE

    ctx = _ctx_with_prose()
    llm = SimpleNamespace(acomplete=AsyncMock(return_value="Plain words."))
    adapted = await LanguageAdapter().adapt(ctx, COURT_SELF_HELP_PROFILE, llm)

    assert llm.acomplete.await_count >= 1
    assert adapted.executive_summary == "Plain words."
    assert adapted.claims_by_jurisdiction["California"][0].issue_statement == "Plain words."


async def test_language_adapter_skips_professional_profile():
    """adapt() makes no LLM call for the professional attorney memo."""
    from app.services.output.language_adapter import LanguageAdapter
    from app.services.output.schemas import LAW_FIRM_PROFILE

    ctx = _ctx_with_prose()
    llm = SimpleNamespace(acomplete=AsyncMock(return_value="Plain words."))
    adapted = await LanguageAdapter().adapt(ctx, LAW_FIRM_PROFILE, llm)

    assert llm.acomplete.await_count == 0
    # Prose unchanged.
    assert adapted.executive_summary == "The client likely has a viable claim."


async def test_plain_prompt_targets_sixth_grade():
    """The plain-language system prompt targets ~6th grade (RUB-10)."""
    from app.services.output.language_adapter import _SYSTEM_PROMPTS

    assert "6th grade" in _SYSTEM_PROMPTS["plain"]


# ---------------------------------------------------------------------------
# BUG-19 -- rewriter refusal / clarification must NOT leak into memos/PDFs
# ---------------------------------------------------------------------------


async def test_language_adapter_fails_closed_on_refusal():
    """BUG-19: when the rewriter LLM returns a refusal/clarification instead of a
    rewrite, adapt() must keep the ORIGINAL prose, never the meta-commentary.

    Observed leaks in client PDFs: "It seems there was an issue with the text
    provided. Please provide the legal text you'd like rewritten." and
    "I'm sorry, but I cannot assist with that." — repeated as claim conclusions.
    """
    from app.services.output.language_adapter import LanguageAdapter
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE

    ctx = _ctx_with_prose()
    original_issue = ctx.claims_by_jurisdiction["California"][0].issue_statement
    original_summary = ctx.executive_summary
    refusal = (
        "It seems there was an issue with the text provided. "
        "Please provide the legal text you'd like rewritten."
    )
    llm = SimpleNamespace(acomplete=AsyncMock(return_value=refusal))
    adapted = await LanguageAdapter().adapt(ctx, COURT_SELF_HELP_PROFILE, llm)

    # The refusal text must appear NOWHERE in the adapted context.
    assert adapted.executive_summary == original_summary
    assert adapted.claims_by_jurisdiction["California"][0].issue_statement == original_issue
    assert "issue with the text" not in adapted.executive_summary.lower()
    assert (
        "issue with the text"
        not in adapted.claims_by_jurisdiction["California"][0].issue_statement.lower()
    )


async def test_language_adapter_fails_closed_on_sorry_refusal():
    """BUG-19: the "I'm sorry, but I cannot assist" refusal also fails closed."""
    from app.services.output.language_adapter import LanguageAdapter
    from app.services.output.schemas import COURT_SELF_HELP_PROFILE

    ctx = _ctx_with_prose()
    original_issue = ctx.claims_by_jurisdiction["California"][0].issue_statement
    llm = SimpleNamespace(
        acomplete=AsyncMock(return_value="I'm sorry, but I cannot assist with that.")
    )
    adapted = await LanguageAdapter().adapt(ctx, COURT_SELF_HELP_PROFILE, llm)
    assert adapted.claims_by_jurisdiction["California"][0].issue_statement == original_issue


async def test_looks_like_refusal_helper():
    """The refusal detector flags meta-commentary but passes genuine rewrites."""
    from app.services.output.language_adapter import _looks_like_refusal

    assert _looks_like_refusal(
        "It seems there was an issue with the text provided. Please provide the legal text."
    )
    assert _looks_like_refusal("I'm sorry, but I cannot assist with that.")
    assert not _looks_like_refusal(
        "You may have a strong claim. The landlord did not fix the heat. That breaks the law."
    )


# ---------------------------------------------------------------------------
# q10 -- memo claim display: top-7 cap + relation grouping
# ---------------------------------------------------------------------------


async def _seed_bare_run(session):
    """Create a bare intake + converged run (no narrative) for claim tests."""
    intake = Intake(org_id=1, status="active", metadata_json={})
    session.add(intake)
    await session.flush()
    run = AnalysisRun(intake_id=intake.id, status="converged", trigger_type="manual")
    session.add(run)
    await session.flush()
    return intake, run


async def test_memo_caps_full_sections_at_seven(async_session):
    """>7 claims -> exactly 7 full sections; the rest land in the compact list."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE
    from app.services.output.template_engine import TemplateEngine

    intake, run = await _seed_bare_run(async_session)
    for i in range(10):
        async_session.add(
            AnalysisClaim(
                run_id=run.id,
                claim_name=f"Claim {chr(65 + i)}",
                claim_type="identified",
                jurisdiction="California",
                confidence=0.95 - i * 0.05,
            )
        )
    await async_session.flush()

    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=LAW_FIRM_PROFILE
    )

    sections = ctx.claims_by_jurisdiction["California"]
    assert len(sections) == 7
    # Ranked by confidence desc: A..G render fully; H, I, J overflow.
    assert [s.claim_name for s in sections] == [f"Claim {c}" for c in "ABCDEFG"]
    extra = ctx.additional_claims_by_jurisdiction["California"]
    assert [a.claim_name for a in extra] == ["Claim H", "Claim I", "Claim J"]

    memo = TemplateEngine().render_full(ctx, LAW_FIRM_PROFILE)
    assert "More possible issues (show more)" in memo
    assert "### Claim G" in memo
    assert "### Claim H" not in memo
    assert "**Claim H**: 60% confidence" in memo


async def test_adjacency_child_renders_grouped_under_parent(async_session):
    """An adjacency-discovered claim nests under its parent, not interleaved."""
    from app.services.output.data_assembler import DataAssembler
    from app.services.output.schemas import LAW_FIRM_PROFILE
    from app.services.output.template_engine import TemplateEngine

    intake, run = await _seed_bare_run(async_session)
    async_session.add_all(
        [
            AnalysisClaim(
                run_id=run.id,
                claim_name="Wrongful Termination",
                claim_type="identified",
                jurisdiction="California",
                confidence=0.9,
            ),
            AnalysisClaim(
                run_id=run.id,
                claim_name="Breach of Contract",
                claim_type="identified",
                jurisdiction="California",
                confidence=0.5,
            ),
            # Exploration-discovered adjacency claim: no jurisdiction, parent
            # linkage only via the rationale text (mirrors explore.py output).
            AnalysisClaim(
                run_id=run.id,
                claim_name="Retaliation",
                claim_type="discovered",
                confidence=0.7,
                is_potential=True,
                rationale=(
                    "Discovered via FOLIO ontology traversal from "
                    "Wrongful Termination (depth 1)"
                ),
                metadata_json={"source_layer": "folio_adjacency", "exploration_round": 1},
            ),
        ]
    )
    await async_session.flush()

    ctx = await DataAssembler(async_session).assemble(
        run_id=run.id, intake_id=intake.id, profile=LAW_FIRM_PROFILE
    )

    sections = ctx.claims_by_jurisdiction["California"]
    assert [s.claim_name for s in sections] == [
        "Wrongful Termination",
        "Breach of Contract",
    ]
    assert [c.claim_name for c in sections[0].children] == ["Retaliation"]
    assert sections[0].children[0].parent_claim_name == "Wrongful Termination"
    # The child moved out of the jurisdictionless "General" bucket entirely.
    assert "General" not in ctx.claims_by_jurisdiction

    memo = TemplateEngine().render_full(ctx, LAW_FIRM_PROFILE)
    i_parent = memo.index("### Wrongful Termination")
    i_child = memo.index("### Retaliation")
    i_sibling = memo.index("### Breach of Contract")
    assert i_parent < i_child < i_sibling
    assert "**Related to:** Wrongful Termination" in memo
