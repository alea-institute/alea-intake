"""Autonomy configuration schema with three presets and per-stage toggles.

Defines the autonomy spectrum: chatbot (fully autonomous), professional
(human-at-every-step), and agent (AI with selective checkpoints).

Implements D-01, D-03, D-04, D-11, D-12 from phase 10 research.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StageCheckpoint(str, Enum):
    """Whether a stage runs automatically or pauses for approval."""

    AUTO = "auto"
    CHECKPOINT = "checkpoint"


class TimeoutBehavior(str, Enum):
    """What happens when an approval request times out (D-04)."""

    AUTO_PROCEED = "auto_proceed"
    QUEUE_NEXT = "queue_next"
    PAUSE_UNTIL = "pause_until"


class SafetyBehavior(str, Enum):
    """How safety alerts affect the autonomy flow (D-12)."""

    STRICT = "strict"
    PROFESSIONAL = "professional"


# The 6 analysis pipeline stages (matches AnalysisOrchestrator.STAGES)
ANALYSIS_STAGES = [
    "issue_spot",
    "explore",
    "research",
    "fact_map",
    "gap_analyze",
    "question_gen",
]


class AutonomyConfig(BaseModel):
    """Per-org autonomy configuration with stage-level checkpoint control.

    Stored as JSON in OrganizationConfig.autonomy_config_json.
    Three presets cover the full autonomy spectrum:
    - chatbot: all AUTO (consumer self-service)
    - professional: all CHECKPOINT (lawyer reviews every stage)
    - agent: selective checkpoints (AI decides, human verifies key outputs)
    """

    stage_checkpoints: dict[str, StageCheckpoint] = Field(
        default_factory=lambda: {
            stage: StageCheckpoint.AUTO
            for stage in ANALYSIS_STAGES[:-1]  # All AUTO except question_gen
        }
        | {"question_gen": StageCheckpoint.CHECKPOINT}
    )
    timeout_seconds: int = Field(default=1800, ge=60)
    timeout_behavior: TimeoutBehavior = TimeoutBehavior.AUTO_PROCEED
    safety_behavior: SafetyBehavior = SafetyBehavior.STRICT
    notify_websocket: bool = True
    notify_email: bool = False
    labels: dict[str, str] = Field(
        default_factory=lambda: {
            "assistant_name": "AI Assistant",
            "review_message": "Legal professional is reviewing",
            "paused_message": "Analysis paused for review",
        }
    )

    def get_stage_checkpoint(self, stage_name: str) -> StageCheckpoint:
        """Return checkpoint setting for a stage; AUTO for unknown stages."""
        return self.stage_checkpoints.get(stage_name, StageCheckpoint.AUTO)

    @classmethod
    def chatbot_preset(cls) -> AutonomyConfig:
        """AUTONOMY-01: Fully autonomous -- all stages AUTO."""
        return cls(
            stage_checkpoints={stage: StageCheckpoint.AUTO for stage in ANALYSIS_STAGES},
        )

    @classmethod
    def professional_preset(cls) -> AutonomyConfig:
        """AUTONOMY-02: Human-at-every-step -- all stages CHECKPOINT."""
        return cls(
            stage_checkpoints={
                stage: StageCheckpoint.CHECKPOINT for stage in ANALYSIS_STAGES
            },
            timeout_behavior=TimeoutBehavior.PAUSE_UNTIL,
        )

    @classmethod
    def agent_preset(cls) -> AutonomyConfig:
        """AUTONOMY-03: Selective checkpoints -- only question_gen pauses."""
        return cls()  # Default already has question_gen as CHECKPOINT
