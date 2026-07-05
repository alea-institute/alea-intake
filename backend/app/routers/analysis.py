"""Analysis API endpoints: trigger, status, results, override, audit trail.

REST endpoints for manual analysis triggering (202 Accepted), status checking,
results retrieval, convergence override, and full audit trail. All endpoints
are scoped to a specific intake_id.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    AnalysisStage,
    ClaimElement,
    Deadline,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact, FactSourceSpan
from app.models.intake import IntakeSession, Message
from app.models.user import User
from app.schemas.visualization import (
    VisualizationClaim,
    VisualizationElement,
    VisualizationFact,
    VisualizationGap,
    VisualizationMapping,
    VisualizationMessage,
    VisualizationResponse,
    VisualizationSourceSpan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


def _get_org_id(request: Request) -> int:
    """Extract org_id from tenant context. Default to 1 for testing."""
    return getattr(request.state, "org_id", 1)


@router.post("/{intake_id}/analyze", status_code=202)
async def trigger_analysis(
    intake_id: int,
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Manual analysis trigger. Returns 202 Accepted with run_id.

    Creates or returns an existing running analysis for this intake.
    The analysis runs in the background via the orchestrator.
    """
    from app.services.analysis.orchestrator import AnalysisOrchestrator
    from app.services.analysis.trigger import AnalysisTrigger
    from app.services.extraction.backfill import backfill_intake_facts
    from app.services.llm_service import LLMService

    llm_service = LLMService()

    # Resolve FOLIO + embedding singletons (loaded at startup) for concept
    # resolution during extraction; degrade gracefully if unavailable (e.g. tests).
    folio = None
    embedding_service = None
    try:
        from app.services.folio.folio_service import get_folio

        folio = get_folio()
    except Exception:  # pragma: no cover - startup-dependent
        logger.warning("FOLIO unavailable for extraction; skipping concept resolution", exc_info=True)
    try:
        from app.services.embedding.service import EmbeddingService

        embedding_service = EmbeddingService.get_instance()
    except Exception:  # pragma: no cover - startup-dependent
        logger.warning("EmbeddingService unavailable for extraction", exc_info=True)

    # Backfill facts from ingested messages before analysis. Without this the
    # orchestrator's _load_facts() returns [] and analysis yields nothing.
    try:
        n_facts = await backfill_intake_facts(
            db, intake_id, llm_service, folio=folio, embedding_service=embedding_service
        )
        logger.info("Pre-analysis fact backfill created %d facts for intake %d", n_facts, intake_id)
    except Exception:
        logger.warning("Pre-analysis fact backfill failed for intake %d", intake_id, exc_info=True)

    orchestrator = AnalysisOrchestrator(
        db_session=db,
        llm_service=llm_service,
        folio=folio,
        embedding_service=embedding_service,
    )
    trigger = AnalysisTrigger(db_session=db, orchestrator=orchestrator)

    run = await trigger.manual_trigger(intake_id=intake_id, session_id=0)

    # Detect + hedge time-sensitive deadlines / SOL for this run. Runs after the
    # run exists (so Deadline rows carry run_id) and degrades gracefully -- an
    # LLM/parse failure yields zero deadlines and never fails the analysis.
    try:
        from app.services.analysis.stages.deadline_detect import DeadlineDetectStage

        deadline_stage = DeadlineDetectStage(llm_service=llm_service, db_session=db)
        deadlines = await deadline_stage.detect_and_persist(
            intake_id=intake_id, run_id=run.id
        )
        logger.info("Deadline detection produced %d deadlines for intake %d", len(deadlines), intake_id)
    except Exception:
        logger.warning("Deadline detection failed for intake %d", intake_id, exc_info=True)

    return {
        "run_id": run.id,
        "status": run.status,
        "message": "Analysis triggered",
    }


