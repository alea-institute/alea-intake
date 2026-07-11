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
from app.services.analysis.rationale_guard import ground_rationale
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
        # BUG-8 guard: exploration runs ONCE per analysis run. Facts are
        # backfilled at trigger time and don't change between iterations, so
        # re-exploring every iteration only re-invents differently-worded
        # claims the name-dedupe can't catch (observed live: 123 "discovered"
        # claims over 8 iterations). The engine already does multi-round
        # stability internally on its single run.
        if getattr(iteration, "iteration_number", 1) > 1:
            logger.info(
                "Exploration skipped for run %s iteration %s: explore runs once per run",
                run.id,
                iteration.iteration_number,
            )
            return {
                "new_claims": 0,
                "triggered_protocols": [],
                "rounds_completed": 0,
                "total_new_issues": 0,
                "question_transparency": False,
                "skipped_already_ran": True,
            }

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

        # BUG-22 (RUB-05 semantic-fit, all 3 personas): the exploration lane
        # carried its own FOLIO IRIs (assigned in the engine's cheap/expensive
        # LLM dedup and adjacency layers) that BYPASSED the SemanticFitValidator
        # that issue_spot runs. Worst case observed: "Legal Representation"@0.90
        # -> IRI resolving to "Resen", a North Macedonia municipality (a
        # Location-branch geographic node) surfaced as an urgent claim. Route
        # EVERY discovered mapping through the same validator so a wrong IRI is
        # dropped and its confidence recalibrated before persistence. Branch and
        # label are looked up in-memory (no network) from the already-loaded
        # FOLIO singleton, mirroring issue_spot's two-pass pattern.
        survivors: list[dict] = []
        seen_names_pass1 = set(seen_names)
        for new_claim in stage_result.new_claims:
            name_key = (new_claim.get("claim_name") or "Unknown").strip().lower()
            if name_key in seen_names_pass1:
                continue
            seen_names_pass1.add(name_key)
            survivors.append(new_claim)

        fit_verdicts = await self._validate_discovered_mappings(survivors, facts)

        persisted_count = 0
        for new_claim in survivors:
            name_key = (new_claim.get("claim_name") or "Unknown").strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            folio_iri = new_claim.get("folio_iri")
            confidence = new_claim.get("confidence", 0.5)
            verdict = fit_verdicts.get(name_key)
            if verdict is not None:
                if verdict.drop_iri:
                    folio_iri = None
                confidence = verdict.adjusted_confidence

            # BUG-28: hedge unsupported evidence assertions in discovered-claim
            # rationale before persistence (RUB-04 GATE), same guard as issue_spot.
            raw_rationale = new_claim.get(
                "rationale",
                f"Discovered via {new_claim.get('source_layer', 'exploration')} exploration",
            )
            grounded_rationale, hedges = ground_rationale(
                raw_rationale, [f.assertion_text for f in facts]
            )
            if hedges:
                logger.info(
                    "Rationale grounding guard hedged discovered claim %r: %s",
                    new_claim.get("claim_name"),
                    "; ".join(hedges),
                )

            claim = AnalysisClaim(
                run_id=run.id,
                claim_name=new_claim.get("claim_name", "Unknown"),
                claim_type="discovered",
                folio_iri=folio_iri,
                confidence=confidence,
                rationale=grounded_rationale,
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

    async def _validate_discovered_mappings(
        self,
        discovered: list[dict],
        facts: list[ExtractedFact],
    ) -> dict:
        """Semantic-fit validation for exploration-lane claim->FOLIO mappings (BUG-22).

        Mirrors IssueSpotStage's batched semantic-fit pass, applied to the
        discovered claims the exploration engine produced. Only claims that
        carry a ``folio_iri`` are validated (an IRI-less LLM/protocol claim has
        no mapping to drop). Concept label + branch are resolved in-memory from
        the loaded FOLIO singleton -- no network call. Degrades gracefully: any
        failure (no FOLIO, LLM error) yields an empty verdict map so exploration
        never breaks.

        Returns a ``{name_key: FitVerdict}`` map for claims needing action.
        """
        if not discovered or self._folio is None:
            return {}

        from app.services.analysis.semantic_fit import FitItem, SemanticFitValidator
        from app.services.folio.concept_resolver import _determine_branch
        from app.services.folio.folio_service import get_owl_class

        fit_items: list[FitItem] = []
        for nc in discovered:
            iri = nc.get("folio_iri")
            if not iri:
                continue
            name_key = (nc.get("claim_name") or "Unknown").strip().lower()
            claim_name = nc.get("claim_name") or "Unknown"
            # Label + branch, in-memory (no network). Fall back to the claim
            # name for the label (adjacency's claim_name already IS the label).
            try:
                owl = get_owl_class(self._folio, iri)
                label = (getattr(owl, "label", None) or claim_name) if owl else claim_name
            except Exception:
                label = claim_name
            try:
                branch = _determine_branch(iri, self._folio)
            except Exception:
                branch = ""
            fit_items.append(
                FitItem(
                    key=name_key,
                    claim_name=claim_name,
                    concept_label=label,
                    branch=branch or "",
                    confidence=float(nc.get("confidence", 0.5) or 0.5),
                )
            )

        if not fit_items:
            return {}

        matter_context = "; ".join(
            f.assertion_text for f in facts[:12] if f.assertion_text
        )[:1500]
        try:
            validator = SemanticFitValidator(self._llm)
            return await validator.validate(matter_context, fit_items)
        except Exception:
            logger.warning(
                "Exploration semantic-fit validation failed; keeping raw mappings",
                exc_info=True,
            )
            return {}
