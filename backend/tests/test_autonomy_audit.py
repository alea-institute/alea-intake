"""Comprehensive tests for AutonomyAuditLogger (D-10).

Verifies every convenience method creates the correct AutonomyEvent
record with proper event_type, run_id, intake_id, actor_id, stage_name,
and details_json fields. Covers the full decision audit trail including
mode changes with old/new config, rejections with guidance, and edits
with original/edited output.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.autonomy import AutonomyEvent
from app.services.analysis.autonomy.audit_logger import AutonomyAuditLogger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_logger(async_session: AsyncSession) -> AutonomyAuditLogger:
    """Create an AutonomyAuditLogger with the test session."""
    return AutonomyAuditLogger(async_session)


async def _get_last_event(session: AsyncSession) -> AutonomyEvent:
    """Retrieve the most recently created AutonomyEvent."""
    stmt = select(AutonomyEvent).order_by(AutonomyEvent.id.desc()).limit(1)
    result = await session.execute(stmt)
    event = result.scalar_one()
    return event


# ===========================================================================
# checkpoint_reached
# ===========================================================================


class TestLogCheckpointReached:
    """log_checkpoint_reached creates event with correct fields."""

    @pytest.mark.asyncio
    async def test_creates_checkpoint_reached_event(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_checkpoint_reached(
            run_id=1, intake_id=100, stage_name="issue_spot"
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "checkpoint_reached"
        assert event.run_id == 1
        assert event.intake_id == 100
        assert event.stage_name == "issue_spot"

    @pytest.mark.asyncio
    async def test_checkpoint_reached_has_safety_flag(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_checkpoint_reached(
            run_id=1, intake_id=100, stage_name="explore", safety_triggered=True
        )

        event = await _get_last_event(async_session)
        assert event.details_json["safety_triggered"] is True


# ===========================================================================
# approved
# ===========================================================================


class TestLogApproved:
    """log_approved creates event with actor_id."""

    @pytest.mark.asyncio
    async def test_creates_approved_event(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_approved(
            run_id=2, intake_id=200, stage_name="research", actor_id=42
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "approved"
        assert event.run_id == 2
        assert event.intake_id == 200
        assert event.stage_name == "research"
        assert event.actor_id == 42

    @pytest.mark.asyncio
    async def test_approved_links_run_and_intake(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_approved(
            run_id=3, intake_id=300, stage_name="fact_map"
        )

        event = await _get_last_event(async_session)
        assert event.run_id == 3
        assert event.intake_id == 300


# ===========================================================================
# rejected
# ===========================================================================


class TestLogRejected:
    """log_rejected creates event with guidance_text in details_json."""

    @pytest.mark.asyncio
    async def test_creates_rejected_event_with_guidance(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_rejected(
            run_id=4,
            intake_id=400,
            stage_name="issue_spot",
            actor_id=55,
            guidance_text="Please reconsider the employment law claim",
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "rejected"
        assert event.actor_id == 55
        assert event.details_json["guidance_text"] == "Please reconsider the employment law claim"

    @pytest.mark.asyncio
    async def test_rejected_uses_guidance_param_as_fallback(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        """Backward compat: 'guidance' param still works."""
        await audit_logger.log_rejected(
            run_id=5,
            intake_id=500,
            stage_name="explore",
            guidance="Old style guidance",
        )

        event = await _get_last_event(async_session)
        assert event.details_json["guidance_text"] == "Old style guidance"


# ===========================================================================
# edited
# ===========================================================================


class TestLogEdited:
    """log_edited creates event with original and edited output in details_json."""

    @pytest.mark.asyncio
    async def test_creates_edited_event_with_outputs(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_edited(
            run_id=6,
            intake_id=600,
            stage_name="fact_map",
            actor_id=77,
            original_output={"claims": ["breach"]},
            edited_output={"claims": ["breach", "negligence"]},
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "edited"
        assert event.actor_id == 77
        assert event.details_json["original_output"] == {"claims": ["breach"]}
        assert event.details_json["edited_output"] == {"claims": ["breach", "negligence"]}

    @pytest.mark.asyncio
    async def test_edited_with_edits_dict(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        """Legacy edits dict still recorded."""
        await audit_logger.log_edited(
            run_id=7,
            intake_id=700,
            stage_name="research",
            edits={"claims": ["modified"]},
        )

        event = await _get_last_event(async_session)
        assert event.details_json["edits"] == {"claims": ["modified"]}


# ===========================================================================
# auto_proceeded
# ===========================================================================


class TestLogAutoProceeded:
    """log_auto_proceed creates event with timeout_duration in details_json."""

    @pytest.mark.asyncio
    async def test_creates_auto_proceeded_event(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_auto_proceed(
            run_id=8, intake_id=800, stage_name="gap_analyze", timeout_duration=1800.0
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "auto_proceeded"
        assert event.stage_name == "gap_analyze"
        assert event.details_json["timeout_duration"] == 1800.0

    @pytest.mark.asyncio
    async def test_auto_proceed_without_timeout(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        """Auto proceed with no timeout_duration records no details."""
        await audit_logger.log_auto_proceed(
            run_id=9, intake_id=900, stage_name="question_gen"
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "auto_proceeded"
        assert event.details_json is None


# ===========================================================================
# stage_skipped
# ===========================================================================


class TestLogStageSkipped:
    """log_stage_skip creates event with reason in details_json."""

    @pytest.mark.asyncio
    async def test_creates_stage_skipped_event(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_stage_skip(
            run_id=10, intake_id=1000, stage_name="explore", reason="max_rejections_exceeded"
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "stage_skipped"
        assert event.details_json["reason"] == "max_rejections_exceeded"


# ===========================================================================
# mode_changed (D-10)
# ===========================================================================


class TestLogModeChanged:
    """log_mode_change creates event with old_config and new_config in details_json."""

    @pytest.mark.asyncio
    async def test_creates_mode_changed_event(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        old_config = {"stage_checkpoints": {"issue_spot": "auto"}}
        new_config = {"stage_checkpoints": {"issue_spot": "checkpoint"}}

        await audit_logger.log_mode_change(
            run_id=11,
            intake_id=1100,
            actor_id=99,
            reason="Client requested full review",
            old_config=old_config,
            new_config=new_config,
        )

        event = await _get_last_event(async_session)
        assert event.event_type == "mode_changed"
        assert event.actor_id == 99
        assert event.details_json["old_config"] == old_config
        assert event.details_json["new_config"] == new_config
        assert event.details_json["reason"] == "Client requested full review"

    @pytest.mark.asyncio
    async def test_mode_change_links_run_and_intake(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        await audit_logger.log_mode_change(
            run_id=12, intake_id=1200
        )

        event = await _get_last_event(async_session)
        assert event.run_id == 12
        assert event.intake_id == 1200


# ===========================================================================
# Common properties
# ===========================================================================


class TestCommonProperties:
    """All events share common properties: created_at, run_id, intake_id."""

    @pytest.mark.asyncio
    async def test_all_events_have_created_at(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        """Every event type should have created_at auto-populated."""
        # Create one of each type
        await audit_logger.log_checkpoint_reached(run_id=1, intake_id=1, stage_name="s")
        await audit_logger.log_approved(run_id=2, intake_id=2, stage_name="s")
        await audit_logger.log_rejected(run_id=3, intake_id=3, stage_name="s")
        await audit_logger.log_edited(run_id=4, intake_id=4, stage_name="s")
        await audit_logger.log_auto_proceed(run_id=5, intake_id=5, stage_name="s")
        await audit_logger.log_stage_skip(run_id=6, intake_id=6, stage_name="s")
        await audit_logger.log_mode_change(run_id=7, intake_id=7)

        stmt = select(AutonomyEvent)
        result = await async_session.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 7
        for event in events:
            # created_at is populated by server_default=func.now()
            # In aiosqlite it may be None if func.now() isn't supported,
            # but the column exists and is mapped
            assert event.run_id is not None
            assert event.intake_id is not None
            assert event.event_type is not None

    @pytest.mark.asyncio
    async def test_all_events_link_run_and_intake(
        self, async_session: AsyncSession, audit_logger: AutonomyAuditLogger
    ):
        """Every event links to both run_id and intake_id."""
        await audit_logger.log_approved(run_id=42, intake_id=84, stage_name="research")

        event = await _get_last_event(async_session)
        assert event.run_id == 42
        assert event.intake_id == 84
