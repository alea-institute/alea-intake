"""Fact-mapping stage -- maps facts to claims/elements with composite confidence.

Creates many-to-many FactClaimMapping records linking extracted facts to
analysis claims and their elements. Each mapping uses composite confidence
scoring (D-05) combining LLM mapping confidence, ConceptResolver match
strength, and source fact confidence with org-configurable weights.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.models.analysis import ClaimElement, FactClaimMapping
from app.services.analysis.schemas import ConfidenceWeights, FactMapResult
from app.services.analysis.scoring import compute_composite_confidence

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisClaim, AnalysisIteration, AnalysisRun
    from app.models.fact import ExtractedFact
    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

FACT_MAP_SYSTEM_PROMPT = """You are a legal fact-mapping assistant. Given a set of extracted facts and identified legal claims with their required elements, create mappings from facts to claim elements.

For each mapping, provide:
- fact_id: The ID of the fact being mapped
- claim_name: The name of the claim this fact supports
- element_name: The specific element of the claim this fact addresses (or null if general claim support)
- llm_confidence: 0.0-1.0 confidence that this fact supports this claim/element
- mapping_rationale: Brief explanation of how this fact supports this element

Also identify any unmapped_facts (fact IDs that don't clearly support any claim).

Rules:
1. One fact can map to multiple claims and elements (many-to-many).
2. Only create mappings where there is genuine factual support.
3. Be conservative with confidence -- only high confidence for clear, direct support.
4. Every fact should either be mapped or listed as unmapped.

Return a JSON object with "mappings" and "unmapped_facts" arrays."""


class FactMapStage:
    """Maps facts to claims/elements with composite confidence scoring.

    Stage in the iterative analysis pipeline. Each execution:
    1. Builds a prompt with facts and claims for LLM mapping
    2. Calls LLM for structured fact-to-claim mapping
    3. Computes composite confidence for each mapping
    4. Persists FactClaimMapping records
    5. Updates ClaimElement satisfaction status
    6. Returns stage result dict for pipeline orchestration
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        confidence_weights: ConfidenceWeights | None = None,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._llm = llm_service
        self._session = db_session
        self._weights = confidence_weights
        self._folio = folio
        self._embedding_service = embedding_service

    async def _call_llm(
        self, facts: list[ExtractedFact], claims: list[AnalysisClaim]
    ) -> dict[str, Any]:
        """Call LLM with facts and claims, return parsed JSON response.

        Separated for easy mocking in tests.
        """
        facts_text = "\n".join(
            f"- Fact #{f.id}: [{f.fact_type}] (confidence: {f.confidence:.2f}) {f.assertion_text}"
            for f in facts
        )

        claims_text = ""
        for c in claims:
            claims_text += f"\nClaim: {c.claim_name} (type: {c.claim_type}, jurisdiction: {c.jurisdiction})\n"
            # Get elements for this claim
            from sqlalchemy import select

            elements_result = await self._session.execute(
                select(ClaimElement).where(ClaimElement.claim_id == c.id)
            )
            elements = elements_result.scalars().all()
            for elem in elements:
                claims_text += f"  - Element: {elem.element_name}: {elem.element_description or 'N/A'}\n"

        messages = [
            {"role": "system", "content": FACT_MAP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extracted facts:\n{facts_text}\n\nIdentified claims:\n{claims_text}",
            },
        ]

        config = self._llm.get_client_config()

        from alea_llm_client import AnthropicModel, GoogleModel, OpenAIModel, VLLMModel

        _provider_map = {
            "openai": OpenAIModel,
            "anthropic": AnthropicModel,
            "google": GoogleModel,
            "vllm": VLLMModel,
        }

        model_cls = _provider_map.get(config["provider"])
        if model_cls is None:
            logger.error("Unknown LLM provider: %s", config["provider"])
            return {"mappings": [], "unmapped_facts": []}

        init_kwargs: dict[str, Any] = {
            "api_key": config.get("api_key"),
            "model": config.get("model"),
        }
        if "endpoint" in config:
            init_kwargs["endpoint"] = config["endpoint"]

        model = model_cls(**init_kwargs)
        response = await model.json_async(messages=messages)
        return response.data

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        facts: list[ExtractedFact],
        claims: list[AnalysisClaim],
    ) -> dict:
        """Execute fact-mapping stage.

        Args:
            run: The current AnalysisRun.
            iteration: The current AnalysisIteration.
            facts: List of ExtractedFact records to map.
            claims: List of AnalysisClaim records to map to.

        Returns:
            Dict with mappings_created, unmapped_facts, avg_confidence.
        """
        if not facts or not claims:
            return {
                "mappings_created": 0,
                "unmapped_facts": [f.id for f in facts] if facts else [],
                "avg_confidence": 0.0,
            }

        # Call LLM for fact mapping
        raw_result = await self._call_llm(facts, claims)

        # Parse through Pydantic schema
        try:
            result = FactMapResult.model_validate(raw_result)
        except Exception:
            logger.warning("Failed to parse LLM fact-map output", exc_info=True)
            return {
                "mappings_created": 0,
                "unmapped_facts": [f.id for f in facts],
                "avg_confidence": 0.0,
            }

        # Build lookup tables
        fact_by_id = {f.id: f for f in facts}
        claim_by_name = {c.claim_name: c for c in claims}

        # Pre-load all elements for claims
        from sqlalchemy import select

        all_elements: dict[int, list[ClaimElement]] = {}
        for c in claims:
            elems_result = await self._session.execute(
                select(ClaimElement).where(ClaimElement.claim_id == c.id)
            )
            all_elements[c.id] = list(elems_result.scalars().all())

        created_mappings: list[FactClaimMapping] = []
        total_confidence = 0.0

        for mapping_schema in result.mappings:
            # Resolve claim
            claim = claim_by_name.get(mapping_schema.claim_name)
            if claim is None:
                logger.debug(
                    "Claim '%s' from LLM mapping not found, skipping",
                    mapping_schema.claim_name,
                )
                continue

            # Resolve element (optional)
            element_id = None
            if mapping_schema.element_name:
                claim_elements = all_elements.get(claim.id, [])
                for elem in claim_elements:
                    if elem.element_name == mapping_schema.element_name:
                        element_id = elem.id
                        break

            # Get fact confidence
            source_fact = fact_by_id.get(mapping_schema.fact_id)
            fact_confidence = source_fact.confidence if source_fact else 0.5

            # Get concept confidence (default 0.5 if FOLIO unavailable)
            concept_confidence = 0.5

            # Compute composite confidence
            composite = compute_composite_confidence(
                llm_confidence=mapping_schema.llm_confidence,
                concept_confidence=concept_confidence,
                fact_confidence=fact_confidence,
                weights=self._weights,
            )

            # Create FactClaimMapping record
            fcm = FactClaimMapping(
                fact_id=mapping_schema.fact_id,
                claim_id=claim.id,
                element_id=element_id,
                confidence=composite,
                llm_confidence=mapping_schema.llm_confidence,
                concept_confidence=concept_confidence,
                fact_confidence=fact_confidence,
                mapping_rationale=mapping_schema.mapping_rationale,
                iteration_number=iteration.iteration_number,
            )
            self._session.add(fcm)
            created_mappings.append(fcm)
            total_confidence += composite

        await self._session.flush()

        # Update element satisfaction based on mappings
        await self._update_element_satisfaction(claims, all_elements)

        avg_confidence = total_confidence / len(created_mappings) if created_mappings else 0.0

        return {
            "mappings_created": len(created_mappings),
            "unmapped_facts": result.unmapped_facts,
            "avg_confidence": round(avg_confidence, 4),
        }

    async def _update_element_satisfaction(
        self,
        claims: list[AnalysisClaim],
        all_elements: dict[int, list[ClaimElement]],
    ) -> None:
        """Update ClaimElement satisfaction based on FactClaimMapping records.

        An element is marked satisfied if at least one mapping references it
        with composite confidence > 0.5.
        """
        from sqlalchemy import select

        for claim in claims:
            elements = all_elements.get(claim.id, [])
            for elem in elements:
                # Find mappings for this element
                mappings_result = await self._session.execute(
                    select(FactClaimMapping).where(
                        FactClaimMapping.claim_id == claim.id,
                        FactClaimMapping.element_id == elem.id,
                    )
                )
                mappings = mappings_result.scalars().all()

                if mappings:
                    max_confidence = max(m.confidence for m in mappings)
                    if max_confidence > 0.5:
                        elem.is_satisfied = True
                        elem.satisfaction_confidence = max_confidence
                        self._session.add(elem)

        await self._session.flush()
