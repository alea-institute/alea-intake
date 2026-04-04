"""Issue-spotting stage -- identifies legal claims from extracted facts via LLM.

Uses LLM structured output to identify legal claims from extracted facts,
classifies claims as 'identified' (from narrative) or 'discovered' (adjacent
issues the consumer didn't mention), resolves FOLIO IRIs via ConceptResolver,
detects multiple jurisdictions for parallel analysis, and persists all claims
and elements to the database.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.models.analysis import AnalysisClaim, ClaimElement
from app.services.analysis.schemas import IssueSpotResult

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.analysis import AnalysisIteration, AnalysisRun
    from app.models.fact import ExtractedFact
    from app.services.embedding.service import EmbeddingService
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

ISSUE_SPOT_SYSTEM_PROMPT = """You are a legal issue-spotting assistant. Given a set of extracted facts from a consumer intake, identify all relevant legal claims.

For each claim, provide:
- claim_name: Short descriptive name of the legal claim
- claim_type: "identified" if directly stated in the facts, "discovered" if you infer it from patterns (adjacent issues the consumer may not know about)
- jurisdiction: The jurisdiction where this claim applies (state, federal, etc.)
- confidence: 0.0-1.0 based on how strongly the facts support this claim
- rationale: Brief explanation of why this claim was identified
- is_potential: true if the claim is speculative/discovered and not directly evidenced
- elements: List of required legal elements for this claim, each with element_name and element_description

Also provide:
- jurisdictions: All jurisdictions detected across all claims (for parallel analysis)
- summary: A brief overview of the legal landscape

Return a JSON object with "claims", "jurisdictions", and "summary" fields."""


class IssueSpotStage:
    """Identifies legal claims from extracted facts via LLM + ConceptResolver.

    Stage in the iterative analysis pipeline. Each execution:
    1. Builds a prompt with all extracted facts
    2. Calls LLM for structured claim identification
    3. Resolves FOLIO IRIs for each claim via ConceptResolver
    4. Persists AnalysisClaim and ClaimElement records
    5. Returns stage result dict for pipeline orchestration
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._llm = llm_service
        self._session = db_session
        self._folio = folio
        self._embedding_service = embedding_service

    async def _call_llm(self, facts: list[ExtractedFact]) -> dict[str, Any]:
        """Call LLM with facts and return parsed JSON response.

        Separated for easy mocking in tests.
        """
        facts_text = "\n".join(
            f"- [{f.fact_type}] (confidence: {f.confidence:.2f}) {f.assertion_text}"
            for f in facts
        )

        messages = [
            {"role": "system", "content": ISSUE_SPOT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extracted facts:\n{facts_text}"},
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
            return {"claims": [], "jurisdictions": [], "summary": ""}

        init_kwargs: dict[str, Any] = {
            "api_key": config.get("api_key"),
            "model": config.get("model"),
        }
        if "endpoint" in config:
            init_kwargs["endpoint"] = config["endpoint"]

        model = model_cls(**init_kwargs)
        response = await model.json_async(*messages)
        return response.data

    async def _resolve_folio_iri(self, claim_name: str) -> str | None:
        """Resolve a claim name to a FOLIO IRI via ConceptResolver.

        Returns the best-match IRI or None if resolution fails/unavailable.
        Separated for easy mocking in tests.
        """
        try:
            from app.services.folio.concept_resolver import resolve_concepts

            resolved = await resolve_concepts(
                text=claim_name,
                folio=self._folio,
                embedding_service=self._embedding_service,
            )
            if resolved:
                return resolved[0].iri
        except Exception:
            logger.debug(
                "ConceptResolver failed for claim '%s', proceeding without IRI",
                claim_name,
                exc_info=True,
            )
        return None

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        facts: list[ExtractedFact],
    ) -> dict:
        """Execute issue-spotting stage.

        Args:
            run: The current AnalysisRun.
            iteration: The current AnalysisIteration.
            facts: List of ExtractedFact records to analyze.

        Returns:
            Dict with claims_count, jurisdictions, summary, and claims list.
        """
        if not facts:
            return {
                "claims_count": 0,
                "jurisdictions": [],
                "summary": "No facts to analyze",
                "claims": [],
            }

        # Call LLM for issue-spotting
        raw_result = await self._call_llm(facts)

        # Parse through Pydantic schema for validation
        try:
            result = IssueSpotResult.model_validate(raw_result)
        except Exception:
            logger.warning("Failed to parse LLM issue-spot output", exc_info=True)
            return {
                "claims_count": 0,
                "jurisdictions": [],
                "summary": "Failed to parse LLM output",
                "claims": [],
            }

        persisted_claims: list[dict] = []

        for spotted in result.claims:
            # Resolve FOLIO IRI if folio and embedding_service are available
            folio_iri = spotted.folio_iri
            if self._folio is not None and self._embedding_service is not None and not folio_iri:
                folio_iri = await self._resolve_folio_iri(spotted.claim_name)

            # Persist AnalysisClaim
            claim = AnalysisClaim(
                run_id=run.id,
                claim_name=spotted.claim_name,
                claim_type=spotted.claim_type,
                folio_iri=folio_iri,
                jurisdiction=spotted.jurisdiction,
                confidence=spotted.confidence,
                rationale=spotted.rationale,
                is_potential=spotted.is_potential,
                iteration_discovered=iteration.iteration_number,
            )
            self._session.add(claim)
            await self._session.flush()

            # Persist ClaimElement records
            for elem in spotted.elements:
                element = ClaimElement(
                    claim_id=claim.id,
                    element_name=elem.element_name,
                    element_description=elem.element_description,
                    jurisdiction=elem.jurisdiction or spotted.jurisdiction,
                )
                self._session.add(element)

            await self._session.flush()

            persisted_claims.append({
                "id": claim.id,
                "claim_name": claim.claim_name,
                "claim_type": claim.claim_type,
                "folio_iri": claim.folio_iri,
                "jurisdiction": claim.jurisdiction,
                "confidence": claim.confidence,
                "is_potential": claim.is_potential,
                "elements_count": len(spotted.elements),
            })

        return {
            "claims_count": len(persisted_claims),
            "jurisdictions": result.jurisdictions,
            "summary": result.summary,
            "claims": persisted_claims,
        }
