"""Intake session lifecycle management.

Handles creating intakes, sessions, parties, and storing messages with
sequence numbering. Uses AsyncSession for database operations.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intake import Intake, IntakeParty, IntakeSession, Message


class IntakeSessionService:
    """Service for managing intake sessions and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_intake(
        self,
        org_id: int,
        user_id: int | None = None,
        session_mode: str = "multi_session",
    ) -> Intake:
        """Create a new intake record."""
        intake = Intake(
            org_id=org_id,
            created_by_user_id=user_id,
            session_mode=session_mode,
            status="active",
        )
        self.session.add(intake)
        await self.session.flush()
        return intake

    async def create_session(self, intake_id: int) -> IntakeSession:
        """Create a new session for an intake."""
        session_record = IntakeSession(
            intake_id=intake_id,
            status="active",
        )
        self.session.add(session_record)
        await self.session.flush()
        return session_record

    async def add_party(
        self,
        intake_id: int,
        user_id: int | None = None,
        role_in_intake: str = "primary",
        label: str | None = None,
    ) -> IntakeParty:
        """Add a party to an intake."""
        party = IntakeParty(
            intake_id=intake_id,
            user_id=user_id,
            role_in_intake=role_in_intake,
            label=label,
        )
        self.session.add(party)
        await self.session.flush()
        return party

    async def get_next_sequence(self, session_id: int) -> int:
        """Get the next sequence number for a session."""
        result = await self.session.execute(
            select(func.max(Message.sequence_number)).where(
                Message.session_id == session_id
            )
        )
        max_seq = result.scalar_one_or_none()
        return (max_seq or 0) + 1

    async def store_message(
        self,
        session_id: int,
        sender_type: str,
        modality: str,
        content: str,
        party_id: int | None = None,
        metadata_json: dict | None = None,
    ) -> Message:
        """Store a message in the database with auto-incremented sequence number."""
        seq = await self.get_next_sequence(session_id)
        msg = Message(
            session_id=session_id,
            party_id=party_id,
            sender_type=sender_type,
            modality=modality,
            content_encrypted=content.encode("utf-8"),
            sequence_number=seq,
            metadata_json=metadata_json,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def pause_session(self, session_id: int) -> IntakeSession:
        """Pause a session."""
        result = await self.session.execute(
            select(IntakeSession).where(IntakeSession.id == session_id)
        )
        session_record = result.scalar_one()
        session_record.status = "paused"
        session_record.ended_at = datetime.now(timezone.utc)
        await self.session.flush()
        return session_record

    async def resume_session(self, session_id: int) -> IntakeSession:
        """Resume a paused session."""
        result = await self.session.execute(
            select(IntakeSession).where(IntakeSession.id == session_id)
        )
        session_record = result.scalar_one()
        session_record.status = "active"
        session_record.ended_at = None
        await self.session.flush()
        return session_record

    async def list_intakes(self, org_id: int) -> list[Intake]:
        """List all intakes for an organization."""
        result = await self.session.execute(
            select(Intake).where(Intake.org_id == org_id).order_by(Intake.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_messages(
        self, session_id: int, limit: int = 50, offset: int = 0
    ) -> list[Message]:
        """Get paginated messages for a session."""
        result = await self.session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
