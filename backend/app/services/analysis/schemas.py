"""Pydantic schemas for analysis pipeline LLM I/O and stage contracts.

Defines structured output schemas for each analysis stage (issue-spotting,
fact-mapping, gap analysis, question generation), the LLM orchestrator
decision, convergence evaluation, and org-configurable analysis settings.
All schemas use Pydantic v2 BaseModel for validation and JSON serialization.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class OrchestratorDecision(BaseModel):
    """LLM orchestrator output -- decides which stage to run next (D-01)."""

    next_stage: Literal["issue_spot", "explore", "research", "fact_map", "gap_analyze", "question", "converge"]
    reasoning: str
    skip_stages: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Issue-Spotting Stage
# ---------------------------------------------------------------------------


class ClaimElementSchema(BaseModel):
    """A required element of a legal claim."""

    element_name: str
    element_description: str | None = None
    jurisdiction: str | None = None


class SpottedClaim(BaseModel):
    """A claim identified or discovered during issue-spotting."""

    claim_name: str
    claim_type: Literal["identified", "discovered"]
    folio_iri: str | None = None
    jurisdiction: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    is_potential: bool = False
    elements: list[ClaimElementSchema] = Field(default_factory=list)


class IssueSpotResult(BaseModel):
    """Complete output from the issue_spot stage."""

    claims: list[SpottedClaim]
    jurisdictions: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Fact-Mapping Stage
# ---------------------------------------------------------------------------


class FactMappingSchema(BaseModel):
    """A single fact-to-claim mapping produced by the fact_map stage."""

    fact_id: int
    claim_name: str
    element_name: str | None = None
    llm_confidence: float = Field(ge=0.0, le=1.0)
    mapping_rationale: str


class FactMapResult(BaseModel):
    """Complete output from the fact_map stage."""

    mappings: list[FactMappingSchema]
    unmapped_facts: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gap Analysis Stage
# ---------------------------------------------------------------------------


class GapSchema(BaseModel):
    """A single gap identified in the analysis."""

    gap_type: Literal["unsupported_element", "unexplored_claim", "weak_mapping", "procedural_requirement"]
    claim_name: str | None = None
    element_name: str | None = None
    description: str
    priority: int


class GapAnalysisResult(BaseModel):
    """Complete output from the gap_analyze stage."""

    gaps: list[GapSchema]
    coverage_pct: float = Field(ge=0.0, le=1.0)
    summary: str


# ---------------------------------------------------------------------------
# Question Generation Stage
# ---------------------------------------------------------------------------


class QuestionSchema(BaseModel):
    """A single follow-up question for the consumer."""

    question_text: str
    rationale: str | None = None
    priority: int
    gap_description: str | None = None


class QuestionGroup(BaseModel):
    """Topic-grouped follow-up questions (D-10)."""

    topic: str
    questions: list[QuestionSchema]


class QuestionGenResult(BaseModel):
    """Complete output from the question generation stage."""

    groups: list[QuestionGroup]
    total_questions: int


# ---------------------------------------------------------------------------
# Convergence Evaluation
# ---------------------------------------------------------------------------


class ConvergenceSignals(BaseModel):
    """Input signals for convergence evaluation (D-13)."""

    coverage_pct: float = Field(ge=0.0, le=1.0)
    confidence_delta: float
    iteration_number: int
    max_iterations: int
    skip_rate: float = Field(ge=0.0, le=1.0)
    avg_response_time_sec: float
    new_gaps_count: int
    previous_gaps_count: int


class ConvergenceWeights(BaseModel):
    """Org-configurable weights for convergence signals (D-13).

    Default weights sum to 1.0.
    """

    coverage: float = 0.30
    confidence_plateau: float = 0.20
    iteration_cap: float = 0.10
    user_fatigue: float = 0.15
    diminishing_gaps: float = 0.25


# ---------------------------------------------------------------------------
# Confidence Scoring
# ---------------------------------------------------------------------------


class ConfidenceWeights(BaseModel):
    """Org-configurable weights for composite confidence scoring (D-05).

    Default weights sum to 1.0.
    """

    llm_weight: float = 0.4
    concept_weight: float = 0.3
    fact_weight: float = 0.3


# ---------------------------------------------------------------------------
# Org Analysis Configuration
# ---------------------------------------------------------------------------


class AnalysisConfig(BaseModel):
    """Complete org-level analysis configuration (D-04, D-12, D-13, D-14).

    Stored as JSON in OrganizationConfig.analysis_config_json.
    Supports round-trip JSON serialization for DB persistence.
    Includes exploration config for pre-research exploration depth and transparency.
    """

    auto_trigger_enabled: bool = True
    auto_trigger_fact_threshold: int = 5
    max_iterations: int = 10
    convergence_threshold: float = 0.75
    convergence_weights: ConvergenceWeights = Field(default_factory=ConvergenceWeights)
    confidence_weights: ConfidenceWeights = Field(default_factory=ConfidenceWeights)
    question_transparency: bool = True

    # Phase 5: Pre-research exploration configuration
    exploration: "ExplorationConfig" = Field(default_factory=lambda: ExplorationConfig())


# Avoid circular import -- ExplorationConfig imported at end
from app.services.exploration.schemas import ExplorationConfig  # noqa: E402

# Update forward reference
AnalysisConfig.model_rebuild()
