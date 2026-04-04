"""Intake session lifecycle management.

Handles creation and state management for intakes, sessions, parties, and
messages. All operations go through an AsyncSession for transactional integrity.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intake import Intake, IntakeParty, IntakeSession, Message


class IntakeSessionService:
    """Manages intake session lifecycle: create, pause, resume, store messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_intake(
        self,
        org_id: int,
        user_id: int | None,
        session_mode: str = "multi_session",
    ) -> Intake:
        """Create a new intake record with status 'active'."""
        intake = Intake(
            org_id=org_id,
            status="active",
            created_by_user_id=user_id,
            session_mode=session_mode,
        )
        self._session.add(intake)
        await self._session.flush()
        return intake

    async def create_session(self, intake_id: int) -> IntakeSession:
        """Create a new session for the given intake with status 'active'."""
        session = IntakeSession(
            intake_id=intake_id,
            status="active",
        )
        self._session.add(session)
        await self._session.flush()
        return session

    async def add_party(
        self,
        intake_id: int,
        user_id: int | None,
        role_in_intake: str = "primary",
        label: str | None = None,
    ) -> IntakeParty:
        """Add a party (participant) to an intake."""
        party = IntakeParty(
            intake_id=intake_id,
            user_id=user_id,
            role_in_intake=role_in_intake,
            label=label,
        )
        self._session.add(party)
        await self._session.flush()
        return party

    async def get_next_sequence(self, session_id: int) -> int:
        """Return the next sequence number for messages in this session."""
        result = await self._session.execute(
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
        """Store a message in the intake session with auto-incremented sequence number.

        Content is stored as bytes in content_encrypted. Actual encryption will be
        wired through EncryptionContext in a future phase.
        """
        seq = await self.get_next_sequence(session_id)
        message = Message(
            session_id=session_id,
            party_id=party_id,
            sender_type=sender_type,
            modality=modality,
            content_encrypted=content.encode("utf-8"),
            sequence_number=seq,
            metadata_json=metadata_json,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def pause_session(self, session_id: int) -> IntakeSession:
        """Pause an active session by setting status to 'paused' and ended_at."""
        result = await self._session.execute(
            select(IntakeSession).where(IntakeSession.id == session_id)
        )
        session = result.scalar_one()
        session.status = "paused"
        session.ended_at = datetime.now(timezone.utc)
        await self._session.flush()
        return session

    async def resume_session(self, session_id: int) -> IntakeSession:
        """Resume a paused session by setting status to 'active' and clearing ended_at."""
        result = await self._session.execute(
            select(IntakeSession).where(IntakeSession.id == session_id)
        )
        session = result.scalar_one()
        session.status = "active"
        session.ended_at = None
        await self._session.flush()
        return session

    async def list_intakes(self, org_id: int) -> list[Intake]:
        """List all intakes for an organization, ordered by created_at descending."""
        result = await self._session.execute(
            select(Intake)
            .where(Intake.org_id == org_id)
            .order_by(Intake.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_messages(
        self,
        session_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """Retrieve messages for a session, ordered by sequence number."""
        result = await self._session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
