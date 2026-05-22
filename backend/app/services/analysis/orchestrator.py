"""Analysis pipeline orchestrator -- LLM-driven iterative analysis loop (D-01).

Single LLM orchestrator per iteration decides which stage to run next.
Stages: issue-spot -> research -> fact-map -> gap-analyze -> question.
When multiple jurisdictions detected (ANALYSIS-08/D-06), fact-map and
gap-analyze run per jurisdiction sequentially over the shared session
(asyncpg connections are not concurrency-safe; see _run_parallel_jurisdictions).

Each stage completion creates an AnalysisStage checkpoint record for
pause/resume (ANALYSIS-09). Audit trail populates audit_json on every
stage with stage_name, input_fact_count, claims_produced,
sources_consulted, confidence_scores_summary, duration_ms (ANALYSIS-10).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select

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
from app.models.fact import ExtractedFact
from app.services.analysis.convergence import ConvergenceEvaluator
from app.services.analysis.schemas import AnalysisConfig, ConvergenceSignals

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.analysis.autonomy.interceptor import AutonomyInterceptor
    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class AnalysisOrchestrator:
    """LLM-driven iterative analysis loop (D-01).

    Single LLM orchestrator per iteration decides which stage to run next.
    Stages: issue-spot -> research -> fact-map -> gap-analyze -> question.
    When multiple jurisdictions detected (ANALYSIS-08/D-06), fact-map and
    gap-analyze run per jurisdiction sequentially over the shared session
    (asyncpg connections are not concurrency-safe; see _run_parallel_jurisdictions).
    """

    STAGES = ["issue_spot", "explore", "research", "fact_map", "gap_analyze", "question_gen"]

    def __init__(
        self,
        db_session: AsyncSession,
        llm_service: LLMService,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
        org_config: dict | None = None,
        max_iterations: int = 10,
        autonomy_interceptor: "AutonomyInterceptor | None" = None,
    ) -> None:
        self._session = db_session
        self._llm = llm_service
        self._folio = folio
        self._embedding_service = embedding_service
        self._org_config = org_config or {}
        self._max_iterations = max_iterations
        self._org_id: int = self._org_config.get("org_id", 0)
        self._autonomy = autonomy_interceptor

        # Parse analysis config from org settings
        self._analysis_config = AnalysisConfig(
            **(self._org_config.get("analysis_config", {}))
        ) if self._org_config.get("analysis_config") else AnalysisConfig(
            max_iterations=max_iterations,
        )

        # Build convergence evaluator from org config
        self._convergence_evaluator = ConvergenceEvaluator(
            threshold=self._analysis_config.convergence_threshold,
        )

        # Track detected jurisdictions across iterations
        self._jurisdictions: list[str] = []

    async def run(
        self,
        intake_id: int,
        session_id: int,
        ws_manager: Any | None = None,
    ) -> AnalysisRun:
        """Execute the full analysis loop.

        1. Create AnalysisRun record
        2. Loop: run iteration until convergence or hard cap
        3. On convergence: update AnalysisRun status
        4. Return AnalysisRun with final state
        """
        # Load facts for this intake
        facts = await self._load_facts(intake_id)

        # Create AnalysisRun record
        run = AnalysisRun(
            intake_id=intake_id,
            status="running",
            trigger_type="manual",
            current_iteration_number=0,
            max_iterations=self._analysis_config.max_iterations,
        )
        self._session.add(run)
        await self._session.flush()

        # Main iteration loop
        converged = False
        convergence_score = 0.0

        for i in range(1, self._analysis_config.max_iterations + 1):
            run.current_iteration_number = i
            self._session.add(run)
            await self._session.flush()

            # Run a single iteration
            iteration = await self._run_iteration(run, i, ws_manager, session_id)

            # Evaluate convergence
            converged, convergence_score = await self._evaluate_convergence(run, iteration)

            # Update iteration record
            iteration.converged = converged
            iteration.status = "completed"
            iteration.completed_at = datetime.now(timezone.utc)
            self._session.add(iteration)
            await self._session.flush()

            if converged:
                break

        # Finalize run
        if converged:
            run.status = "converged"
        else:
            run.status = "max_iterations"

        run.convergence_score = convergence_score
        self._session.add(run)
        await self._session.flush()

        # Broadcast final status
        if ws_manager and session_id:
            await self._broadcast_progress(
                run, "complete", ws_manager, session_id=session_id
            )

        return run

    async def resume(
        self,
        run_id: int,
        ws_manager: Any | None = None,
    ) -> AnalysisRun:
        """Resume from latest checkpoint (ANALYSIS-09).

        Load latest AnalysisStage, continue from next stage in sequence.
        """
        # Load the run
        result = await self._session.execute(
            select(AnalysisRun).where(AnalysisRun.id == run_id)
        )
        run = result.scalars().first()
        if run is None:
            raise ValueError(f"AnalysisRun {run_id} not found")

        # Find the session_id from intake
        session_id = None

        # Mark as running again
        run.status = "running"
        self._session.add(run)
        await self._session.flush()

        # Find latest completed stage
        result = await self._session.execute(
            select(AnalysisStage)
            .join(AnalysisIteration, AnalysisStage.iteration_id == AnalysisIteration.id)
            .where(AnalysisIteration.run_id == run_id)
            .where(AnalysisStage.status == "completed")
            .order_by(desc(AnalysisStage.id))
        )
        last_stage = result.scalars().first()

        # Determine where to resume
        if last_stage:
            completed_stage_name = last_stage.stage_name
            # Get the iteration this stage belongs to
            result = await self._session.execute(
                select(AnalysisIteration).where(
                    AnalysisIteration.id == last_stage.iteration_id
                )
            )
            current_iteration = result.scalars().first()
        else:
            completed_stage_name = None
            current_iteration = None

        # Continue the loop from current iteration
        start_iteration = run.current_iteration_number
        converged = False
        convergence_score = 0.0

        for i in range(start_iteration, self._analysis_config.max_iterations + 1):
            run.current_iteration_number = i
            self._session.add(run)
            await self._session.flush()

            # Determine which stages to run (skip already completed ones in first iteration)
            stages = await self._select_stages(run, current_iteration)
            if current_iteration and current_iteration.iteration_number == i and completed_stage_name:
                # Filter out already completed stages
                try:
                    idx = self.STAGES.index(completed_stage_name)
                    stages = [s for s in stages if s in self.STAGES[idx + 1:]]
                except ValueError:
                    pass

            # Create or reuse iteration
            if current_iteration and current_iteration.iteration_number == i:
                iteration = current_iteration
            else:
                iteration = AnalysisIteration(
                    run_id=run.id,
                    iteration_number=i,
                    status="running",
                )
                self._session.add(iteration)
                await self._session.flush()

            # Execute remaining stages
            for stage_name in stages:
                await self._execute_stage(stage_name, run, iteration, ws_manager)

            # Evaluate convergence
            converged, convergence_score = await self._evaluate_convergence(run, iteration)

            iteration.converged = converged
            iteration.status = "completed"
            iteration.completed_at = datetime.now(timezone.utc)
            self._session.add(iteration)
            await self._session.flush()

            if converged:
                break

            # Reset for next iteration
            current_iteration = None
            completed_stage_name = None

        # Finalize
        run.status = "converged" if converged else "max_iterations"
        run.convergence_score = convergence_score
        self._session.add(run)
        await self._session.flush()

        return run

    async def override_convergence(
        self,
        run_id: int,
        ws_manager: Any | None = None,
    ) -> AnalysisRun:
        """Override termination and continue analysis (D-16).

        Reset convergence signals, increment iteration, continue loop.
        """
        result = await self._session.execute(
            select(AnalysisRun).where(AnalysisRun.id == run_id)
        )
        run = result.scalars().first()
        if run is None:
            raise ValueError(f"AnalysisRun {run_id} not found")

        # Reset convergence state
        run.status = "running"
        run.convergence_score = None
        self._convergence_evaluator._previously_converged = False
        self._session.add(run)
        await self._session.flush()

        # Continue from current position
        start_iteration = run.current_iteration_number + 1
        converged = False
        convergence_score = 0.0

        for i in range(start_iteration, self._analysis_config.max_iterations + 1):
            run.current_iteration_number = i
            self._session.add(run)
            await self._session.flush()

            iteration = await self._run_iteration(run, i, ws_manager, session_id=None)

            converged, convergence_score = await self._evaluate_convergence(run, iteration)

            iteration.converged = converged
            iteration.status = "completed"
            iteration.completed_at = datetime.now(timezone.utc)
            self._session.add(iteration)
            await self._session.flush()

            if converged:
                break

        run.status = "converged" if converged else "max_iterations"
        run.convergence_score = convergence_score
        self._session.add(run)
        await self._session.flush()

        return run

    async def _run_iteration(
        self,
        run: AnalysisRun,
        iteration_num: int,
        ws_manager: Any | None,
        session_id: int | None = None,
    ) -> AnalysisIteration:
        """Single iteration: select stages -> execute -> checkpoint -> converge check.

        If issue_spot identified multiple jurisdictions, use _run_parallel_jurisdictions
        for fact_map and gap_analyze stages.
        """
        iteration = AnalysisIteration(
            run_id=run.id,
            iteration_number=iteration_num,
            status="running",
        )
        self._session.add(iteration)
        await self._session.flush()

        # LLM selects which stages to run
        stages = await self._select_stages(run, iteration)

        # Execute stages
        for stage_name in stages:
            if stage_name in ("fact_map", "gap_analyze") and len(self._jurisdictions) > 1:
                # Run in parallel per jurisdiction
                await self._run_parallel_jurisdictions(
                    self._jurisdictions, run, iteration, ws_manager,
                )
                # Skip individual fact_map and gap_analyze since they ran in parallel
                stages_to_skip = {"fact_map", "gap_analyze"}
                stages = [s for s in stages if s not in stages_to_skip]
                break
            else:
                result = await self._execute_stage(
                    stage_name, run, iteration, ws_manager,
                )
                # Track jurisdictions from issue_spot results
                if stage_name == "issue_spot" and isinstance(result, dict):
                    jurisdictions = result.get("jurisdictions", [])
                    if jurisdictions:
                        self._jurisdictions = jurisdictions

            # Broadcast progress
            if ws_manager and session_id:
                await self._broadcast_progress(
                    run, stage_name, ws_manager, session_id=session_id,
                )

        return iteration

    async def _run_parallel_jurisdictions(
        self,
        jurisdictions: list[str],
        run: AnalysisRun,
        iteration: AnalysisIteration,
        ws_manager: Any | None,
    ) -> None:
        """ANALYSIS-08: Run fact-map + gap-analyze per jurisdiction.

        Each branch:
        1. Runs FactMapStage.execute(jurisdiction=j)
        2. Runs GapAnalyzeStage.execute(jurisdiction=j)
        3. Creates AnalysisStage checkpoints with jurisdiction label
        Results merged with jurisdiction annotations on all mappings and gaps.

        NOTE: Branches run SEQUENTIALLY, not concurrently. Every branch drives
        the SHARED self._session (one asyncpg connection) -- both through the
        stage instances (db_session=self._session) and through the orchestrator's
        own checkpoint writes (self._session.add / flush in _execute_stage_inner).
        asyncpg connections are NOT concurrency-safe, so fanning these branches
        out concurrently (the previous gather-based approach) raises "another
        operation is in progress" and poisons the pooled connection (it only
        ever survived on SQLite, which serializes access internally). True
        per-jurisdiction parallelism would require per-branch connections plus
        merging the run/iteration ORM objects across sessions -- deferred as a
        follow-up.
        """

        async def _jurisdiction_branch(jurisdiction: str) -> None:
            await self._execute_stage(
                "fact_map", run, iteration, ws_manager, jurisdiction=jurisdiction,
            )
            await self._execute_stage(
                "gap_analyze", run, iteration, ws_manager, jurisdiction=jurisdiction,
            )

        for j in jurisdictions:
            await _jurisdiction_branch(j)

    async def _select_stages(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration | None,
    ) -> list[str]:
        """LLM orchestrator decides which stages to run this iteration.

        For simplicity, runs all stages in order on first iteration,
        then uses the standard sequence for subsequent iterations.
        In a full implementation, this would use LLM structured output
        via OrchestratorDecision schema.
        """
        return list(self.STAGES)

    async def _execute_stage(
        self,
        stage_name: str,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        ws_manager: Any | None,
        jurisdiction: str | None = None,
    ) -> dict:
        """Execute a stage, optionally gated by autonomy interceptor.

        If an autonomy interceptor is configured, delegates to it.
        Otherwise calls _execute_stage_inner directly.
        """
        if self._autonomy is not None:
            return await self._autonomy.execute_with_autonomy(
                stage_name=stage_name,
                execute_fn=lambda **kw: self._execute_stage_inner(
                    stage_name, run, iteration, ws_manager, jurisdiction,
                ),
                run_id=run.id,
                iteration_id=iteration.id,
                intake_id=run.intake_id,
            )
        return await self._execute_stage_inner(
            stage_name, run, iteration, ws_manager, jurisdiction,
        )

    async def _execute_stage_inner(
        self,
        stage_name: str,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        ws_manager: Any | None,
        jurisdiction: str | None = None,
    ) -> dict:
        """Execute a single stage, create AnalysisStage checkpoint with audit_json.

        audit_json includes: stage_name, input_fact_count, claims_produced,
        sources_consulted, confidence_scores_summary, duration_ms.
        """
        start_time = time.monotonic()

        # Get the stage instance
        stage_instance = self._get_stage_instance(stage_name)

        # Load data needed for the stage
        facts = await self._load_facts(run.intake_id)
        claims = await self._load_claims(run.id)
        elements = await self._load_elements(claims)
        mappings = await self._load_mappings(run.id)
        gaps = await self._load_gaps(run.id)
        questions = await self._load_questions(run.id)

        # Execute the stage with appropriate arguments
        try:
            if stage_name == "issue_spot":
                result = await stage_instance.execute(run, iteration, facts)
            elif stage_name == "explore":
                result = await stage_instance.execute(run, iteration, claims, facts)
            elif stage_name == "research":
                result = await stage_instance.execute(run, claims)
            elif stage_name == "fact_map":
                result = await stage_instance.execute(run, iteration, facts, claims)
            elif stage_name == "gap_analyze":
                result = await stage_instance.execute(
                    run, iteration, claims, elements, mappings, gaps,
                )
            elif stage_name == "question_gen":
                result = await stage_instance.execute(
                    run, iteration, gaps, "", questions,
                )
            else:
                result = {}
        except Exception as exc:
            logger.error("Stage %s failed: %s", stage_name, exc, exc_info=True)
            result = {"error": str(exc)}

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Build audit_json
        audit_json = {
            "stage_name": stage_name,
            "input_fact_count": len(facts),
            "claims_produced": result.get("claims_count", 0) if isinstance(result, dict) else 0,
            "sources_consulted": result.get("jurisdictions", []) if isinstance(result, dict) else [],
            "confidence_scores_summary": result.get("avg_confidence", 0.0) if isinstance(result, dict) else 0.0,
            "duration_ms": elapsed_ms,
        }

        if jurisdiction:
            audit_json["jurisdiction"] = jurisdiction

        # Create AnalysisStage checkpoint record
        stage_record = AnalysisStage(
            iteration_id=iteration.id,
            stage_name=stage_name,
            status="completed",
            result_json=result if isinstance(result, dict) else {"result": str(result)},
            audit_json=audit_json,
            duration_ms=elapsed_ms,
        )
        self._session.add(stage_record)
        await self._session.flush()

        return result if isinstance(result, dict) else {}

    def _get_stage_instance(self, stage_name: str) -> Any:
        """Get a stage instance by name, creating it with the right dependencies."""
        from app.services.analysis.stages.fact_map import FactMapStage
        from app.services.analysis.stages.gap_analyze import GapAnalyzeStage
        from app.services.analysis.stages.issue_spot import IssueSpotStage
        from app.services.analysis.stages.question_gen import QuestionGenStage
        from app.services.research.research_stage import ResearchStage

        if stage_name == "issue_spot":
            return IssueSpotStage(
                llm_service=self._llm,
                db_session=self._session,
                folio=self._folio,
                embedding_service=self._embedding_service,
            )
        elif stage_name == "explore":
            from app.services.analysis.stages.explore import ExploreStage

            return ExploreStage(
                llm_service=self._llm,
                db_session=self._session,
                folio=self._folio,
                embedding_service=self._embedding_service,
                org_config=self._org_config,
            )
        elif stage_name == "research":
            return ResearchStage(
                db_session=self._session,
                llm_service=self._llm,
                org_id=self._org_id,
            )
        elif stage_name == "fact_map":
            return FactMapStage(
                llm_service=self._llm,
                db_session=self._session,
                folio=self._folio,
                embedding_service=self._embedding_service,
            )
        elif stage_name == "gap_analyze":
            return GapAnalyzeStage(
                llm_service=self._llm,
                db_session=self._session,
            )
        elif stage_name == "question_gen":
            return QuestionGenStage(
                llm_service=self._llm,
                db_session=self._session,
                question_transparency=self._analysis_config.question_transparency,
            )
        else:
            raise ValueError(f"Unknown stage: {stage_name}")

    async def _evaluate_convergence(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
    ) -> tuple[bool, float]:
        """Evaluate convergence after gap analysis using ConvergenceEvaluator."""
        # Gather signals
        claims = await self._load_claims(run.id)
        elements = await self._load_elements(claims)
        mappings = await self._load_mappings(run.id)
        gaps = await self._load_gaps(run.id)

        # Calculate coverage
        total_elements = len(elements)
        satisfied = sum(1 for e in elements if e.is_satisfied)
        coverage = satisfied / total_elements if total_elements > 0 else 0.5

        # Calculate confidence delta (compare with previous iteration)
        if mappings:
            current_avg = sum(m.confidence for m in mappings) / len(mappings)
        else:
            current_avg = 0.0

        # Simple approximation for delta
        confidence_delta = 0.05 if iteration.iteration_number == 1 else 0.01

        # Count new gaps vs previous
        open_gaps = [g for g in gaps if g.status == "open"]
        previous_gap_count = max(len(open_gaps) - len([
            g for g in open_gaps if g.iteration_found == iteration.iteration_number
        ]), 1)
        new_gaps = len([
            g for g in open_gaps if g.iteration_found == iteration.iteration_number
        ])

        signals = ConvergenceSignals(
            coverage_pct=coverage,
            confidence_delta=confidence_delta,
            iteration_number=iteration.iteration_number,
            max_iterations=run.max_iterations,
            skip_rate=0.0,
            avg_response_time_sec=0.0,
            new_gaps_count=new_gaps,
            previous_gaps_count=previous_gap_count,
        )

        return self._convergence_evaluator.evaluate(signals)

    async def _broadcast_progress(
        self,
        run: AnalysisRun,
        stage_name: str,
        ws_manager: Any,
        session_id: int | None = None,
    ) -> None:
        """Push stage-by-stage progress update via WebSocket (D-15)."""
        if ws_manager is None or session_id is None:
            return

        progress_pct = 0
        if run.max_iterations > 0:
            progress_pct = int(
                (run.current_iteration_number / run.max_iterations) * 100
            )

        message = {
            "type": "analysis_progress",
            "run_id": run.id,
            "stage": stage_name,
            "iteration": run.current_iteration_number,
            "max_iterations": run.max_iterations,
            "status": run.status,
            "progress_pct": progress_pct,
        }

        await ws_manager.send_to_session(session_id, message)

    # --- Data loading helpers ---

    async def _load_facts(self, intake_id: int) -> list[ExtractedFact]:
        """Load all active extracted facts for an intake."""
        result = await self._session.execute(
            select(ExtractedFact).where(
                ExtractedFact.intake_id == intake_id,
                ExtractedFact.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def _load_claims(self, run_id: int) -> list[AnalysisClaim]:
        """Load all claims for an analysis run."""
        result = await self._session.execute(
            select(AnalysisClaim).where(AnalysisClaim.run_id == run_id)
        )
        return list(result.scalars().all())

    async def _load_elements(self, claims: list[AnalysisClaim]) -> list[ClaimElement]:
        """Load all elements for the given claims."""
        if not claims:
            return []
        claim_ids = [c.id for c in claims]
        result = await self._session.execute(
            select(ClaimElement).where(ClaimElement.claim_id.in_(claim_ids))
        )
        return list(result.scalars().all())

    async def _load_mappings(self, run_id: int) -> list[FactClaimMapping]:
        """Load all fact-claim mappings for claims in this run."""
        claims = await self._load_claims(run_id)
        if not claims:
            return []
        claim_ids = [c.id for c in claims]
        result = await self._session.execute(
            select(FactClaimMapping).where(FactClaimMapping.claim_id.in_(claim_ids))
        )
        return list(result.scalars().all())

    async def _load_gaps(self, run_id: int) -> list[AnalysisGap]:
        """Load all gaps for an analysis run."""
        result = await self._session.execute(
            select(AnalysisGap).where(AnalysisGap.run_id == run_id)
        )
        return list(result.scalars().all())

    async def _load_questions(self, run_id: int) -> list[FollowUpQuestion]:
        """Load all follow-up questions for an analysis run."""
        result = await self._session.execute(
            select(FollowUpQuestion).where(FollowUpQuestion.run_id == run_id)
        )
        return list(result.scalars().all())
