"""Legal research infrastructure models -- tenant-scoped authorities, results, tool config, and verification.

These models store research results, legal authorities, per-org research tool
configuration, and citation verification records within tenant schemas.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Float, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class AuthorityType(str, Enum):
    """Types of legal authorities."""

    CASE_LAW = "case_law"
    STATUTE = "statute"
    REGULATION = "regulation"
    CONSTITUTIONAL = "constitutional"
    RULE = "rule"
    SECONDARY = "secondary"
    OTHER = "other"


class VerificationStatus(str, Enum):
    """Citation verification statuses."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    NOT_FOUND = "not_found"
    ERROR = "error"


class Authority(TenantBase):
    """A legal authority (case, statute, regulation) found by research tools.

    Stores the canonical representation of a legal authority with FOLIO IRI
    reference, jurisdiction, citation string, and verification status.
    """

    __tablename__ = "authorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id
    citation: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    authority_type: Mapped[str] = mapped_column(String(50), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(256), nullable=True)
    folio_iri: Mapped[str | None] = mapped_column(String(512), nullable=True)  # FOLIO concept IRI
    claim_iri: Mapped[str | None] = mapped_column(String(512), nullable=True)  # FOLIO claim IRI this supports
    source_tool: Mapped[str] = mapped_column(String(100), nullable=False)  # Which research tool found this
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified", nullable=False)
    verification_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ResearchResult(TenantBase):
    """Links an intake+claim research query to its results.

    Records each research query executed, which tool was used,
    the query parameters, and how many authorities were found.
    """

    __tablename__ = "research_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id
    claim_iri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(256), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    authority_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ResearchToolConfig(TenantBase):
    """Per-organization configuration of available research tools.

    Each org configures which research tools they have access to,
    with encrypted API keys and enabled/disabled state.
    """

    __tablename__ = "research_tool_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "courtlistener", "westlaw"
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Tool-specific settings
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class CitationVerification(TenantBase):
    """Records each citation verification attempt.

    Tracks which source was used to verify, the result, and any
    metadata from the verification service.
    """

    __tablename__ = "citation_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    authority_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to authorities.id
    verification_source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # verified/unverified/not_found/error
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(server_default=func.now())
