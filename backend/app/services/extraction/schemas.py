"""Pydantic models for structured LLM extraction output.

These schemas define the expected JSON structure from the extraction LLM call.
They are used for both validation of LLM output and type safety in downstream code.
"""

from pydantic import BaseModel, Field


class ExtractedEntitySchema(BaseModel):
    """A single extracted entity from narrative text."""

    entity_type: str  # person, date, location, amount, organization,
    # party_relationship, legal_event, document_reference,
    # time_period, claimed_damages
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_start: int  # char offset in normalized text
    source_end: int


class ExtractedFactSchema(BaseModel):
    """An atomic factual assertion decomposed from narrative."""

    assertion: str  # Natural language statement of the fact
    fact_type: str  # event, relationship, amount, date, condition, sequence
    entities: list[ExtractedEntitySchema] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source_start: int
    source_end: int


class ExtractionResultSchema(BaseModel):
    """Complete extraction from a single message."""

    facts: list[ExtractedFactSchema] = Field(default_factory=list)
    entities: list[ExtractedEntitySchema] = Field(default_factory=list)
