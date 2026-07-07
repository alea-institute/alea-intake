"""Exploration stage -- three-layer pre-research exploration for issue discovery.

Runs between issue_spot and research in the AnalysisOrchestrator pipeline.
Uses ExplorationEngine to execute four exploration layers in hybrid parallel
(D-05), with multi-round stability detection (D-06). Discovered issues become
new AnalysisClaim records with claim_type='discovered' and is_potential=True
(EXPLORE-10). Question transparency from ExplorationConfig propagated per
EXPLORE-06.

Follows IssueSpotStage pattern exactly: constructor injection, execute method,
DB persistence, dict return for orchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.models.analysis import AnalysisClaim
from app.services.exploration.engine import ExplorationEngine
from app.services.exploration.schemas import ExplorationConfig
from app.services.screening.protocol_service import ProtocolService

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisIteration, AnalysisRun
    from app.models.fact import ExtractedFact
    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ExploreStage:
    """Three-layer exploration stage for the analysis pipeline.

    Executes between issue_spot and research stages. Uses ExplorationEngine
    to run four exploration layers (FOLIO adjacency, protocol matching,
    cheap LLM, expensive LLM) in hybrid parallel. Discovered issues become
    new AnalysisClaim records feeding into the research stage.

    Constructor signature matches IssueSpotStage pattern with additional
    org_config for exploration settings.
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
        org_config: dict | None = None,
    ) -> None:
        self._llm = llm_service
        self._session = db_session
        self._folio = folio
        self._embedding_service = embedding_service
        self._org_config = org_config or {}

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        claims: list[AnalysisClaim],
        facts: list[ExtractedFact],
    ) -> dict:
        """Execute the exploration stage.

        1. Parse ExplorationConfig from org_config
        2. Create ProtocolService and load active protocols
        3. Create ExplorationEngine and run exploration
        4. Persist discovered issues as AnalysisClaim records
        5. Return result dict for orchestrator

        Args:
            run: The current AnalysisRun.
            iteration: The current AnalysisIteration.
            claims: List of existing AnalysisClaim objects.
            facts: List of ExtractedFact objects.

        Returns:
            Dict with new_claims count, triggered_protocols, rounds_completed,
            total_new_issues, and question_transparency flag.
        """
        # BUG-8 guard: never explore from nothing. With zero extracted facts
        # every layer degenerates into ungrounded speculation (the LLM invents
        # generic claims), which violates the no-fabrication contract (RUB-04).
        if not facts:
            logger.info(
                "Exploration skipped for run %s iteration %s: no extracted facts",
                run.id,
                iteration.iteration_number,
            )
            return {
                "new_claims": 0,
                "triggered_protocols": [],
                "rounds_completed": 0,
                "total_new_issues": 0,
                "question_transparency": False,
                "skipped_no_facts": True,
            }

        # Parse exploration config
        exploration_raw = self._org_config.get("exploration", {})
        if isinstance(exploration_raw, ExplorationConfig):
            config = exploration_raw
        elif isinstance(exploration_raw, dict):
            config = ExplorationConfig(**exploration_raw)
        else:
            config = ExplorationConfig()

        # Create ProtocolService for protocol loading
        protocol_service = ProtocolService(self._session)

        # Create and run ExplorationEngine
        engine = ExplorationEngine(
            folio=self._folio,
            llm_service=self._llm,
            embedding_service=self._embedding_service,
            db_session=self._session,
            org_config=self._org_config,
            protocol_service=protocol_service,
        )

        stage_result = await engine.explore(run, iteration, claims, facts)

        # Persist discovered issues as AnalysisClaim records (EXPLORE-10).
        # BUG-8 dedupe: the orchestrator re-runs exploration every iteration;
        # without a name-level dedupe the same discovered issues re-persist
        # each pass (observed live: 133 near-duplicate claims per intake).
        seen_names = {
            (c.claim_name or "").strip().lower() for c in claims if c.claim_name
        }
        persisted_count = 0
        for new_claim in stage_result.new_claims:
            name_key = (new_claim.get("claim_name") or "Unknown").strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            claim = AnalysisClaim(
                run_id=run.id,
                claim_name=new_claim.get("claim_name", "Unknown"),
                claim_type="discovered",
                folio_iri=new_claim.get("folio_iri"),
                confidence=new_claim.get("confidence", 0.5),
                rationale=new_claim.get(
                    "rationale",
                    f"Discovered via {new_claim.get('source_layer', 'exploration')} exploration",
                ),
                is_potential=True,
                metadata_json={
                    "source_layer": new_claim.get("source_layer"),
                    "exploration_round": new_claim.get("exploration_round"),
                },
                iteration_discovered=iteration.iteration_number,
            )
            self._session.add(claim)
            persisted_count += 1

        if persisted_count > 0:
            await self._session.flush()

        return {
            "new_claims": persisted_count,
            "triggered_protocols": [
                p for p in stage_result.triggered_protocols
            ],
            "rounds_completed": len(stage_result.rounds),
            "total_new_issues": stage_result.total_new_issues,
            "question_transparency": config.question_transparency,
        }
