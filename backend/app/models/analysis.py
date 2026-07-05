"""Analysis pipeline DB models -- iterative analysis state tracking.

All models live in per-tenant schemas via TenantBase. Captures the full
lifecycle of an analysis run: iterations, stages, claims, elements,
fact-claim mappings, gaps, and follow-up questions. Supports checkpoint
persistence for pause/resume and audit trail for every stage.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class AnalysisRun(TenantBase):
    """Top-level analysis run -- one per triggered analysis of an intake."""

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    current_iteration_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    convergence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    convergence_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AnalysisIteration(TenantBase):
    """A single iteration within an analysis run."""

    __tablename__ = "analysis_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    converged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    convergence_signals_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AnalysisStage(TenantBase):
    """A single stage execution within an iteration (issue_spot, research, etc.)."""

    __tablename__ = "analysis_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iteration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AnalysisClaim(TenantBase):
    """A legal claim identified or discovered during analysis."""

    __tablename__ = "analysis_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_name: Mapped[str] = mapped_column(String(255), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    folio_iri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_potential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    iteration_discovered: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ClaimElement(TenantBase):
    """A required element of a legal claim that must be satisfied."""

    __tablename__ = "claim_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(Integer, nullable=False)
    element_name: Mapped[str] = mapped_column(String(255), nullable=False)
    element_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_satisfied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    satisfaction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FactClaimMapping(TenantBase):
    """Many-to-many link between extracted facts and claim elements with composite confidence."""

    __tablename__ = "fact_claim_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_id: Mapped[int] = mapped_column(Integer, nullable=False)
    element_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    concept_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fact_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapping_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AnalysisGap(TenantBase):
    """A gap in the analysis -- missing evidence, unexplored claims, or weak mappings."""

    __tablename__ = "analysis_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(30), nullable=False)
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    iteration_found: Mapped[int] = mapped_column(Integer, nullable=False)
    iteration_resolved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Deadline(TenantBase):
    """A detected time-sensitive event and its (optionally computed) deadline.

    Part of the v1 "detect + hedge" deadline/SOL engine. Every row surfaces a
    time-sensitive event from the intake narrative or documents. Where a
    verified rule in ``app/services/deadline/rules.py`` applies, ``computed`` is
    True and ``computed_date`` holds an estimated date with a ``citation``;
    otherwise the event is "detected + hedged only" (``computed=False``).
    ``hedge`` always carries a "verify the exact date" caveat.
    """

    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_text: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    trigger: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trigger_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    computed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    hedge: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FollowUpQuestion(TenantBase):
    """A follow-up question generated from gap analysis, grouped by topic."""

    __tablename__ = "follow_up_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic_group: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    answer_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iteration_asked: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
