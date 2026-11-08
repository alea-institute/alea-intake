"""LLM-driven fact extraction service with ConceptResolver integration.

Extracts atomic factual assertions from normalized text via a dedicated LLM call
with Pydantic structured output. Each extracted fact has assertion_text, fact_type,
entity_type, confidence score, and source span (start_char, end_char).

Extracted facts are persisted as ExtractedFact + FactSourceSpan records and
passed to ConceptResolver for FOLIO IRI matching (per CONTEXT.md locked decision).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.fact import ExtractedFact, FactSourceSpan
from app.services.extraction.schemas import ExtractedFactSchema, ExtractionResultSchema
from app.services.folio.concept_resolver import resolve_concepts

if TYPE_CHECKING:
    from folio import FOLIO

    from app.services.embedding.service import EmbeddingService
    from app.services.intake.message_pipeline import NormalizedContent
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# Output bounds (2026-11-08 live run): unbounded prompts produced replies that
# hit the 8192-token JSON ceiling on a ~1,700-token message, so every reply was
# truncated JSON. Cap the facts per call and chunk long messages instead.
MAX_FACTS_PER_CALL = 25
COMPACT_MAX_FACTS = 10
CHUNK_CHARS = 6000
# One retry, with a stricter (non-identical) request; never more.
MAX_EXTRACTION_ATTEMPTS = 2

EXTRACTION_SYSTEM_PROMPT = """You are a legal fact extraction assistant. Given narrative text from a legal intake,
extract atomic factual assertions. Each fact should be the smallest meaningful unit.

Entity types:
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
2. Use confidence 0.0-1.0 based on how clearly the fact is stated.
3. If a fact contradicts a previously extracted fact, still extract it -- note both.
4. Decompose compound statements into atomic facts.
5. Be concise. Return at most {max_facts} facts, the most legally important first.
   Each assertion is one short sentence (at most 25 words). Do not repeat the
   narrative, do not restate a fact, and add no commentary.
6. "source_quote" is a short excerpt (at most 15 words) copied character for
   character from the text that states the fact.
7. Every item in "entities" MUST be an object with "entity_type" and "value",
   never a bare string. List only entities named in that fact.

