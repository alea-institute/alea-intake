"""Tests for autonomy config schema, DB models, and notification service.

Covers AutonomyConfig presets (chatbot/professional/agent), validation,
JSON serialization, DB model columns, and NotificationService dispatch.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.analysis.autonomy.config import (
    AutonomyConfig,
    SafetyBehavior,
    StageCheckpoint,
    TimeoutBehavior,
)


# --- AutonomyConfig preset tests ---


ALL_STAGES = [
    "issue_spot",
    "explore",
    "research",
    "fact_map",
    "gap_analyze",
    "question_gen",
]


class TestAutonomyConfigPresets:
    """Preset factory methods produce correct stage checkpoint maps."""

    def test_chatbot_preset_all_auto(self) -> None:
        """AUTONOMY-01: chatbot preset sets all 6 stages to AUTO."""
        config = AutonomyConfig.chatbot_preset()
        for stage in ALL_STAGES:
            assert config.get_stage_checkpoint(stage) == StageCheckpoint.AUTO

    def test_professional_preset_all_checkpoint(self) -> None:
        """AUTONOMY-02: professional preset sets all 6 stages to CHECKPOINT."""
        config = AutonomyConfig.professional_preset()
        for stage in ALL_STAGES:
            assert config.get_stage_checkpoint(stage) == StageCheckpoint.CHECKPOINT

    def test_agent_preset_selective(self) -> None:
        """AUTONOMY-03: agent preset defaults question_gen to CHECKPOINT, rest AUTO."""
        config = AutonomyConfig.agent_preset()
        for stage in ALL_STAGES:
            if stage == "question_gen":
                assert config.get_stage_checkpoint(stage) == StageCheckpoint.CHECKPOINT
            else:
                assert config.get_stage_checkpoint(stage) == StageCheckpoint.AUTO

    def test_unknown_stage_returns_auto(self) -> None:
        """Safe fallback: unknown stage names return AUTO."""
        config = AutonomyConfig()
        assert config.get_stage_checkpoint("nonexistent_stage") == StageCheckpoint.AUTO

    def test_timeout_seconds_minimum_60(self) -> None:
        """timeout_seconds must be >= 60."""
        with pytest.raises(ValueError):
            AutonomyConfig(timeout_seconds=30)

    def test_json_round_trip(self) -> None:
        """AutonomyConfig round-trips through JSON serialization."""
        original = AutonomyConfig.professional_preset()
        dumped = original.model_dump(mode="json")
        restored = AutonomyConfig.model_validate(dumped)
        assert restored == original

    def test_json_round_trip_agent(self) -> None:
        """Agent preset also round-trips correctly."""
        original = AutonomyConfig.agent_preset()
        dumped = original.model_dump(mode="json")
        restored = AutonomyConfig.model_validate(dumped)
        assert restored == original

    def test_default_labels(self) -> None:
        """Default labels per D-11 are present."""
        config = AutonomyConfig()
        assert "assistant_name" in config.labels
        assert "review_message" in config.labels
        assert "paused_message" in config.labels


# --- DB model column tests ---


class TestApprovalRequestModel:
    """ApprovalRequest model has all required columns."""

    def test_required_columns(self) -> None:
        from app.models.autonomy import ApprovalRequest

        required = [
            "run_id",
            "stage_name",
            "status",
            "safety_triggered",
            "is_rerun",
            "rerun_attempt",
            "guidance_text",
            "stage_output_json",
            "edited_output_json",
            "actor_id",
            "timeout_seconds",
            "created_at",
            "resolved_at",
        ]
        columns = {c.name for c in ApprovalRequest.__table__.columns}
        for col in required:
            assert col in columns, f"Missing column: {col}"


class TestAutonomyEventModel:
    """AutonomyEvent model has all required columns."""

    def test_required_columns(self) -> None:
        from app.models.autonomy import AutonomyEvent

        required = [
            "run_id",
            "intake_id",
            "event_type",
            "actor_id",
            "stage_name",
            "details_json",
            "created_at",
        ]
        columns = {c.name for c in AutonomyEvent.__table__.columns}
        for col in required:
            assert col in columns, f"Missing column: {col}"


# --- NotificationService tests ---


class TestNotificationService:
    """NotificationService dispatches approval_pending via WebSocket."""

    @pytest.mark.asyncio
    async def test_notify_sends_approval_pending(self) -> None:
        from app.services.analysis.autonomy.notification import NotificationService

        ws_manager = AsyncMock()
        service = NotificationService(ws_manager=ws_manager)

        # Create a mock approval request with required fields
        mock_request = MagicMock()
        mock_request.id = 1
        mock_request.run_id = 10
        mock_request.stage_name = "issue_spot"
        mock_request.safety_triggered = False

        await service.notify(request=mock_request, session_id=42)

        ws_manager.send_to_session.assert_awaited_once()
        call_args = ws_manager.send_to_session.call_args
        assert call_args[0][0] == 42  # session_id
        message = call_args[0][1]
        assert message["type"] == "approval_pending"
        assert message["request_id"] == 1
        assert message["run_id"] == 10
        assert message["stage_name"] == "issue_spot"
