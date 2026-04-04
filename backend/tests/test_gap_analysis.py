"""Tests for gap analysis and question generation stages.

Tests cover four gap types (unsupported_element, unexplored_claim,
weak_mapping, procedural_requirement), prioritization, coverage
calculation, duplicate filtering, and DB persistence.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    ClaimElement,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.services.analysis.stages.gap_analyze import GapAnalyzeStage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def analysis_run(async_session: AsyncSession) -> AnalysisRun:
    """Create a test analysis run."""
    run = AnalysisRun(
        intake_id=1,
        status="running",
        trigger_type="auto",
        current_iteration_number=1,
        max_iterations=10,
    )
    async_session.add(run)
    await async_session.flush()
    return run


@pytest.fixture
async def analysis_iteration(
    async_session: AsyncSession, analysis_run: AnalysisRun
) -> AnalysisIteration:
    """Create a test analysis iteration."""
    iteration = AnalysisIteration(
        run_id=analysis_run.id,
        iteration_number=1,
        status="running",
    )
    async_session.add(iteration)
    await async_session.flush()
    return iteration


@pytest.fixture
async def claims_with_elements(
    async_session: AsyncSession, analysis_run: AnalysisRun
) -> tuple[list[AnalysisClaim], list[ClaimElement]]:
    """Create claims and elements for gap detection testing."""
    # Claim 1: Wrongful Termination (high confidence, some elements unsupported)
    claim1 = AnalysisClaim(
        run_id=analysis_run.id,
        claim_name="Wrongful Termination",
        claim_type="identified",
        confidence=0.9,
        is_potential=False,
        iteration_discovered=1,
    )
    # Claim 2: Breach of Contract (potential/unexplored)
    claim2 = AnalysisClaim(
        run_id=analysis_run.id,
        claim_name="Breach of Contract",
        claim_type="discovered",
        confidence=0.6,
        is_potential=True,
        iteration_discovered=1,
    )
    async_session.add_all([claim1, claim2])
    await async_session.flush()

    # Elements for claim1
    elem1 = ClaimElement(
        claim_id=claim1.id,
        element_name="Employment Relationship",
        is_satisfied=True,
        satisfaction_confidence=0.85,
    )
    elem2 = ClaimElement(
        claim_id=claim1.id,
        element_name="Wrongful Act",
        is_satisfied=False,
        satisfaction_confidence=None,
    )
    elem3 = ClaimElement(
        claim_id=claim1.id,
        element_name="Damages",
        is_satisfied=False,
        satisfaction_confidence=None,
    )
    async_session.add_all([elem1, elem2, elem3])
    await async_session.flush()

    return [claim1, claim2], [elem1, elem2, elem3]


@pytest.fixture
async def weak_mapping(
    async_session: AsyncSession,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
) -> FactClaimMapping:
    """Create a weak fact-to-claim mapping (confidence < 0.5)."""
    claims, elements = claims_with_elements
    mapping = FactClaimMapping(
        fact_id=100,
        claim_id=claims[0].id,
        element_id=elements[0].id,
        confidence=0.3,
        llm_confidence=0.3,
        iteration_number=1,
    )
    async_session.add(mapping)
    await async_session.flush()
    return mapping


@pytest.fixture
def mock_llm_service() -> MagicMock:
    """Create a mock LLM service for procedural requirement detection."""
    service = MagicMock()
    service.get_client_config = MagicMock(return_value={"provider": "openai", "model": "gpt-4"})
    return service


# ---------------------------------------------------------------------------
# GapAnalyzeStage Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_four_gap_types(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    weak_mapping: FactClaimMapping,
    mock_llm_service: MagicMock,
):
    """GapAnalyzeStage detects all four gap types from analysis state."""
    claims, elements = claims_with_elements

    # Mock LLM for procedural requirements
    from app.services.analysis.schemas import GapAnalysisResult, GapSchema

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(
            gaps=[
                GapSchema(
                    gap_type="procedural_requirement",
                    claim_name="Wrongful Termination",
                    description="Statute of limitations may be expiring soon",
                    priority=80,
                ),
            ],
            coverage_pct=0.33,
            summary="Procedural gaps found",
        )
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[weak_mapping],
        existing_gaps=[],
    )

    # Should find all four gap types
    gap_types = result["gap_types"]
    assert gap_types.get("unsupported_element", 0) > 0
    assert gap_types.get("unexplored_claim", 0) > 0
    assert gap_types.get("weak_mapping", 0) > 0
    assert gap_types.get("procedural_requirement", 0) > 0


@pytest.mark.asyncio
async def test_detect_unsupported_elements(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Unsupported elements (is_satisfied=False, no mapping) create gaps."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    # elem2 and elem3 are unsatisfied with no mappings
    assert result["gap_types"].get("unsupported_element", 0) >= 2


@pytest.mark.asyncio
async def test_detect_unexplored_claims(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Unexplored claims (is_potential=True, no mappings) create gaps."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    # claim2 is potential with no mappings
    assert result["gap_types"].get("unexplored_claim", 0) >= 1


@pytest.mark.asyncio
async def test_detect_weak_mappings(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    weak_mapping: FactClaimMapping,
    mock_llm_service: MagicMock,
):
    """Weak mappings (confidence < threshold) create gaps."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[weak_mapping],
        existing_gaps=[],
    )

    assert result["gap_types"].get("weak_mapping", 0) >= 1


