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
from app.services.analysis.rationale_guard import ground_rationale
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

Surface latent, unspoken issues that the FACTS fairly raise even when the consumer did not name them. Consumers routinely omit the most consequential relief because they do not know it exists. Treat these as "discovered" claims (claim_type="discovered", is_potential=true) and give an honest confidence reflecting how strongly the facts support them.

Latent-issue triggers (a general checklist -- if the facts show the trigger, ALSO consider the associated issue). This is not exhaustive and not client-specific; apply the same principle to any comparable fact pattern:
- Domestic-violence facts (grabbing, hitting, bruising, choking, threats, stalking, coercive control) -> Order for Protection / restraining order and safety planning; and, in an immigration context, VAWA self-petition, U-visa (victim of qualifying crime), or T-visa (trafficking).
- A scheduled removal/immigration hearing, an order of removal, or a missed hearing -> in-absentia removal risk and motion to reopen / reschedule.
- Habitability facts in a tenancy (mold, no heat, no water, pests, serious disrepair, code violations) -> breach of the implied warranty of habitability, repair-and-deduct, or rent escrow / rent withholding.
- Child custody combined with flight or abduction indicators (threats to leave the state or country, hidden passports, prior disappearance, foreign ties) -> emergency/ex parte custody and child-abduction-risk relief (e.g., UCCJEA emergency jurisdiction, passport holds).

Apply these as principled, generalizable heuristics -- not a fixed script. Only surface an issue when the facts fairly raise it. Do NOT fabricate or speculate beyond what the facts support: no invented parties, injuries, dates, or claims unsupported by the record. When in doubt, lower the confidence rather than omit a fairly-raised issue, but never assert an issue the facts do not support.

RATIONALE GROUNDING (STRICT -- fabrication is the worst failure in this product): the rationale prose may reference ONLY facts actually present in the record. NEVER assert that evidence, documentation, corroboration, records, testimony, or proof EXISTS unless a fact explicitly states so. In particular, do NOT upgrade a client's own report into documented proof: if the client says they have a condition but the record shows no documentation, write "the client reports X" or "the reported X" -- NEVER "the doctor's documentation of X", "the doctor has noted X", "medical records show X", or "the police report confirms X". When a supporting document is not in the record, omit the reference rather than embellish. Prefer duller, provably-grounded prose over confident prose that overstates the evidence.

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
        response = await model.json_async(messages=messages)
        return response.data

    async def _resolve_folio_concept(self, claim_name: str) -> Any | None:
        """Resolve a claim name to a FOLIO concept via ConceptResolver.

        Returns the best-match ResolvedConcept (carrying iri/label/branch) or
        None if resolution fails/unavailable. Separated for easy mocking.
        """
        try:
            from app.services.folio.concept_resolver import resolve_concepts

            resolved = await resolve_concepts(
                text=claim_name,
                folio=self._folio,
                embedding_service=self._embedding_service,
            )
            if resolved:
                return resolved[0]
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

        # Dedupe against claims already persisted for this run: the
        # orchestrator re-runs issue_spot every iteration over the SAME facts,
        # which re-persisted identical claims each pass (observed live:
        # 'Nonpayment of Rent' x3 in one run).
        from sqlalchemy import select

        existing_rows = await self._session.execute(
            select(AnalysisClaim.claim_name).where(AnalysisClaim.run_id == run.id)
        )
        seen_names = {(n or "").strip().lower() for (n,) in existing_rows.all()}

        # Pass 1: dedupe + resolve FOLIO concepts (iri/label/branch) for each new
        # claim. We collect resolutions so a single batched semantic-fit pass can
        # validate them before persistence (BUG-21).
        from app.services.analysis.semantic_fit import FitItem, SemanticFitValidator

        new_claims: list[Any] = []          # spotted claim schemas surviving dedupe
        resolutions: dict[str, Any] = {}    # name_key -> ResolvedConcept | None
        for spotted in result.claims:
            name_key = (spotted.claim_name or "").strip().lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            resolved = None
            if (
                self._folio is not None
                and self._embedding_service is not None
                and not spotted.folio_iri
            ):
                resolved = await self._resolve_folio_concept(spotted.claim_name)
            resolutions[name_key] = resolved
            new_claims.append(spotted)

        # Semantic-fit validation (BUG-21): geographic/placeholder/branch-mismatch
        # rejection + confidence recalibration, one LLM call per analysis over the
        # whole batch. A wrong mapping is cleared so it can neither be presented at
        # false confidence nor seed the adjacency fan-out into unrelated concepts.
        fit_items: list[FitItem] = []
        for spotted in new_claims:
            name_key = (spotted.claim_name or "").strip().lower()
            resolved = resolutions.get(name_key)
            if resolved is not None and getattr(resolved, "iri", None):
                fit_items.append(
                    FitItem(
                        key=name_key,
                        claim_name=spotted.claim_name,
                        concept_label=getattr(resolved, "label", "") or "",
                        branch=getattr(resolved, "branch", "") or "",
                        confidence=spotted.confidence,
                    )
                )

        fit_verdicts: dict[str, Any] = {}
        if fit_items:
            matter_context = "; ".join(
                f.assertion_text for f in facts[:12] if f.assertion_text
            )[:1500]
            validator = SemanticFitValidator(self._llm)
            fit_verdicts = await validator.validate(matter_context, fit_items)

        persisted_claims: list[dict] = []

        for spotted in new_claims:
            name_key = (spotted.claim_name or "").strip().lower()
            resolved = resolutions.get(name_key)
            folio_iri = spotted.folio_iri or (
                getattr(resolved, "iri", None) if resolved is not None else None
            )
            confidence = spotted.confidence

            # Apply semantic-fit verdict: drop the wrong IRI and/or recalibrate.
            verdict = fit_verdicts.get(name_key)
            if verdict is not None:
                if verdict.drop_iri:
                    folio_iri = None
                confidence = verdict.adjusted_confidence

            # BUG-28: deterministic grounding backstop -- hedge any rationale
            # clause that asserts evidence/documentation the fact record does
            # not contain (RUB-04 GATE). No-op when the LLM prose is grounded.
            grounded_rationale, hedges = ground_rationale(
                spotted.rationale, [f.assertion_text for f in facts]
            )
            if hedges:
                logger.info(
                    "Rationale grounding guard hedged claim %r: %s",
                    spotted.claim_name,
                    "; ".join(hedges),
                )

            # Persist AnalysisClaim
            claim = AnalysisClaim(
                run_id=run.id,
                claim_name=spotted.claim_name,
                claim_type=spotted.claim_type,
                folio_iri=folio_iri,
                jurisdiction=spotted.jurisdiction,
                confidence=confidence,
                rationale=grounded_rationale,
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
