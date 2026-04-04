"""Research API request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- Request schemas ---


class ResearchQueryRequest(BaseModel):
    """Request to query configured research tools for a claim."""

    claim_iri: str | None = None
    jurisdiction: str | None = None
    query_text: str = Field(..., min_length=3, max_length=2000)
    authority_types: list[str] | None = None  # Filter by authority type
    max_results: int = Field(default=20, ge=1, le=100)


class VerifyCitationRequest(BaseModel):
    """Request to verify a citation against configured tools."""

    citation: str = Field(..., min_length=3, max_length=512)
    title: str | None = None
    authority_type: str | None = None


class ConfigureToolRequest(BaseModel):
    """Request to configure a research tool for the org."""

    tool_name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=255)
    api_key: str | None = None
    base_url: str | None = None
    enabled: bool = True
    config: dict | None = None


# --- Response schemas ---


class AuthorityResponse(BaseModel):
    """A legal authority found by research."""

    id: int | None = None
    citation: str
    title: str
    authority_type: str
    jurisdiction: str | None = None
    folio_iri: str | None = None
    claim_iri: str | None = None
    source_tool: str
    source_url: str | None = None
    excerpt: str | None = None
    relevance_score: float | None = None
    verified: bool = False
    verification_status: str = "unverified"
    verification_source: str | None = None

    model_config = {"from_attributes": True}


class ResearchQueryResponse(BaseModel):
    """Response from research tool query."""

    query_text: str
    tool_names: list[str]
    authorities: list[AuthorityResponse]
    total_results: int


class VerificationResultResponse(BaseModel):
    """Response from citation verification."""

    citation: str
    verified: bool
    status: str  # verified/unverified/not_found/error
    verification_source: str | None = None
    confidence: float | None = None
    matched_title: str | None = None
    source_url: str | None = None
    error: str | None = None


class ResearchToolResponse(BaseModel):
    """A configured research tool."""

    id: int
    tool_name: str
    display_name: str
    enabled: bool
    base_url: str | None = None
    has_api_key: bool = False
    config: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