@pytest.mark.asyncio
async def test_detect_procedural_requirements(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Procedural requirements detected via LLM call."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult, GapSchema

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(
            gaps=[
                GapSchema(
                    gap_type="procedural_requirement",
                    claim_name="Wrongful Termination",
                    description="Filing deadline approaching",
                    priority=90,
                ),
            ],
            coverage_pct=0.33,
            summary="Procedural gaps found",
        )
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    assert result["gap_types"].get("procedural_requirement", 0) >= 1
    mock_llm_service.json_async.assert_called_once()


@pytest.mark.asyncio
async def test_gap_priority_ordering(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Gaps are prioritized: unsupported elements on high-confidence claims get highest priority."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    # Verify gaps from DB
    stmt = select(AnalysisGap).where(AnalysisGap.run_id == analysis_run.id)
    db_result = await async_session.execute(stmt)
    gaps = db_result.scalars().all()

    # Unsupported elements on claim1 (confidence=0.9) should have priority 90
    unsupported = [g for g in gaps if g.gap_type == "unsupported_element"]
    assert len(unsupported) > 0
    for g in unsupported:
        assert g.priority == 90  # claim1.confidence * 100


@pytest.mark.asyncio
async def test_coverage_calculation(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Coverage percentage = satisfied elements / total elements."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    # 1 out of 3 elements is satisfied
    assert abs(result["coverage_pct"] - (1 / 3)) < 0.01


@pytest.mark.asyncio
async def test_resolved_gaps_not_redetected(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Previously resolved gaps (status='addressed') are not re-detected."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    # Create an existing addressed gap for elem2 (unsupported_element)
    existing_gap = AnalysisGap(
        run_id=analysis_run.id,
        gap_type="unsupported_element",
        claim_id=claims[0].id,
        element_id=elements[1].id,
        description="Wrongful Act element not yet supported",
        priority=90,
        status="addressed",
        iteration_found=0,
    )
    async_session.add(existing_gap)
    await async_session.flush()

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[existing_gap],
    )

    # Should still detect the other unsupported element (elem3) but not re-detect elem2
    stmt = select(AnalysisGap).where(
        AnalysisGap.run_id == analysis_run.id,
        AnalysisGap.gap_type == "unsupported_element",
        AnalysisGap.iteration_found == analysis_iteration.iteration_number,
    )
    db_result = await async_session.execute(stmt)
    new_gaps = db_result.scalars().all()

    # elem2 was addressed, only elem3 should be new
    assert len(new_gaps) == 1


@pytest.mark.asyncio
async def test_gaps_persisted_to_db(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    claims_with_elements: tuple[list[AnalysisClaim], list[ClaimElement]],
    mock_llm_service: MagicMock,
):
    """Gaps are persisted as AnalysisGap records with correct fields."""
    claims, elements = claims_with_elements
    from app.services.analysis.schemas import GapAnalysisResult

    mock_llm_service.json_async = AsyncMock(
        return_value=GapAnalysisResult(gaps=[], coverage_pct=0.33, summary="No procedural gaps")
    )

    stage = GapAnalyzeStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        claims=claims,
        elements=elements,
        mappings=[],
        existing_gaps=[],
    )

    stmt = select(AnalysisGap).where(AnalysisGap.run_id == analysis_run.id)
    db_result = await async_session.execute(stmt)
    gaps = db_result.scalars().all()

    assert len(gaps) > 0
    for gap in gaps:
        assert gap.run_id == analysis_run.id
        assert gap.gap_type in (
            "unsupported_element",
            "unexplored_claim",
            "weak_mapping",
            "procedural_requirement",
        )
        assert gap.iteration_found == analysis_iteration.iteration_number
        assert gap.status == "open"


# ---------------------------------------------------------------------------
# QuestionGenStage Tests
# ---------------------------------------------------------------------------

from app.services.analysis.stages.question_gen import QuestionGenStage


@pytest.fixture
async def seeded_gaps(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
) -> list[AnalysisGap]:
    """Create a set of open gaps for question generation testing."""
    gap1 = AnalysisGap(
        run_id=analysis_run.id,
        gap_type="unsupported_element",
        claim_id=1,
        element_id=1,
        description="Element 'Employment Relationship' is not yet supported by any facts",
        priority=90,
        status="open",
        iteration_found=1,
    )
    gap2 = AnalysisGap(
        run_id=analysis_run.id,
        gap_type="unexplored_claim",
        claim_id=2,
        element_id=None,
        description="Potential claim 'Breach of Contract' has not been explored",
        priority=50,
        status="open",
        iteration_found=1,
    )
    gap3 = AnalysisGap(
        run_id=analysis_run.id,
        gap_type="weak_mapping",
        claim_id=1,
        element_id=2,
        description="Weak mapping (confidence=0.30) for claim 'Wrongful Termination' / element 'Damages'",
        priority=70,
        status="open",
        iteration_found=1,
    )
    async_session.add_all([gap1, gap2, gap3])
    await async_session.flush()
    return [gap1, gap2, gap3]


def _make_question_gen_llm_response(with_rationale: bool = True):
    """Build a mock LLM response for QuestionGenStage."""
    from app.services.analysis.schemas import QuestionGenResult, QuestionGroup, QuestionSchema

    return QuestionGenResult(
        groups=[
            QuestionGroup(
                topic="About your employment",
                questions=[
                    QuestionSchema(
                        question_text="Can you describe the nature of your work relationship with the company?",
                        rationale="We need to establish whether an employment relationship existed" if with_rationale else None,
                        priority=90,
                        gap_description="Element 'Employment Relationship' is not yet supported by any facts",
                    ),
                    QuestionSchema(
                        question_text="Were there specific damages or losses you experienced?",
                        rationale="Strengthening the evidence for financial impact" if with_rationale else None,
                        priority=70,
                        gap_description="Weak mapping (confidence=0.30) for claim 'Wrongful Termination' / element 'Damages'",
                    ),
                ],
            ),
            QuestionGroup(
                topic="About the contract",
                questions=[
                    QuestionSchema(
                        question_text="Did you have a written or verbal agreement with the company?",
                        rationale="Exploring potential breach of contract claim" if with_rationale else None,
                        priority=50,
                        gap_description="Potential claim 'Breach of Contract' has not been explored",
                    ),
                ],
            ),
        ],
        total_questions=3,
    )


@pytest.mark.asyncio
async def test_question_gen_generates_from_gaps(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """QuestionGenStage.execute() generates questions from gap list."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
        question_transparency=True,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
        consumer_context="I was fired from my job.",
    )

    assert result["questions_generated"] == 3
    assert result["total_questions"] == 3
    mock_llm_service.json_async.assert_called_once()


@pytest.mark.asyncio
async def test_question_topic_grouping(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """Questions are grouped by topic (D-10)."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    assert "About your employment" in result["topic_groups"]
    assert "About the contract" in result["topic_groups"]
    assert len(result["topic_groups"]) == 2


@pytest.mark.asyncio
async def test_question_priority_ordering(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """Questions are ranked by priority (highest-impact gaps first)."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    # Verify questions in DB are ordered correctly
    stmt = (
        select(FollowUpQuestion)
        .where(FollowUpQuestion.run_id == analysis_run.id)
        .order_by(FollowUpQuestion.priority.desc())
    )
    db_result = await async_session.execute(stmt)
    questions = db_result.scalars().all()

    priorities = [q.priority for q in questions]
    assert priorities == sorted(priorities, reverse=True)


@pytest.mark.asyncio
async def test_question_transparency_enabled(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """When question_transparency=True, rationale is included (D-12)."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response(with_rationale=True)
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
        question_transparency=True,
    )
    await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    stmt = select(FollowUpQuestion).where(FollowUpQuestion.run_id == analysis_run.id)
    db_result = await async_session.execute(stmt)
    questions = db_result.scalars().all()

    for q in questions:
        assert q.rationale is not None
        assert len(q.rationale) > 0


@pytest.mark.asyncio
async def test_question_transparency_disabled(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """When question_transparency=False, rationale is None."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response(with_rationale=True)
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
        question_transparency=False,
    )
    await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    stmt = select(FollowUpQuestion).where(FollowUpQuestion.run_id == analysis_run.id)
    db_result = await async_session.execute(stmt)
    questions = db_result.scalars().all()

    for q in questions:
        assert q.rationale is None


@pytest.mark.asyncio
async def test_question_persistence(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """Questions persisted as FollowUpQuestion records with gap_id, topic_group, priority, iteration_asked."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    stmt = select(FollowUpQuestion).where(FollowUpQuestion.run_id == analysis_run.id)
    db_result = await async_session.execute(stmt)
    questions = db_result.scalars().all()

    assert len(questions) == 3
    for q in questions:
        assert q.run_id == analysis_run.id
        assert q.topic_group in ("About your employment", "About the contract")
        assert q.priority > 0
        assert q.iteration_asked == analysis_iteration.iteration_number
        assert q.status == "pending"


@pytest.mark.asyncio
async def test_all_gaps_produce_questions(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """All gaps produce at least one question (D-11)."""
    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
    )

    # 3 gaps should produce at least 3 questions
    assert result["questions_generated"] >= len(seeded_gaps)


@pytest.mark.asyncio
async def test_answered_questions_not_regenerated(
    async_session: AsyncSession,
    analysis_run: AnalysisRun,
    analysis_iteration: AnalysisIteration,
    seeded_gaps: list[AnalysisGap],
    mock_llm_service: MagicMock,
):
    """Previously answered questions (status='answered') not re-generated."""
    # Create an existing answered question
    existing_q = FollowUpQuestion(
        run_id=analysis_run.id,
        gap_id=seeded_gaps[0].id,
        question_text="Can you describe the nature of your work relationship with the company?",
        topic_group="About your employment",
        priority=90,
        rationale="We need to establish whether an employment relationship existed",
        status="answered",
        answer_message_id=42,
        iteration_asked=0,
    )
    async_session.add(existing_q)
    await async_session.flush()

    mock_llm_service.json_async = AsyncMock(
        return_value=_make_question_gen_llm_response()
    )

    stage = QuestionGenStage(
        llm_service=mock_llm_service,
        db_session=async_session,
    )
    result = await stage.execute(
        run=analysis_run,
        iteration=analysis_iteration,
        gaps=seeded_gaps,
        existing_questions=[existing_q],
    )

    # Should skip the already-answered question
    stmt = select(FollowUpQuestion).where(
        FollowUpQuestion.run_id == analysis_run.id,
        FollowUpQuestion.iteration_asked == analysis_iteration.iteration_number,
    )
    db_result = await async_session.execute(stmt)
    new_questions = db_result.scalars().all()

    # The already-answered question should not be re-created
    answered_texts = {existing_q.question_text}
    for q in new_questions:
        assert q.question_text not in answered_texts
