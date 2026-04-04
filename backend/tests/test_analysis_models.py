"""Tests for analysis pipeline DB models.

Verifies that all 8 analysis models can be created in the database
and that OrganizationConfig accepts the new analysis_config_json column.
"""

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_analysis_run_create(async_session):
    """AnalysisRun can be created with status, trigger_type, max_iterations."""
    from app.models.analysis import AnalysisRun

    run = AnalysisRun(
        intake_id=1,
        status="running",
        trigger_type="manual",
        current_iteration_number=0,
        max_iterations=10,
    )
    async_session.add(run)
    await async_session.flush()

    assert run.id is not None
    assert run.status == "running"
    assert run.trigger_type == "manual"
    assert run.max_iterations == 10
    assert run.current_iteration_number == 0
    assert run.convergence_score is None
    assert run.convergence_config_json is None


async def test_analysis_iteration_create(async_session):
    """AnalysisIteration links to run_id with iteration_number and convergence_signals_json."""
    from app.models.analysis import AnalysisIteration, AnalysisRun

    run = AnalysisRun(intake_id=1, status="running", trigger_type="auto")
    async_session.add(run)
    await async_session.flush()

    iteration = AnalysisIteration(
        run_id=run.id,
        iteration_number=1,
        status="running",
        converged=False,
        convergence_signals_json={"coverage_pct": 0.45, "confidence_delta": 0.12},
    )
    async_session.add(iteration)
    await async_session.flush()

    assert iteration.id is not None
    assert iteration.run_id == run.id
    assert iteration.iteration_number == 1
    assert iteration.converged is False
    assert iteration.convergence_signals_json["coverage_pct"] == 0.45


async def test_analysis_stage_create(async_session):
    """AnalysisStage links to iteration_id with stage_name, result_json, audit_json, schema_version."""
    from app.models.analysis import AnalysisIteration, AnalysisRun, AnalysisStage

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    iteration = AnalysisIteration(run_id=run.id, iteration_number=1)
    async_session.add(iteration)
    await async_session.flush()

    stage = AnalysisStage(
        iteration_id=iteration.id,
        stage_name="issue_spot",
        status="completed",
        schema_version=1,
        result_json={"claims": [{"name": "wrongful_termination"}]},
        audit_json={"llm_call_id": "abc123", "tokens_used": 500},
        duration_ms=1234,
    )
    async_session.add(stage)
    await async_session.flush()

    assert stage.id is not None
    assert stage.iteration_id == iteration.id
    assert stage.stage_name == "issue_spot"
    assert stage.schema_version == 1
    assert stage.result_json["claims"][0]["name"] == "wrongful_termination"
    assert stage.audit_json["llm_call_id"] == "abc123"
    assert stage.duration_ms == 1234


async def test_analysis_claim_create(async_session):
    """AnalysisClaim stores claim_name, claim_type, folio_iri, jurisdiction, is_potential flag."""
    from app.models.analysis import AnalysisClaim, AnalysisRun

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    claim = AnalysisClaim(
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
    async_session.add(claim)
    await async_session.flush()

    assert claim.id is not None
    assert claim.claim_name == "Wrongful Termination"
    assert claim.folio_iri == "https://folio.openlegalstandard.org/objective001"
    assert claim.is_potential is False
    assert claim.iteration_discovered == 1


async def test_analysis_claim_potential_flag(async_session):
    """AnalysisClaim is_potential defaults to False per D-08."""
    from app.models.analysis import AnalysisClaim, AnalysisRun

    run = AnalysisRun(intake_id=1, status="running", trigger_type="auto")
    async_session.add(run)
    await async_session.flush()

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Workplace Harassment",
        claim_type="discovered",
        confidence=0.6,
        is_potential=True,
    )
    async_session.add(claim)
    await async_session.flush()

    assert claim.is_potential is True


async def test_claim_element_create(async_session):
    """ClaimElement links to claim_id with element_name, is_satisfied, satisfaction_confidence."""
    from app.models.analysis import AnalysisClaim, AnalysisRun, ClaimElement

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.85,
    )
    async_session.add(claim)
    await async_session.flush()

    element = ClaimElement(
        claim_id=claim.id,
        element_name="Employment Relationship",
        element_description="Plaintiff must prove an employment relationship existed",
        is_satisfied=True,
        satisfaction_confidence=0.92,
        jurisdiction="California",
    )
    async_session.add(element)
    await async_session.flush()

    assert element.id is not None
    assert element.claim_id == claim.id
    assert element.element_name == "Employment Relationship"
    assert element.is_satisfied is True
    assert element.satisfaction_confidence == 0.92


