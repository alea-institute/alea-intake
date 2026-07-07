"""LLM-driven fact extraction service with ConceptResolver integration.

Extracts atomic factual assertions from normalized text via a dedicated LLM call
with Pydantic structured output. Each extracted fact has assertion_text, fact_type,
entity_type, confidence score, and source span (start_char, end_char).

Extracted facts are persisted as ExtractedFact + FactSourceSpan records and
passed to ConceptResolver for FOLIO IRI matching (per CONTEXT.md locked decision).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.fact import ExtractedFact, FactSourceSpan
from app.services.extraction.schemas import ExtractionResultSchema
from app.services.folio.concept_resolver import resolve_concepts

if TYPE_CHECKING:
    from folio import FOLIO

    from app.services.embedding.service import EmbeddingService
    from app.services.intake.message_pipeline import NormalizedContent
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """You are a legal fact extraction assistant. Given narrative text from a legal intake,
extract atomic factual assertions. Each fact should be the smallest meaningful unit.

Entity types to extract:
- person: Named individuals
- date: Specific dates or date ranges
- location: Places, addresses, jurisdictions
- amount: Dollar amounts, quantities
- organization: Companies, agencies, courts
- party_relationship: employer/employee, landlord/tenant, spouse/spouse
- legal_event: Filing, service, injury, termination, arrest
- document_reference: Contracts, leases, court orders
- time_period: Statute of limitations, employment duration
- claimed_damages: Specific damages claimed

Rules:
1. Only extract facts explicitly stated in the text. Never infer unstated facts.
2. Each fact must have a source_start and source_end character offset in the original text.
3. Use confidence 0.0-1.0 based on how clearly the fact is stated.
4. If a fact contradicts a previously extracted fact, still extract it -- note both.
5. Decompose compound statements into atomic facts.

