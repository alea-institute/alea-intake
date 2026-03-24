"""FOLIO concept data models -- tenant-scoped concept mappings, graph, and unmapped records.

These models store per-intake FOLIO concept resolution results within tenant schemas.
The intake_id column is a plain Integer; FK to intakes.id will be added in Phase 3
when the Intake model is created.
"""

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class ConceptMapping(TenantBase):
    """Maps an intake fact to a FOLIO concept IRI with confidence score."""

    __tablename__ = "concept_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id -- added in Phase 3
    iri: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "embedding"/"label_match"/"llm"/"combined"
    is_unmapped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ConceptGraphNode(TenantBase):
    """A node in the per-intake concept graph (FOLIO concept or unmapped concept)."""

    __tablename__ = "concept_graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id -- added in Phase 3
    iri: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_unmapped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ConceptGraphEdge(TenantBase):
    """An edge in the per-intake concept graph connecting two concept IRIs."""

    __tablename__ = "concept_graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id -- added in Phase 3
    source_iri: Mapped[str] = mapped_column(String(512), nullable=False)
    target_iri: Mapped[str] = mapped_column(String(512), nullable=False)
    relationship: Mapped[str] = mapped_column(String(256), nullable=False)
    traversal_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UnmappedConceptRecord(TenantBase):
    """Records concepts that could not be mapped to FOLIO, with suggestions."""

    __tablename__ = "unmapped_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to intakes.id -- added in Phase 3
    local_iri: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unmapped_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    nearest_iris: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list of {iri, label, confidence}
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