async def test_fact_claim_mapping_create(async_session):
    """FactClaimMapping links fact_id to claim_id/element_id with composite confidence."""
    from app.models.analysis import AnalysisClaim, AnalysisRun, ClaimElement, FactClaimMapping

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.85,
    )
    async_session.add(claim)
    await async_session.flush()

    element = ClaimElement(
        claim_id=claim.id,
        element_name="Termination Without Cause",
        is_satisfied=False,
    )
    async_session.add(element)
    await async_session.flush()

    mapping = FactClaimMapping(
        fact_id=42,
        claim_id=claim.id,
        element_id=element.id,
        confidence=0.78,
        llm_confidence=0.80,
        concept_confidence=0.75,
        fact_confidence=0.82,
        mapping_rationale="Consumer stated they were fired without warning",
        iteration_number=1,
    )
    async_session.add(mapping)
    await async_session.flush()

    assert mapping.id is not None
    assert mapping.fact_id == 42
    assert mapping.claim_id == claim.id
    assert mapping.element_id == element.id
    assert mapping.llm_confidence == 0.80
    assert mapping.concept_confidence == 0.75
    assert mapping.fact_confidence == 0.82
    assert mapping.confidence == 0.78


async def test_analysis_gap_create(async_session):
    """AnalysisGap has gap_type, status, priority."""
    from app.models.analysis import AnalysisClaim, AnalysisGap, AnalysisRun

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    claim = AnalysisClaim(
        run_id=run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.85,
    )
    async_session.add(claim)
    await async_session.flush()

    gap = AnalysisGap(
        run_id=run.id,
        gap_type="unsupported_element",
        claim_id=claim.id,
        description="No facts support the 'termination without cause' element",
        priority=1,
        status="open",
        iteration_found=1,
    )
    async_session.add(gap)
    await async_session.flush()

    assert gap.id is not None
    assert gap.gap_type == "unsupported_element"
    assert gap.status == "open"
    assert gap.priority == 1
    assert gap.iteration_found == 1
    assert gap.iteration_resolved is None


async def test_analysis_gap_types(async_session):
    """AnalysisGap supports all four gap types."""
    from app.models.analysis import AnalysisGap, AnalysisRun

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    gap_types = [
        "unsupported_element",
        "unexplored_claim",
        "weak_mapping",
        "procedural_requirement",
    ]
    for gap_type in gap_types:
        gap = AnalysisGap(
            run_id=run.id,
            gap_type=gap_type,
            description=f"Test gap of type {gap_type}",
            priority=0,
            status="open",
            iteration_found=1,
        )
        async_session.add(gap)

    await async_session.flush()

    result = await async_session.execute(
        select(AnalysisGap).where(AnalysisGap.run_id == run.id)
    )
    gaps = result.scalars().all()
    assert len(gaps) == 4
    assert set(g.gap_type for g in gaps) == set(gap_types)


async def test_followup_question_create(async_session):
    """FollowUpQuestion has question_text, topic_group, priority, rationale, status."""
    from app.models.analysis import AnalysisRun, FollowUpQuestion

    run = AnalysisRun(intake_id=1, status="running", trigger_type="manual")
    async_session.add(run)
    await async_session.flush()

    question = FollowUpQuestion(
        run_id=run.id,
        gap_id=None,
        question_text="When exactly were you terminated from your position?",
        topic_group="timeline",
        priority=1,
        rationale="Need termination date to establish statute of limitations",
        status="pending",
        answer_message_id=None,
        iteration_asked=1,
    )
    async_session.add(question)
    await async_session.flush()

    assert question.id is not None
    assert question.topic_group == "timeline"
    assert question.priority == 1
    assert question.status == "pending"
    assert question.answer_message_id is None


async def test_organization_config_analysis_json(async_session):
    """OrganizationConfig accepts analysis_config_json column."""
    from app.models.organization import OrganizationConfig

    config = OrganizationConfig(
        org_id=999,
        llm_data_policy="cloud_optout",
        analysis_config_json={
            "auto_trigger_enabled": True,
            "auto_trigger_fact_threshold": 5,
            "max_iterations": 10,
            "convergence_threshold": 0.75,
            "convergence_weights": {
                "coverage": 0.30,
                "confidence_plateau": 0.20,
                "iteration_cap": 0.10,
                "user_fatigue": 0.15,
                "diminishing_gaps": 0.25,
            },
        },
    )
    async_session.add(config)
    await async_session.flush()

    assert config.id is not None
    assert config.analysis_config_json["auto_trigger_enabled"] is True
    assert config.analysis_config_json["max_iterations"] == 10
    assert config.analysis_config_json["convergence_weights"]["coverage"] == 0.30


async def test_models_reexported(async_session):
    """All 8 analysis models are importable from app.models."""
    from app.models import (
        AnalysisClaim,
        AnalysisGap,
        AnalysisIteration,
        AnalysisRun,
        AnalysisStage,
        ClaimElement,
        FactClaimMapping,
        FollowUpQuestion,
    )

    # Verify they are the correct classes
    assert AnalysisRun.__tablename__ == "analysis_runs"
    assert AnalysisIteration.__tablename__ == "analysis_iterations"
    assert AnalysisStage.__tablename__ == "analysis_stages"
    assert AnalysisClaim.__tablename__ == "analysis_claims"
    assert ClaimElement.__tablename__ == "claim_elements"
    assert FactClaimMapping.__tablename__ == "fact_claim_mappings"
    assert AnalysisGap.__tablename__ == "analysis_gaps"
    assert FollowUpQuestion.__tablename__ == "follow_up_questions"