Return a JSON object matching the ExtractionResult schema with "facts" and "entities" arrays."""


class FactExtractionService:
    """LLM-driven fact extraction with ConceptResolver wiring.

    Extracts atomic facts from normalized text, resolves FOLIO concepts,
    and persists results with source provenance.
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize with LLM service, DB session, and optional FOLIO services.

        Args:
            llm_service: LLM service for extraction calls.
            db_session: Async database session for persistence.
            folio: FOLIO instance for concept resolution. None = skip resolution.
            embedding_service: Embedding service for concept resolution. None = skip.
        """
        self._llm = llm_service
        self._session = db_session
        self._folio = folio
        self._embedding_service = embedding_service

    async def _call_llm_extraction(
        self, text: str, session_facts: list[dict] | None = None
    ) -> dict[str, Any]:
        """Call LLM to extract facts from text. Returns raw JSON dict.

        This method is separated for easy mocking in tests.
        """
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        ]

        # Include session context for contradiction detection
        if session_facts:
            context = "Previously extracted facts for context:\n"
            for f in session_facts[:20]:  # Limit context size
                context += f"- {f.get('assertion_text', '')}\n"
            messages.append({"role": "system", "content": context})

        messages.append({"role": "user", "content": text})

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
            return {"facts": [], "entities": []}

        init_kwargs: dict[str, Any] = {
            "api_key": config.get("api_key"),
            "model": config.get("model"),
        }
        if "endpoint" in config:
            init_kwargs["endpoint"] = config["endpoint"]

        model = model_cls(**init_kwargs)
        response = await model.json_async(messages=messages)
        return response.data

    async def extract_facts(
        self,
        text: str,
        session_facts: list[dict] | None = None,
    ) -> ExtractionResultSchema:
        """Extract atomic facts from text via LLM structured output.

        Args:
            text: Normalized text to extract facts from.
            session_facts: Previously extracted facts for contradiction context.

        Returns:
            Validated ExtractionResultSchema with facts and entities.
        """
        if not text or not text.strip():
            return ExtractionResultSchema(facts=[], entities=[])

        try:
            raw_result = await self._call_llm_extraction(text, session_facts)
            result = ExtractionResultSchema.model_validate(raw_result)
        except Exception:
            logger.warning("Failed to parse LLM extraction output", exc_info=True)
            return ExtractionResultSchema(facts=[], entities=[])

        # Validate source spans: drop facts with out-of-bounds offsets
        text_len = len(text)
        valid_facts = [
            f
            for f in result.facts
            if f.source_start >= 0
            and f.source_end <= text_len
            and f.source_start < f.source_end
        ]
        result.facts = valid_facts

        return result

    async def extract_and_persist(
        self,
        normalized: NormalizedContent,
        intake_id: int,
        message_id: int,
        party_id: int | None = None,
        session_facts: list[dict] | None = None,
        **kwargs,
    ) -> list[ExtractedFact]:
        """Extract facts, resolve FOLIO concepts, and persist to DB.

        Args:
            normalized: Normalized content to extract from.
            intake_id: ID of the intake.
            message_id: ID of the source message.
            party_id: ID of the party (for attribution).
            session_facts: Previously extracted facts for supersession detection.
            **kwargs: Additional metadata (timestamp fields, page numbers).

        Returns:
            List of created ExtractedFact records.
        """
        settings = get_settings()
        result = await self.extract_facts(normalized.text, session_facts)

        created_facts: list[ExtractedFact] = []

        for fact_schema in result.facts:
            # Resolve FOLIO concepts if services are available
            resolved_iris: list[dict[str, Any]] = []
            if self._folio is not None and self._embedding_service is not None:
                try:
                    resolved = await resolve_concepts(
                        fact_schema.assertion,
                        self._folio,
                        self._embedding_service,
                    )
                    resolved_iris = [
                        {
                            "iri": rc.iri,
                            "label": rc.label,
                            "confidence": rc.confidence,
                        }
                        for rc in resolved
                    ]
                except Exception:
                    logger.warning(
                        "Concept resolution failed for fact: %s",
                        fact_schema.assertion,
                        exc_info=True,
                    )

            # Build metadata
            metadata = {
                "entities": [e.model_dump() for e in fact_schema.entities],
                "resolved_concepts": resolved_iris,
            }

            # Create ExtractedFact record
            db_fact = ExtractedFact(
                intake_id=intake_id,
                message_id=message_id,
                party_id=party_id,
                assertion_text=fact_schema.assertion,
                fact_type=fact_schema.fact_type,
                entity_type=(
                    fact_schema.entities[0].entity_type
                    if fact_schema.entities
                    else None
                ),
                confidence=fact_schema.confidence,
                is_active=True,
                visibility=settings.intake_fact_visibility,
                metadata_json=metadata,
            )
            self._session.add(db_fact)
            await self._session.flush()

            # Create FactSourceSpan record
            span = FactSourceSpan(
                fact_id=db_fact.id,
                message_id=message_id,
                start_char=fact_schema.source_start,
                end_char=fact_schema.source_end,
                timestamp_start_sec=kwargs.get("timestamp_start_sec"),
                timestamp_end_sec=kwargs.get("timestamp_end_sec"),
                page_number=kwargs.get("page_number"),
            )
            self._session.add(span)

            # Handle same-party supersession
            if session_facts and party_id is not None:
                await self._handle_supersession(
                    db_fact, fact_schema, session_facts, party_id
                )

            created_facts.append(db_fact)

        await self._session.flush()
        return created_facts

    async def _handle_supersession(
        self,
        new_fact: ExtractedFact,
        new_schema,
        session_facts: list[dict],
        party_id: int,
    ) -> None:
        """Handle same-party fact supersession.

        If an existing active fact from the same party has overlapping
        entity types and values, mark it as superseded.
        """
        new_entity_types = {e.entity_type for e in new_schema.entities}

        for existing in session_facts:
            if existing.get("party_id") != party_id:
                continue
            if existing.get("fact_type") != new_fact.fact_type:
                continue

            # Check for overlapping entity types
            existing_entities = existing.get("metadata_json", {}).get("entities", [])
            existing_entity_types = {
                e.get("entity_type") for e in existing_entities if isinstance(e, dict)
            }

            if new_entity_types & existing_entity_types:
                # Supersede the old fact
                existing_id = existing.get("id")
                if existing_id:
                    result = await self._session.execute(
                        select(ExtractedFact).where(
                            ExtractedFact.id == existing_id,
                            ExtractedFact.is_active == True,  # noqa: E712
                        )
                    )
                    old_fact = result.scalar_one_or_none()
                    if old_fact:
                        old_fact.is_active = False
                        old_fact.superseded_by_id = new_fact.id
                        await self._session.flush()

    async def get_session_facts(self, intake_id: int) -> list[dict]:
        """Get all active facts for an intake session.

        Returns:
            List of fact dicts with assertion_text, fact_type, entity_type,
            confidence, party_id, metadata_json (includes resolved_concepts).
        """
        result = await self._session.execute(
            select(ExtractedFact)
            .where(ExtractedFact.intake_id == intake_id)
            .where(ExtractedFact.is_active == True)  # noqa: E712
            .order_by(ExtractedFact.created_at)
        )
        facts = result.scalars().all()
        return [
            {
                "id": f.id,
                "assertion_text": f.assertion_text,
                "fact_type": f.fact_type,
                "entity_type": f.entity_type,
                "confidence": f.confidence,
                "party_id": f.party_id,
                "metadata_json": f.metadata_json or {},
            }
            for f in facts
        ]
