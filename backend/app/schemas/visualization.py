"""Pydantic response schemas for the visualization API endpoint.

Defines the complete visualization payload structure: facts with source spans,
claims with elements, mappings, gaps, and messages. Used by the
GET /api/v1/analysis/{intake_id}/visualization endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel


class VisualizationSourceSpan(BaseModel):
    """A character/time/page range linking a fact back to its source message."""

    message_id: int
    start_char: int
    end_char: int
    page_number: int | None = None
    paragraph_index: int | None = None
    timestamp_start_sec: float | None = None
    timestamp_end_sec: float | None = None


class VisualizationFact(BaseModel):
    """An extracted fact with its source provenance spans."""

    id: int
    assertion_text: str
    fact_type: str
    confidence: float
    source_spans: list[VisualizationSourceSpan] = []


class VisualizationElement(BaseModel):
    """A required element of a legal claim."""

    id: int
    element_name: str
    element_description: str | None = None
    is_satisfied: bool
    satisfaction_confidence: float | None = None


class VisualizationClaim(BaseModel):
    """A legal claim with its constituent elements."""

    id: int
    claim_name: str
    claim_type: str
    jurisdiction: str | None = None
    confidence: float
    rationale: str | None = None
    elements: list[VisualizationElement] = []


class VisualizationMapping(BaseModel):
    """A fact-to-claim-element mapping with confidence score."""

    id: int
    fact_id: int
    claim_id: int
    element_id: int | None = None
    confidence: float
    mapping_rationale: str | None = None


class VisualizationGap(BaseModel):
    """An identified gap in the analysis."""

    id: int
    gap_type: str
    claim_id: int | None = None
    element_id: int | None = None
    description: str
    priority: int
    status: str


class VisualizationMessage(BaseModel):
    """A source message with decoded content for source span rendering."""

    id: int
    content: str
    sender_type: str


class VisualizationResponse(BaseModel):
    """Complete visualization payload for a single analysis run."""

    run_id: int
    status: str
    facts: list[VisualizationFact] = []
    claims: list[VisualizationClaim] = []
    mappings: list[VisualizationMapping] = []
    gaps: list[VisualizationGap] = []
    messages: list[VisualizationMessage] = []
