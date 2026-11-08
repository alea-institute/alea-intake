"""Pydantic models for structured LLM extraction output.

These schemas define the expected JSON structure from the extraction LLM call.
They are used for both validation of LLM output and type safety in downstream code.

Live models do not always follow the requested shape exactly (2026-11-08 live
run: per-fact ``entities`` came back as bare strings, and character offsets are
often missing because models cannot count characters reliably). The schemas
therefore accept those variants instead of rejecting a whole extraction.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExtractedEntitySchema(BaseModel):
    """A single extracted entity from narrative text."""

    # person, date, location, amount, organization, party_relationship,
    # legal_event, document_reference, time_period, claimed_damages.
    # None marks an untyped entity coerced from a bare string.
    entity_type: str | None = None
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_start: int | None = None  # char offset in normalized text
    source_end: int | None = None


def _coerce_entities(value: Any) -> Any:
    """Turn bare-string entities into untyped entity objects; drop other junk."""
    if value is None:
        return []
    if not isinstance(value, list):
        return value
    coerced = []
    for item in value:
        if isinstance(item, str):
            if item.strip():
                coerced.append({"value": item})
        elif isinstance(item, (dict, BaseModel)):
            coerced.append(item)
    return coerced


class ExtractedFactSchema(BaseModel):
    """An atomic factual assertion decomposed from narrative."""

    assertion: str  # Natural language statement of the fact
    fact_type: str = "event"  # event, relationship, amount, date, condition, sequence
    entities: list[ExtractedEntitySchema] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    # Short verbatim excerpt; the service derives offsets from it.
    source_quote: str | None = None
    source_start: int | None = None
    source_end: int | None = None

    @field_validator("entities", mode="before")
    @classmethod
    def _entities_tolerate_strings(cls, value: Any) -> Any:
        return _coerce_entities(value)


class ExtractionResultSchema(BaseModel):
    """Complete extraction from a single message."""

    facts: list[ExtractedFactSchema] = Field(default_factory=list)
    entities: list[ExtractedEntitySchema] = Field(default_factory=list)

    @field_validator("entities", mode="before")
    @classmethod
    def _entities_tolerate_strings(cls, value: Any) -> Any:
        return _coerce_entities(value)
