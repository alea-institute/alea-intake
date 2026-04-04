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
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.user import User

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
    from app.services.llm_service import LLMService

    llm_service = LLMService()
    orchestrator = AnalysisOrchestrator(
        db_session=db,
        llm_service=llm_service,
        folio=None,
        embedding_service=None,
    )
    trigger = AnalysisTrigger(db_session=db, orchestrator=orchestrator)

    run = await trigger.manual_trigger(intake_id=intake_id, session_id=0)

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

    return {
        "run_id": run.id,
        "status": run.status,
        "claims": claims_data,
        "gaps": gaps_data,
        "questions": questions_data,
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
