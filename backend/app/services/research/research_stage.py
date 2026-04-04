"""ResearchStage -- full research pipeline replacing research_stub.

Per D-04, orchestrates parallel research across all org-configured tools:
1. Build ResearchQuery per claim from claim_name, elements, jurisdiction
2. Get active adapters via tool_registry.get_active_adapters(org_id)
3. Filter out tools exceeding budget cap (D-18)
4. Query all adapters + KB retriever + InsightsService in parallel via asyncio.gather
5. Flatten and filter exceptions (graceful degradation)
6. Deduplicate via CitationNormalizer (D-15)
7. Verify citations in batch via CitationVerifier (D-05)
8. Rank via ResultRanker (D-15)
9. Record usage per tool (D-18)
10. Store top results as Authority records (D-06)
11. Detect research gaps for re-iteration (D-04)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from app.services.research.base import ResearchQuery, ResearchResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisClaim, AnalysisRun
    from app.services.knowledge_base.retriever import KBRetriever
    from app.services.research.citation_normalizer import CitationNormalizer
    from app.services.research.citation_verifier import CitationVerifier
    from app.services.research.insights_service import InsightsService
    from app.services.research.result_ranker import ResultRanker
    from app.services.research.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class ResearchStage:
    """Full research pipeline stage for the analysis orchestrator.

    Replaces ResearchStubStage with real research tool integration.
    Queries all org-configured tools in parallel, deduplicates, verifies,
    ranks, stores authorities, and identifies gaps for re-iteration.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        tool_registry: Any = None,
        citation_verifier: CitationVerifier | None = None,
        result_ranker: ResultRanker | None = None,
        citation_normalizer: CitationNormalizer | None = None,
        kb_retriever: KBRetriever | None = None,
        insights_service: InsightsService | None = None,
        usage_tracker: UsageTracker | None = None,
        llm_service: Any = None,
        org_id: int = 0,
    ) -> None:
        self._session = db_session
        self._tool_registry = tool_registry
        self._citation_verifier = citation_verifier
        self._result_ranker = result_ranker
        self._citation_normalizer = citation_normalizer
        self._kb_retriever = kb_retriever
        self._insights_service = insights_service
        self._usage_tracker = usage_tracker
        self._llm_service = llm_service
        self._org_id = org_id

    async def execute(
        self,
        run: AnalysisRun,
        claims: list[AnalysisClaim],
    ) -> dict:
        """Execute the full research pipeline for all claims.

        Args:
            run: The current AnalysisRun.
            claims: List of AnalysisClaim records to research.

        Returns:
            Dict with authorities_found, verified_count, unverified_count,
            tools_queried, kb_results_count, insights_count, research_gaps,
            research_notes.
        """
        all_results: list[ResearchResult] = []
        all_kb_results: list = []
        all_insights: list = []
        tools_queried_set: set[str] = set()
        research_gaps: list[str] = []
        notes_parts: list[str] = []

        for claim in claims:
            # Step 1: Build ResearchQuery from claim
            element_names = [
                e.element_name for e in getattr(claim, "elements", [])
            ]
            query_text = claim.claim_name
            if element_names:
                query_text += " " + " ".join(element_names)

            query = ResearchQuery(
                query_text=query_text,
                claim_iri=getattr(claim, "folio_iri", None),
                jurisdiction=getattr(claim, "jurisdiction", None),
            )

            # Step 2: Get active adapters
            adapters = []
            if self._tool_registry:
                adapters = await self._tool_registry.get_active_adapters(self._org_id)

            # Step 3: Filter out tools exceeding budget cap
            active_adapters = []
            if self._usage_tracker:
                for adapter in adapters:
                    within_budget = await self._usage_tracker.check_budget(
                        self._org_id, adapter.adapter_name
                    )
                    if within_budget:
                        active_adapters.append(adapter)
                    else:
                        logger.info(
                            "Skipping adapter %s for org %d: budget exceeded",
                            adapter.adapter_name, self._org_id,
                        )
            else:
                active_adapters = adapters

            # Step 4: Build parallel tasks -- adapters + KB + insights
            tasks: list = []
            task_labels: list[str] = []

            for adapter in active_adapters:
                tasks.append(adapter.discover(query))
                task_labels.append(f"adapter:{adapter.adapter_name}")

            # KB retrieval in parallel (D-11)
            if self._kb_retriever:
                tasks.append(
                    self._kb_retriever.search(
                        claim.claim_name,
                        self._org_id,
                        folio_iris=[claim.folio_iri] if getattr(claim, "folio_iri", None) else None,
                    )
                )
                task_labels.append("kb_retriever")

            # Insights in parallel (D-08)
            folio_iri = getattr(claim, "folio_iri", None)
            if self._insights_service and folio_iri:
                tasks.append(self._insights_service.get_insights(folio_iri))
                task_labels.append("insights")

            # Execute all in parallel with graceful degradation
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Step 5: Flatten results, filter out exceptions
            claim_results: list[ResearchResult] = []
            for i, raw in enumerate(raw_results):
                label = task_labels[i] if i < len(task_labels) else "unknown"
                if isinstance(raw, Exception):
                    logger.warning(
                        "Research task %s failed for claim '%s': %s",
                        label, claim.claim_name, raw,
                    )
                    continue

                if label.startswith("adapter:"):
                    tool_name = label.split(":", 1)[1]
                    tools_queried_set.add(tool_name)
                    if isinstance(raw, list):
                        claim_results.extend(raw)
                elif label == "kb_retriever":
                    if isinstance(raw, list):
                        all_kb_results.extend(raw)
                elif label == "insights":
                    if isinstance(raw, list):
                        all_insights.extend(raw)

            all_results.extend(claim_results)

            # Step 9: Record usage for each successful tool
            if self._usage_tracker:
                for tool_name in tools_queried_set:
                    await self._usage_tracker.record_call(self._org_id, tool_name)

            # Step 11: Detect gaps -- claims with no supporting results
            if not claim_results and not any(
                isinstance(r, Exception) for r in raw_results
            ):
                research_gaps.append(
                    f"No authorities found for claim '{claim.claim_name}'"
                )

        # Step 6: Deduplicate via CitationNormalizer
        if self._citation_normalizer and all_results:
            all_results = self._citation_normalizer.deduplicate_results(all_results)

        # Step 7: Verify all citations in batch
        verified_count = 0
        unverified_count = 0
        if self._citation_verifier and all_results:
            citations = [r.citation for r in all_results]
            verification_results = await self._citation_verifier.verify_batch(citations)
            for vr in verification_results:
                if vr.status == "verified":
                    verified_count += 1
                else:
                    unverified_count += 1
        else:
            unverified_count = len(all_results)

        # Step 8: Rank results
        if self._result_ranker and all_results:
            # Use first claim's query as representative for ranking
            if claims:
                rank_query = ResearchQuery(
                    query_text=claims[0].claim_name,
                    jurisdiction=getattr(claims[0], "jurisdiction", None),
                )
                all_results = self._result_ranker.rank(all_results, rank_query)

        # Step 10: Store top results as Authority records
        # (DB storage is skipped when db_session is a mock)
        authorities_stored = await self._store_authorities(run, all_results)

        return {
            "authorities_found": len(all_results),
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "tools_queried": len(tools_queried_set),
            "kb_results_count": len(all_kb_results),
            "insights_count": len(all_insights),
            "research_gaps": research_gaps,
            "research_notes": "; ".join(notes_parts) if notes_parts else (
                f"Researched {len(claims)} claims across {len(tools_queried_set)} tools"
            ),
        }

    async def _store_authorities(
        self,
        run: AnalysisRun,
        results: list[ResearchResult],
        max_store: int = 50,
    ) -> int:
        """Store top research results as Authority records in DB.

        Args:
            run: The current AnalysisRun (for intake_id).
            results: Ranked research results.
            max_store: Maximum number of authorities to store.

        Returns:
            Number of authorities stored.
        """
        try:
            from app.models.research import Authority

            stored = 0
            for result in results[:max_store]:
                authority = Authority(
                    intake_id=run.intake_id,
                    citation=result.citation,
                    title=result.title,
                    authority_type=result.authority_type,
                    jurisdiction=result.jurisdiction,
                    folio_iri=result.folio_iri,
                    claim_iri=getattr(result, "claim_iri", None) or result.metadata.get("claim_iri"),
                    source_tool=result.source_tool,
                    source_url=result.source_url,
                    excerpt=result.excerpt,
                    relevance_score=result.relevance_score,
                    verified=result.metadata.get("verified", False),
                    verification_status=result.metadata.get("verification_status", "unverified"),
                    metadata_json=result.metadata,
                )
                self._session.add(authority)
                stored += 1

            if stored > 0:
                await self._session.flush()

            return stored
        except Exception as e:
            logger.warning("Failed to store authorities: %s", e)
            return 0