@router.get("/{intake_id}/status")
async def get_analysis_status(
    intake_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Get current analysis run status: iteration, stage, convergence score, progress %."""
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.intake_id == intake_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()

    if run is None:
        raise HTTPException(status_code=404, detail="No analysis run found for this intake")

    # Get latest stage info
    latest_stage = None
    iterations_result = await db.execute(
        select(AnalysisIteration)
        .where(AnalysisIteration.run_id == run.id)
        .order_by(AnalysisIteration.iteration_number.desc())
        .limit(1)
    )
    latest_iteration = iterations_result.scalars().first()

    if latest_iteration:
        stages_result = await db.execute(
            select(AnalysisStage)
            .where(AnalysisStage.iteration_id == latest_iteration.id)
            .order_by(AnalysisStage.id.desc())
            .limit(1)
        )
        latest_stage = stages_result.scalars().first()

    progress_pct = 0
    if run.max_iterations > 0:
        progress_pct = int((run.current_iteration_number / run.max_iterations) * 100)

    return {
        "run_id": run.id,
        "status": run.status,
        "iteration": run.current_iteration_number,
        "max_iterations": run.max_iterations,
        "convergence_score": run.convergence_score,
        "progress_pct": progress_pct,
        "latest_stage": latest_stage.stage_name if latest_stage else None,
    }


@router.get("/{intake_id}/results")
async def get_analysis_results(
    intake_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Get analysis results: claims, mappings, gaps, questions with jurisdiction labels."""
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.intake_id == intake_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()

    if run is None:
        raise HTTPException(status_code=404, detail="No analysis run found for this intake")

    # Load claims
    claims_result = await db.execute(
        select(AnalysisClaim).where(AnalysisClaim.run_id == run.id)
    )
    claims = claims_result.scalars().all()

    claims_data = []
    for c in claims:
        # Load elements for each claim
        elements_result = await db.execute(
            select(ClaimElement).where(ClaimElement.claim_id == c.id)
        )
        elements = elements_result.scalars().all()

        claims_data.append({
            "id": c.id,
            "claim_name": c.claim_name,
            "claim_type": c.claim_type,
            "folio_iri": c.folio_iri,
            "jurisdiction": c.jurisdiction,
            "confidence": c.confidence,
            "is_potential": c.is_potential,
            "rationale": c.rationale,
            "elements": [
                {
                    "id": e.id,
                    "element_name": e.element_name,
                    "is_satisfied": e.is_satisfied,
                    "satisfaction_confidence": e.satisfaction_confidence,
                }
                for e in elements
            ],
        })

    # Load gaps
    gaps_result = await db.execute(
        select(AnalysisGap).where(AnalysisGap.run_id == run.id)
    )
    gaps = gaps_result.scalars().all()

    gaps_data = [
        {
            "id": g.id,
            "gap_type": g.gap_type,
            "description": g.description,
            "priority": g.priority,
            "status": g.status,
        }
        for g in gaps
    ]

    # Load questions
    questions_result = await db.execute(
        select(FollowUpQuestion).where(FollowUpQuestion.run_id == run.id)
    )
    questions = questions_result.scalars().all()

    questions_data = [
        {
            "id": q.id,
            "question_text": q.question_text,
            "topic_group": q.topic_group,
            "priority": q.priority,
            "rationale": q.rationale,
            "status": q.status,
        }
        for q in questions
    ]

    # Load deadlines (v1 "detect + hedge")
    deadlines_result = await db.execute(
        select(Deadline).where(Deadline.run_id == run.id)
    )
    deadlines = deadlines_result.scalars().all()
    deadlines_data = [
        {
            "id": d.id,
            "event_text": d.event_text,
            "event_type": d.event_type,
            "trigger": d.trigger,
            "trigger_date": d.trigger_date.isoformat() if d.trigger_date else None,
            "computed_date": d.computed_date.isoformat() if d.computed_date else None,
            "rule_id": d.rule_id,
            "citation": d.citation,
            "computed": d.computed,
            "urgency": d.urgency,
            "hedge": d.hedge,
            "jurisdiction": d.jurisdiction,
        }
        for d in deadlines
    ]

    return {
        "run_id": run.id,
        "status": run.status,
        "claims": claims_data,
        "gaps": gaps_data,
        "questions": questions_data,
        "deadlines": deadlines_data,
    }


@router.post("/{intake_id}/override")
async def override_convergence(
    intake_id: int,
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Override convergence and continue analysis (D-16)."""
    from app.services.analysis.orchestrator import AnalysisOrchestrator
    from app.services.llm_service import LLMService

    # Find the latest converged run
    result = await db.execute(
        select(AnalysisRun)
        .where(
            AnalysisRun.intake_id == intake_id,
            AnalysisRun.status == "converged",
        )
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No converged analysis run found to override",
        )

    llm_service = LLMService()
    orchestrator = AnalysisOrchestrator(
        db_session=db,
        llm_service=llm_service,
        folio=None,
        embedding_service=None,
    )

    updated_run = await orchestrator.override_convergence(run_id=run.id)

    return {
        "run_id": updated_run.id,
        "status": updated_run.status,
        "iteration": updated_run.current_iteration_number,
        "message": "Convergence overridden, analysis continued",
    }


@router.get("/{intake_id}/audit")
async def get_audit_trail(
    intake_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Full audit trail: every stage, sources, confidence scores (ANALYSIS-10)."""
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.intake_id == intake_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()

    if run is None:
        raise HTTPException(status_code=404, detail="No analysis run found for this intake")

    # Load all iterations
    iterations_result = await db.execute(
        select(AnalysisIteration)
        .where(AnalysisIteration.run_id == run.id)
        .order_by(AnalysisIteration.iteration_number)
    )
    iterations = iterations_result.scalars().all()

    audit_data = []
    for iteration in iterations:
        # Load stages for this iteration
        stages_result = await db.execute(
            select(AnalysisStage)
            .where(AnalysisStage.iteration_id == iteration.id)
            .order_by(AnalysisStage.id)
        )
        stages = stages_result.scalars().all()

        iteration_audit = {
            "iteration_number": iteration.iteration_number,
            "status": iteration.status,
            "converged": iteration.converged,
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "audit_json": s.audit_json,
                    "result_json": s.result_json,
                }
                for s in stages
            ],
        }
        audit_data.append(iteration_audit)

    return {
        "run_id": run.id,
        "status": run.status,
        "iterations": audit_data,
    }


