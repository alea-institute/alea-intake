"""Pydantic schemas for autonomy API request/response bodies.

Defines action schemas for approval decisions, request serialization,
mode switching, and audit event representation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.services.analysis.autonomy.config import AutonomyConfig


class ApprovalAction(BaseModel):
    """Action taken on an approval request."""

    decision: Literal[
        "approve", "reject", "edit", "auto_proceed", "queue", "pause"
    ]
    guidance_text: str | None = None
    edits: dict | None = None
    actor_id: int | None = None


class ApprovalRequestSchema(BaseModel):
    """Serialized approval request for API responses."""

    id: int
    run_id: int
    iteration_id: int
    stage_name: str
    status: str
    safety_triggered: bool = False
    is_rerun: bool = False
    rerun_attempt: int = 0
    guidance_text: str | None = None
    stage_output_json: dict | None = None
    created_at: datetime | None = None


class RejectBody(BaseModel):
    """Body for rejection action -- guidance is required."""

    guidance_text: str = Field(..., min_length=1)


class EditBody(BaseModel):
    """Body for edit action -- edits dict is required."""

    edits: dict = Field(...)


class ModeSwitchBody(BaseModel):
    """Body for mid-intake mode switch (D-05)."""

    config: AutonomyConfig
    reason: str


class AutonomyEventSchema(BaseModel):
    """Serialized autonomy event for API responses."""

    run_id: int
    intake_id: int
    event_type: str
    actor_id: int | None = None
    stage_name: str | None = None
    details_json: dict | None = None
    created_at: datetime | None = None
