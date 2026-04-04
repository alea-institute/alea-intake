"""Three-layer exploration engine with hybrid parallel execution and multi-round stability.

Core class implementing D-05 (hybrid parallel) and D-06 (multi-round stability):
- Cheap LLM wide-net scan runs in parallel with sequential
  FOLIO adjacency -> protocol matching -> expensive LLM pipeline
- Multi-round loop with configurable min_rounds, max_rounds, stability_threshold
- Deduplication via ConceptResolver merging results to FOLIO IRIs

Used by ExploreStage to run exploration between issue_spot and research
in the AnalysisOrchestrator pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.services.exploration.layers import (
    layer_cheap_llm,
    layer_expensive_llm,
    layer_folio_adjacency,
    layer_protocol_match,
)
from app.services.exploration.schemas import (
    ExplorationConfig,
    ExplorationResult,
    ExplorationRoundResult,
    ExplorationStageResult,
)

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService
    from app.services.screening.protocol_service import ProtocolService

logger = logging.getLogger(__name__)


@dataclass
class _ExplorationContext:
    """Internal context passed between round executions."""

    facts_text: str
    known_claims: list
    known_claim_iris: set
    known_claim_names: set
    active_protocols: list
    config: ExplorationConfig
    all_discovered: list = field(default_factory=list)


# Lazy import to avoid circular dependency at module level
async def resolve_concepts(text, folio, embedding_service, **kwargs):
    """Lazy wrapper for ConceptResolver.resolve_concepts."""
    from app.services.folio.concept_resolver import resolve_concepts as _resolve

    return await _resolve(text, folio, embedding_service, **kwargs)


class ExplorationEngine:
    """Three-layer exploration engine with hybrid parallel execution (D-05).

    Runs four exploration layers in a hybrid parallel pattern:
    - Branch A: Cheap LLM wide-net scan (fast, broad)
    - Branch B: Sequential FOLIO adjacency -> protocol matching -> expensive LLM

    Multi-round stability detection (D-06): loops through rounds until no new
    issues are discovered or max_rounds reached, respecting min_rounds.

    Deduplication merges results from all layers via ConceptResolver to FOLIO IRIs.
    """

    def __init__(
        self,
        folio: FOLIO | None,
        llm_service: LLMService,
        embedding_service: EmbeddingService | None,
        db_session: AsyncSession,
        org_config: dict | None = None,
        protocol_service: ProtocolService | None = None,
    ) -> None:
        self._folio = folio
        self._llm = llm_service
        self._embedding_service = embedding_service
        self._session = db_session
        self._org_config = org_config or {}
        self._protocol_service = protocol_service

        # Parse exploration config from org settings
        exploration_raw = self._org_config.get("exploration", {})
        if isinstance(exploration_raw, ExplorationConfig):
            self._config = exploration_raw
        elif isinstance(exploration_raw, dict):
            self._config = ExplorationConfig(**exploration_raw)
        else:
            self._config = ExplorationConfig()

    async def explore(
        self,
        run: Any,
        iteration: Any,
        claims: list,
        facts: list,
    ) -> ExplorationStageResult:
        """Main entry point: run multi-round exploration with stability detection.

        Builds facts_text from facts list. Loads active protocols via protocol_service.
        Loops through rounds respecting min_rounds, max_rounds, and stability_threshold.

        Args:
            run: The current AnalysisRun.
            iteration: The current AnalysisIteration.
            claims: List of existing AnalysisClaim objects.
            facts: List of ExtractedFact objects.

        Returns:
            ExplorationStageResult with all rounds, new claims, and triggered protocols.
        """
        # Load active protocols
        active_protocols: list = []
        if self._protocol_service:
            try:
                active_protocols = await self._protocol_service.get_active_protocols()
            except Exception:
                logger.warning("Failed to load active protocols", exc_info=True)

        # Build context
        context = self._build_context(claims, facts, active_protocols)

        all_rounds: list[ExplorationRoundResult] = []
        all_new_claims: list[dict] = []
        all_triggered_protocols: list[dict] = []
        total_new_issues = 0

        for round_num in range(1, self._config.max_rounds + 1):
            round_result = await self._run_exploration_round(context, round_num)
            all_rounds.append(round_result)
            total_new_issues += round_result.new_issues_count

            # Collect new claims and triggered protocols from this round
            for r in round_result.results:
                if r.is_new_issue:
                    all_new_claims.append({
                        "claim_name": r.claim_name or r.description,
                        "folio_iri": r.folio_iri,
                        "confidence": r.confidence,
                        "source_layer": r.source_layer,
                        "rationale": r.rationale,
                    })
                if r.protocol_id is not None:
                    all_triggered_protocols.append({
                        "protocol_id": r.protocol_id,
                        "claim_name": r.claim_name,
                        "confidence": r.confidence,
                    })

            # Update context with newly discovered issues for next round
            for r in round_result.results:
                if r.is_new_issue and r.folio_iri:
                    context.known_claim_iris.add(r.folio_iri)
                if r.is_new_issue and r.claim_name:
                    context.known_claim_names.add(r.claim_name.lower())

            # Stability check: stop if stable and min_rounds met
            if round_num >= self._config.min_rounds and round_result.is_stable:
                break

        return ExplorationStageResult(
            rounds=all_rounds,
            total_new_issues=total_new_issues,
            new_claims=all_new_claims,
            triggered_protocols=all_triggered_protocols,
        )

    def _build_context(
        self,
        claims: list,
        facts: list,
        active_protocols: list,
    ) -> _ExplorationContext:
        """Build exploration context from claims, facts, and protocols."""
        facts_text = "\n".join(
            f"- [{getattr(f, 'fact_type', 'fact')}] {getattr(f, 'assertion_text', str(f))}"
            for f in facts
        ) if facts else "No facts available"

        known_iris = {c.folio_iri for c in claims if getattr(c, "folio_iri", None)}
        known_names = {c.claim_name.lower() for c in claims if getattr(c, "claim_name", None)}

        return _ExplorationContext(
            facts_text=facts_text,
            known_claims=claims,
            known_claim_iris=known_iris,
            known_claim_names=known_names,
            active_protocols=active_protocols,
            config=self._config,
        )

    async def _run_exploration_round(
        self,
        context: _ExplorationContext,
        round_num: int,
    ) -> ExplorationRoundResult:
        """Execute a single exploration round with hybrid parallel approach (D-05).

        Branch A: Cheap LLM wide-net scan (fast)
        Branch B: Sequential FOLIO adjacency -> protocol matching -> expensive LLM

        Both branches run in parallel via asyncio.gather. Results are merged
        and deduplicated via ConceptResolver.
        """
        # Branch A: Cheap LLM (fast, broad)
        cheap_task = layer_cheap_llm(
            self._llm, context.facts_text, context.known_claims, self._org_config,
        )

        # Branch B: Sequential precision pipeline
        async def _sequential_pipeline() -> list[ExplorationResult]:
            folio_results = await layer_folio_adjacency(
                self._folio, context.known_claims, context.config,
            )
            protocol_results = await layer_protocol_match(
                context.active_protocols, context.facts_text, folio_results,
            )
            expensive_results = await layer_expensive_llm(
                self._llm, context.facts_text, context.known_claims,
                folio_results, protocol_results, self._org_config,
            )
            return folio_results + protocol_results + expensive_results

        sequential_task = _sequential_pipeline()

        # Run both branches in parallel
        try:
            cheap_results, sequential_results = await asyncio.gather(
                cheap_task, sequential_task, return_exceptions=True,
            )
        except Exception:
            logger.warning("Parallel exploration failed", exc_info=True)
            cheap_results = []
            sequential_results = []

        # Handle exceptions from gather
        if isinstance(cheap_results, Exception):
            logger.warning("Cheap LLM branch failed: %s", cheap_results)
            cheap_results = []
        if isinstance(sequential_results, Exception):
            logger.warning("Sequential pipeline failed: %s", sequential_results)
            sequential_results = []

        # Merge all results
        all_results = list(cheap_results) + list(sequential_results)

        # Deduplicate via ConceptResolver
        deduped = await self._deduplicate_results(all_results)

        # Filter by confidence threshold
        filtered = [
            r for r in deduped
            if r.confidence >= self._config.exploration_confidence_threshold
        ]

        # Mark is_new_issue based on whether IRI/name is already known
        for r in filtered:
            if r.folio_iri and r.folio_iri in context.known_claim_iris:
                r.is_new_issue = False
            elif r.claim_name and r.claim_name.lower() in context.known_claim_names:
                r.is_new_issue = False

        new_issues_count = sum(1 for r in filtered if r.is_new_issue)
        is_stable = new_issues_count <= self._config.stability_threshold

        return ExplorationRoundResult(
            round_number=round_num,
            results=filtered,
            new_issues_count=new_issues_count,
            is_stable=is_stable,
        )

    async def _deduplicate_results(
        self,
        all_results: list[ExplorationResult],
    ) -> list[ExplorationResult]:
        """Deduplicate exploration results via FOLIO IRI merging.

        1. Group results with same folio_iri -- keep highest confidence
        2. For results without folio_iri, try ConceptResolver
        3. Keep truly unresolvable results as-is (not dropped)

        Args:
            all_results: Raw results from all layers.

        Returns:
            Deduplicated list of ExplorationResult.
        """
        if not all_results:
            return []

        # Group by folio_iri
        iri_groups: dict[str, list[ExplorationResult]] = {}
        unresolved: list[ExplorationResult] = []

        for r in all_results:
            if r.folio_iri:
                iri_groups.setdefault(r.folio_iri, []).append(r)
            else:
                unresolved.append(r)

        # For unresolved, try ConceptResolver
        if unresolved and self._folio and self._embedding_service:
            for r in unresolved:
                try:
                    resolved = await resolve_concepts(
                        r.claim_name or r.description,
                        self._folio,
                        self._embedding_service,
                    )
                    if resolved:
                        r.folio_iri = resolved[0].iri
                        iri_groups.setdefault(r.folio_iri, []).append(r)
                    else:
                        # Unresolvable -- keep as-is
                        iri_groups.setdefault(f"_unresolved_{id(r)}", []).append(r)
                except Exception:
                    logger.debug("ConceptResolver failed for '%s'", r.claim_name, exc_info=True)
                    iri_groups.setdefault(f"_unresolved_{id(r)}", []).append(r)
        else:
            # No FOLIO/embedding -- keep unresolved as-is
            for r in unresolved:
                iri_groups.setdefault(f"_unresolved_{id(r)}", []).append(r)

        # Merge groups: keep the result with highest confidence per IRI
        deduplicated: list[ExplorationResult] = []
        for _iri, group in iri_groups.items():
            best = max(group, key=lambda r: r.confidence)
            deduplicated.append(best)

        return deduplicated