@router.get("/{intake_id}/visualization", response_model=VisualizationResponse)
async def get_visualization_data(
    intake_id: int,
    db: AsyncSession = Depends(get_tenant_session),
    user: User = Depends(get_current_active_user),
) -> VisualizationResponse:
    """Get complete visualization payload: facts, claims, mappings, gaps, messages.

    Returns all data needed by the frontend visualization views (graph, matrix,
    narrative). Includes source spans for "trust but verify" provenance links.
    """
    # 1. Latest AnalysisRun for this intake
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.intake_id == intake_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalars().first()

    if run is None:
        raise HTTPException(status_code=404, detail="No analysis run found for this intake")

    # 2. Active extracted facts for this intake
    facts_result = await db.execute(
        select(ExtractedFact).where(
            ExtractedFact.intake_id == intake_id,
            ExtractedFact.is_active == True,  # noqa: E712
        )
    )
    facts = facts_result.scalars().all()
    fact_ids = [f.id for f in facts]

    # 3. Source spans for those facts
    spans_by_fact: dict[int, list[VisualizationSourceSpan]] = {}
    if fact_ids:
        spans_result = await db.execute(
            select(FactSourceSpan).where(FactSourceSpan.fact_id.in_(fact_ids))
        )
        for span in spans_result.scalars().all():
            spans_by_fact.setdefault(span.fact_id, []).append(
                VisualizationSourceSpan(
                    message_id=span.message_id,
                    start_char=span.start_char,
                    end_char=span.end_char,
                    page_number=span.page_number,
                    paragraph_index=span.paragraph_index,
                    timestamp_start_sec=span.timestamp_start_sec,
                    timestamp_end_sec=span.timestamp_end_sec,
                )
            )

    viz_facts = [
        VisualizationFact(
            id=f.id,
            assertion_text=f.assertion_text,
            fact_type=f.fact_type,
            confidence=f.confidence,
            source_spans=spans_by_fact.get(f.id, []),
        )
        for f in facts
    ]

    # 4. Claims for this run
    claims_result = await db.execute(
        select(AnalysisClaim).where(AnalysisClaim.run_id == run.id)
    )
    claims = claims_result.scalars().all()
    claim_ids = [c.id for c in claims]

    # 5. Elements for those claims
    elements_by_claim: dict[int, list[VisualizationElement]] = {}
    if claim_ids:
        elements_result = await db.execute(
            select(ClaimElement).where(ClaimElement.claim_id.in_(claim_ids))
        )
        for elem in elements_result.scalars().all():
            elements_by_claim.setdefault(elem.claim_id, []).append(
                VisualizationElement(
                    id=elem.id,
                    element_name=elem.element_name,
                    element_description=elem.element_description,
                    is_satisfied=elem.is_satisfied,
                    satisfaction_confidence=elem.satisfaction_confidence,
                )
            )

    viz_claims = [
        VisualizationClaim(
            id=c.id,
            claim_name=c.claim_name,
            claim_type=c.claim_type,
            jurisdiction=c.jurisdiction,
            confidence=c.confidence,
            rationale=c.rationale,
            elements=elements_by_claim.get(c.id, []),
        )
        for c in claims
    ]

    # 6. Fact-claim mappings for these facts
    viz_mappings: list[VisualizationMapping] = []
    if fact_ids:
        mappings_result = await db.execute(
            select(FactClaimMapping).where(FactClaimMapping.fact_id.in_(fact_ids))
        )
        viz_mappings = [
            VisualizationMapping(
                id=m.id,
                fact_id=m.fact_id,
                claim_id=m.claim_id,
                element_id=m.element_id,
                confidence=m.confidence,
                mapping_rationale=m.mapping_rationale,
            )
            for m in mappings_result.scalars().all()
        ]

    # 7. Gaps for this run
    gaps_result = await db.execute(
        select(AnalysisGap).where(AnalysisGap.run_id == run.id)
    )
    viz_gaps = [
        VisualizationGap(
            id=g.id,
            gap_type=g.gap_type,
            claim_id=g.claim_id,
            element_id=g.element_id,
            description=g.description,
            priority=g.priority,
            status=g.status,
        )
        for g in gaps_result.scalars().all()
    ]

    # 8. Messages from sessions belonging to this intake
    # Only consumer/professional sender_type messages (not system)
    sessions_result = await db.execute(
        select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
    )
    session_ids = [s for s in sessions_result.scalars().all()]

    viz_messages: list[VisualizationMessage] = []
    if session_ids:
        messages_result = await db.execute(
            select(Message).where(
                Message.session_id.in_(session_ids),
                Message.sender_type.in_(["consumer", "professional"]),
            )
        )
        for msg in messages_result.scalars().all():
            # Decode message content: normalized_text or content_encrypted are LargeBinary.
            # For MVP visualization, decode raw bytes as UTF-8.
            # NOTE: Production should use EncryptionContext (Phase 01-03) for proper
            # decryption of encrypted content fields.
            content = ""
            if msg.normalized_text is not None:
                try:
                    content = msg.normalized_text.decode("utf-8") if isinstance(msg.normalized_text, bytes) else str(msg.normalized_text)
                except (UnicodeDecodeError, AttributeError):
                    content = ""
            elif msg.content_encrypted is not None:
                try:
                    content = msg.content_encrypted.decode("utf-8") if isinstance(msg.content_encrypted, bytes) else str(msg.content_encrypted)
                except (UnicodeDecodeError, AttributeError):
                    content = ""

            viz_messages.append(
                VisualizationMessage(
                    id=msg.id,
                    content=content,
                    sender_type=msg.sender_type,
                )
            )

    return VisualizationResponse(
        run_id=run.id,
        status=run.status,
        facts=viz_facts,
        claims=viz_claims,
        mappings=viz_mappings,
        gaps=viz_gaps,
        messages=viz_messages,
    )