Return ONLY a JSON object, with no prose and no markdown fences, in EXACTLY this structure:
{{
  "facts": [
    {{
      "assertion": "one short sentence stating the fact",
      "fact_type": "event | relationship | amount | date | condition | sequence",
      "entities": [
        {{"entity_type": "one of the entity types above", "value": "verbatim entity text"}}
      ],
      "confidence": 0.9,
      "source_quote": "verbatim excerpt from the text"
    }}
  ]
}}
Every fact MUST include "assertion", "fact_type", "entities", "confidence", and "source_quote"."""

COMPACT_RETRY_INSTRUCTION = (
    "Your previous reply was cut off or was not valid JSON. Reply again with a "
    f"complete JSON object containing at most {COMPACT_MAX_FACTS} facts, each "
    "assertion under 15 words and each source_quote under 10 words."
)


def _system_prompt(max_facts: int) -> str:
    return EXTRACTION_SYSTEM_PROMPT.format(max_facts=max_facts)


def _chunk_text(text: str, limit: int = CHUNK_CHARS) -> list[tuple[int, str]]:
    """Split text into (offset, chunk) pieces at paragraph or sentence breaks."""
    if len(text) <= limit:
        return [(0, text)]
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
            if cut > limit // 2:
                end = start + cut + 1
        chunks.append((start, text[start:end]))
        start = end
    return chunks


def _resolve_span(fact: ExtractedFactSchema, text: str) -> tuple[int, int]:
    """Locate a fact's source span; fall back to the whole message.

    Models cannot count characters reliably, so a verbatim quote wins over
    model-supplied offsets. A fact whose source cannot be located keeps
    message-level provenance instead of being discarded.
    """
    quote = (fact.source_quote or "").strip()
    if quote:
        index = text.find(quote)
        if index < 0:
            lowered = text.lower()
            if len(lowered) == len(text):
                index = lowered.find(quote.lower())
        if index >= 0:
            return index, index + len(quote)
    start, end = fact.source_start, fact.source_end
    if start is not None and end is not None and 0 <= start < end <= len(text):
        return start, end
    return 0, len(text)


def _first_error(exc: ValidationError) -> str:
    """Describe a validation failure by type and field path, never by content."""
    errors = exc.errors(include_input=False, include_url=False)
    if not errors:
        return "unknown"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "<root>"
    return f"{first.get('type', 'unknown')} at {loc}"


def parse_extraction(raw: Any) -> ExtractionResultSchema | None:
    """Validate an extraction reply fact by fact.

    Returns None when the reply has no usable shape (not an object with a
    "facts" list). A single malformed fact is dropped and counted; it never
    discards the rest of the extraction. Logs only counts, error types, and
    field paths -- extraction input and output are visitor data.
    """
    if isinstance(raw, list):
        raw = {"facts": raw}
    if not isinstance(raw, dict) or not isinstance(raw.get("facts"), list):
        logger.warning(
            "LLM extraction reply has no facts list (got %s)", type(raw).__name__
        )
        return None
    facts: list[ExtractedFactSchema] = []
    dropped = 0
    first_error = None
    for item in raw["facts"]:
        try:
            facts.append(ExtractedFactSchema.model_validate(item))
        except ValidationError as exc:
            dropped += 1
            first_error = first_error or _first_error(exc)
    entities = []
    raw_entities = raw.get("entities")
    if isinstance(raw_entities, list):
        try:
            entities = ExtractionResultSchema.model_validate(
                {"entities": raw_entities}
            ).entities
        except ValidationError as exc:
            first_error = first_error or _first_error(exc)
    if dropped:
        logger.warning(
            "Dropped %d of %d extracted facts failing validation (first: %s)",
            dropped, len(raw["facts"]), first_error,
        )
    return ExtractionResultSchema(facts=facts, entities=entities)


def _limit_client_retries(client: Any) -> None:
    """Stop alea-llm-client re-sending an identical request on a bad reply.

    Its retry wrapper resends the same request up to three times when the JSON
    reply fails to parse, which multiplied truncated 8192-token replies. The
    service owns the single retry instead.
    """
    target = getattr(client, "_model", client)
    if hasattr(target, "retry_limit"):
        try:
            target.retry_limit = 1
        except (AttributeError, TypeError):  # pragma: no cover - exotic clients
            pass


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
        self,
        text: str,
        session_facts: list[dict] | None = None,
        compact: bool = False,
    ) -> dict[str, Any]:
        """Call LLM to extract facts from text. Returns raw JSON dict.

        This method is separated for easy mocking in tests. ``compact`` asks
        for a shorter reply after a truncated or invalid one.
        """
        max_facts = COMPACT_MAX_FACTS if compact else MAX_FACTS_PER_CALL
        messages = [
            {"role": "system", "content": _system_prompt(max_facts)},
        ]

        # Include session context for contradiction detection
        if session_facts:
            context = "Previously extracted facts for context:\n"
            for f in session_facts[:20]:  # Limit context size
                context += f"- {f.get('assertion_text', '')}\n"
            messages.append({"role": "system", "content": context})

        if compact:
            messages.append({"role": "system", "content": COMPACT_RETRY_INSTRUCTION})

        messages.append({"role": "user", "content": text})

        model = self._llm.create_client()
        _limit_client_retries(model)
        response = await model.json_async(messages=messages)
        return response.data

    async def _extract_chunk(
        self, text: str, session_facts: list[dict] | None
    ) -> ExtractionResultSchema:
        """Extract one chunk, retrying at most once with a compact request."""
        for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
            try:
                raw = await self._call_llm_extraction(
                    text, session_facts, compact=attempt > 1
                )
            except Exception as exc:
                # Truncated JSON surfaces here as a parse failure. Log the type
                # only: the exception chain can carry the visitor's reply.
                logger.warning(
                    "LLM extraction attempt %d/%d failed (%s)",
                    attempt, MAX_EXTRACTION_ATTEMPTS, type(exc).__name__,
                )
                continue
            result = parse_extraction(raw)
            if result is not None:
                return result
        logger.warning("Failed to parse LLM extraction output after %d attempts",
                       MAX_EXTRACTION_ATTEMPTS)
        return ExtractionResultSchema(facts=[], entities=[])

    async def extract_facts(
        self,
        text: str,
        session_facts: list[dict] | None = None,
    ) -> ExtractionResultSchema:
        """Extract atomic facts from text via LLM structured output.

        Long text is chunked so no single reply has to describe all of it.
        Every returned fact carries resolved, in-bounds source offsets.

        Args:
            text: Normalized text to extract facts from.
            session_facts: Previously extracted facts for contradiction context.

        Returns:
            Validated ExtractionResultSchema with facts and entities.
        """
        if not text or not text.strip():
            return ExtractionResultSchema(facts=[], entities=[])

        facts: list[ExtractedFactSchema] = []
        entities = []
        for offset, chunk in _chunk_text(text):
            result = await self._extract_chunk(chunk, session_facts)
            for fact in result.facts:
                start, end = _resolve_span(fact, chunk)
                fact.source_start, fact.source_end = offset + start, offset + end
                facts.append(fact)
            entities.extend(result.entities)

        return ExtractionResultSchema(facts=facts, entities=entities)

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
                except Exception as exc:
                    logger.warning(
                        "Concept resolution failed for intake %d message %d (%s)",
                        intake_id, message_id, type(exc).__name__,
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
                entity_type=next(
                    (e.entity_type for e in fact_schema.entities if e.entity_type),
                    None,
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
        # Untyped entities (coerced from bare strings) never drive supersession.
        new_entity_types = {e.entity_type for e in new_schema.entities if e.entity_type}

        for existing in session_facts:
            if existing.get("party_id") != party_id:
                continue
            if existing.get("fact_type") != new_fact.fact_type:
                continue

            # Check for overlapping entity types
            existing_entities = existing.get("metadata_json", {}).get("entities", [])
            existing_entity_types = {
                e.get("entity_type")
                for e in existing_entities
                if isinstance(e, dict) and e.get("entity_type")
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
