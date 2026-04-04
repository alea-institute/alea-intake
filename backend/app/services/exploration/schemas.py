"""Pydantic schemas for exploration engine I/O and configuration.

Defines the data contracts for the three-layer exploration engine:
- ExplorationConfig: org-configurable exploration depth and transparency
- ExplorationResult: a single discovered issue from any exploration layer
- ExplorationRoundResult: results from one exploration round
- ExplorationStageResult: complete output from the exploration stage
- ScreeningResult: output from per-message safety screening
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExplorationConfig(BaseModel):
    """Org-configurable exploration settings (D-06, D-15).

    Controls exploration depth (min/max rounds), stability detection,
    confidence threshold for accepting discovered issues, and whether
    to explain exploration question rationale to the consumer.
    """

    min_rounds: int = Field(default=1, ge=1, le=10)
    max_rounds: int = Field(default=3, ge=1, le=10)
    cheap_llm_provider: str | None = None
    cheap_llm_model: str | None = None
    stability_threshold: int = Field(default=0)
    exploration_confidence_threshold: float = Field(default=0.4)
    question_transparency: bool = True


class ExplorationResult(BaseModel):
    """A single issue discovered by one of the three exploration layers.

    source_layer indicates which layer found it:
    - folio_adjacency: FOLIO ontology graph traversal
    - protocol_match: curated screening protocol trigger
    - cheap_llm: fast/cheap LLM reasoning scan
    - expensive_llm: deep/expensive LLM reasoning
    """

    description: str
    folio_iri: str | None = None
    source_layer: Literal["folio_adjacency", "protocol_match", "cheap_llm", "expensive_llm"]
    confidence: float = Field(ge=0.0, le=1.0)
    is_new_issue: bool
    protocol_id: int | None = None
    claim_name: str | None = None
    rationale: str | None = None


class ExplorationRoundResult(BaseModel):
    """Results from a single exploration round.

    is_stable=True when no new issues were found (convergence signal).
    """

    round_number: int
    results: list[ExplorationResult]
    new_issues_count: int
    is_stable: bool


class ExplorationStageResult(BaseModel):
    """Complete output from the exploration stage within the analysis pipeline.

    Aggregates all rounds and summarizes discovered claims and triggered protocols.
    """

    rounds: list[ExplorationRoundResult]
    total_new_issues: int
    new_claims: list[dict] = Field(default_factory=list)
    triggered_protocols: list[dict] = Field(default_factory=list)


class ScreeningResult(BaseModel):
    """Output from per-message safety screening (fast trigger matching).

    Used by the screening middleware to determine immediate response:
    - has_critical: immediate interrupt with safety resources
    - has_elevated: queued for next conversation pause
    - has_advisory: folded into next exploration round
    """

    triggered_protocols: list[dict] = Field(default_factory=list)
    has_critical: bool = False
    has_elevated: bool = False
    has_advisory: bool = False
    safety_resources: list[dict] = Field(default_factory=list)
    mandatory_questions: list[dict] = Field(default_factory=list)
    needs_deep_scan: bool = False
