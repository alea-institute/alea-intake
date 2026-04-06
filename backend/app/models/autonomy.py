"""Autonomy DB models -- approval requests and audit events.

ApprovalRequest tracks pending/resolved stage approval gates.
AutonomyEvent provides the full audit trail for autonomy decisions.
Both models are tenant-scoped via TenantBase.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TenantBase


class ApprovalRequest(TenantBase):
    """Tracks approval gates for checkpointed analysis stages."""

    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    iteration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | approved | rejected | edited | auto_proceeded | timed_out
    safety_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rerun: Mapped[bool] = mapped_column(Boolean, default=False)
    rerun_attempt: Mapped[int] = mapped_column(Integer, default=0)
    guidance_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AutonomyEvent(TenantBase):
    """Audit trail for all autonomy-related events (D-10)."""

    __tablename__ = "autonomy_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # checkpoint_reached | approved | rejected | edited | auto_proceed | stage_skip | mode_change
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
