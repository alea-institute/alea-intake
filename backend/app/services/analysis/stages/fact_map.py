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
from app.services.analysis.schemas import ConfidenceWeights, FactMappingSchema
from app.services.analysis.scoring import compute_composite_confidence
from app.services.llm_bounds import (
    DEFAULT_CONCURRENCY,
    batched,
    bounded_call,
    compact_instruction,
    gather_bounded,
    limit_client_retries,
    list_field,
    showcase_caps,
    validate_items,
)

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisClaim, AnalysisIteration, AnalysisRun
    from app.models.fact import ExtractedFact
    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Output bounds (2026-11-08 live run): mapping 93 facts in one call sent ~8,200
# input tokens and ran to the 8192-token output ceiling, so every reply was
# truncated JSON. Map facts in small concurrent batches instead; a failed batch
# retries once at half size, then contributes no mappings.
FACT_BATCH_SIZE = 20
MAX_MAPPINGS_PER_FACT = 3

FACT_MAP_SYSTEM_PROMPT = """You are a legal fact-mapping assistant. Given a set of extracted facts and identified legal claims with their required elements, create mappings from facts to claim elements.

For each mapping, provide:
- fact_id: The ID of the fact being mapped
- claim_name: The name of the claim this fact supports
- element_name: The specific element of the claim this fact addresses (or null if general claim support)
- llm_confidence: 0.0-1.0 confidence that this fact supports this claim/element
- mapping_rationale: One short sentence (at most 20 words) on how this fact supports this element

Also identify any unmapped_facts (fact IDs that don't clearly support any claim).

Rules:
1. One fact can map to multiple claims and elements (many-to-many), but give at
   most 3 mappings per fact: its strongest ones.
2. Only create mappings where there is genuine factual support.
3. Be conservative with confidence -- only high confidence for clear, direct support.
4. Every fact should either be mapped or listed as unmapped.
5. Use claim and element names exactly as given. Do not restate the facts.

Return a JSON object with "mappings" and "unmapped_facts" arrays. Reply with exactly
one JSON object and nothing else: no prose, no markdown fences, no placeholder or
example object, and no "Correction:" or second attempt."""


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

    async def _claims_text(self, claims: list[AnalysisClaim]) -> str:
        """Describe claims and their elements for the prompt (reads the DB)."""
        from sqlalchemy import select

        claims_text = ""
        for c in claims:
            claims_text += f"\nClaim: {c.claim_name} (type: {c.claim_type}, jurisdiction: {c.jurisdiction})\n"
            elements_result = await self._session.execute(
                select(ClaimElement).where(ClaimElement.claim_id == c.id)
            )
            elements = elements_result.scalars().all()
            for elem in elements:
                claims_text += f"  - Element: {elem.element_name}: {elem.element_description or 'N/A'}\n"
        return claims_text

    async def _call_llm(
        self,
        facts: list[ExtractedFact],
        claims: list[AnalysisClaim],
        compact: bool = False,
        claims_text: str | None = None,
    ) -> dict[str, Any]:
        """Call LLM with facts and claims, return parsed JSON response.

        Separated for easy mocking in tests. Pass ``claims_text`` when calls
        run concurrently: building it reads the shared AsyncSession.
        """
        facts_text = "\n".join(
            f"- Fact #{f.id}: [{f.fact_type}] (confidence: {f.confidence:.2f}) {f.assertion_text}"
            for f in facts
        )

        if claims_text is None:
            claims_text = await self._claims_text(claims)

        messages = [
            {"role": "system", "content": FACT_MAP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extracted facts:\n{facts_text}\n\nIdentified claims:\n{claims_text}",
            },
        ]
        caps = showcase_caps()
        if caps is not None:
            messages.append({
                "role": "system",
                "content": (
                    f"Give at most {caps.mappings_per_fact} mappings per fact, only for "
                    "facts that support one of the claims above; list every other fact "
                    "id in unmapped_facts. Each mapping_rationale is under "
                    f"{caps.rationale_words} words."
                ),
            })
        if compact:
            messages.append({"role": "system", "content": compact_instruction(len(facts) * 2)})

        model = self._llm.create_client()
        limit_client_retries(model)
        response = await model.json_async(messages=messages)
        return response.data

    async def _map_batch(
        self, batch: list[ExtractedFact], claims: list[AnalysisClaim], claims_text: str
    ) -> tuple[list[FactMappingSchema], list[int]] | None:
        """Map one batch; on failure retry once with half the facts.

        Returns None when both attempts fail (the batch contributes nothing).
        """
        retry_batch = batch[: max(1, len(batch) // 2)]

        async def call(compact: bool) -> Any:
            facts = retry_batch if compact else batch
            return await self._call_llm(facts, claims, compact=compact, claims_text=claims_text)

        def parse(raw: Any) -> tuple[list[FactMappingSchema], list[int]] | None:
            items = list_field(raw, "mappings")
            if items is None:
                return None
            mappings = validate_items(items, FactMappingSchema, stage="fact_map")
            unmapped = raw.get("unmapped_facts", []) if isinstance(raw, dict) else []
            ids = [i for i in unmapped if isinstance(i, int)] if isinstance(unmapped, list) else []
            return mappings, ids

        return await bounded_call(call, parse, stage="fact_map", default=None)

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

        # Read claims once, then run the LLM batches concurrently; the batches
        # never touch the AsyncSession.
        claims_text = await self._claims_text(claims)
        batches = batched(facts, FACT_BATCH_SIZE)
        outcomes = await gather_bounded(
            [
                (lambda b=b: self._map_batch(b, claims, claims_text))
                for b in batches
            ],
            concurrency=DEFAULT_CONCURRENCY,
        )

        mapping_schemas: list[FactMappingSchema] = []
        unmapped_ids: list[int] = []
        failed = 0
        for batch, outcome in zip(batches, outcomes):
            if outcome is None:
                failed += 1
                unmapped_ids.extend(f.id for f in batch)
                continue
            mapping_schemas.extend(outcome[0])
            unmapped_ids.extend(outcome[1])
        if failed:
            logger.warning(
                "fact_map: %d of %d batches produced no mappings", failed, len(batches)
            )
        if failed == len(batches):
            return {
                "mappings_created": 0,
                "unmapped_facts": [f.id for f in facts],
                "avg_confidence": 0.0,
            }

        # Cap mappings per fact (the prompt asks for at most three).
        caps = showcase_caps()
        per_fact_cap = (
            min(MAX_MAPPINGS_PER_FACT, caps.mappings_per_fact) if caps else MAX_MAPPINGS_PER_FACT
        )
        per_fact: dict[int, int] = {}
        capped: list[FactMappingSchema] = []
        for m in mapping_schemas:
            per_fact[m.fact_id] = per_fact.get(m.fact_id, 0) + 1
            if per_fact[m.fact_id] <= per_fact_cap:
                capped.append(m)

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

        for mapping_schema in capped:
            # Resolve claim
            claim = claim_by_name.get(mapping_schema.claim_name)
            if claim is None:
                logger.debug("Claim from LLM mapping not found for run %d; skipping", run.id)
                continue

            # Resolve element (optional)
            element_id = None
            if mapping_schema.element_name:
                claim_elements = all_elements.get(claim.id, [])
                for elem in claim_elements:
                    if elem.element_name == mapping_schema.element_name:
                        element_id = elem.id
                        break

            # D03 (fact->element linkage integrity, RUB-03): a valid linkage must
            # connect a REAL client fact to the element it actually supports. Drop
            # three kinds of bogus linkage the LLM occasionally emits:
            #   (a) a fact_id that does not correspond to any extracted fact
            #       (a hallucinated reference),
            #   (b) a named element that does not exist on the resolved claim
            #       (element_name given but no match — the linkage points at an
            #       element the claim does not have), and
            #   (c) an empty mapping_rationale (a genuine linkage explains, in
            #       prose, HOW the fact supports the element).
            source_fact = fact_by_id.get(mapping_schema.fact_id)
            if source_fact is None:
                logger.debug(
                    "Dropping mapping with unknown fact_id=%s (RUB-03 linkage guard)",
                    mapping_schema.fact_id,
                )
                continue
            if mapping_schema.element_name and element_id is None:
                logger.debug("Dropping mapping naming an absent element for claim %d", claim.id)
                continue
            if not (mapping_schema.mapping_rationale or "").strip():
                logger.debug(
                    "Dropping mapping with empty rationale for fact #%s (RUB-03 "
                    "linkage guard)",
                    mapping_schema.fact_id,
                )
                continue

            # Get fact confidence
            fact_confidence = source_fact.confidence

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
            "unmapped_facts": unmapped_ids,
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
