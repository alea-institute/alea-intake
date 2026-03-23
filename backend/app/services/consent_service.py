"""Consent management service: grant, revoke, check, and query consent records.

Handles granular consent with org-configurable templates. Supports both
authenticated users (by user_id) and kiosk sessions (by session_id).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import ConsentRecord, ConsentTemplate


class ConsentService:
    """Service for managing consent records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def grant_consent(
        self,
        user_id: int | None,
        session_id: str | None,
        consent_version: str,
        consent_items: dict[str, bool],
        ip_address: str | None = None,
    ) -> ConsentRecord:
        """Grant consent, revoking any existing active consent first.

        Args:
            user_id: The user granting consent (None for kiosk sessions).
            session_id: The kiosk session ID (None for authenticated users).
            consent_version: Version string of the consent template.
            consent_items: Dict of consent item keys to boolean values.
            ip_address: The client's IP address.

        Returns:
            The newly created ConsentRecord.
        """
        # Revoke any existing active consent for this user/session
        await self.revoke_consent(user_id=user_id, session_id=session_id)

        record = ConsentRecord(
            user_id=user_id,
            session_id=session_id,
            consent_version=consent_version,
            consent_items=consent_items,
            ip_address=ip_address,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def revoke_consent(
        self,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> ConsentRecord | None:
        """Revoke active consent for a user or session.

        Sets revoked_at to current UTC time on the active consent record.

        Args:
            user_id: The user whose consent to revoke.
            session_id: The kiosk session whose consent to revoke.

        Returns:
            The revoked ConsentRecord, or None if no active consent found.
        """
        query = select(ConsentRecord).where(ConsentRecord.revoked_at.is_(None))

        if user_id is not None:
            query = query.where(ConsentRecord.user_id == user_id)
        elif session_id is not None:
            query = query.where(ConsentRecord.session_id == session_id)
        else:
            return None

        result = await self.session.execute(query)
        record = result.scalar_one_or_none()

        if record is not None:
            record.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()

        return record

    async def check_consent(
        self,
        user_id: int | None = None,
        session_id: str | None = None,
        required_item: str = "ai_processing",
    ) -> bool:
        """Check if active consent exists with a specific item granted.

        Args:
            user_id: The user to check consent for.
            session_id: The kiosk session to check consent for.
            required_item: The consent item key to check (default: "ai_processing").

        Returns:
            True if active consent exists and the required item is True.
        """
        record = await self.get_consent_status(
            user_id=user_id, session_id=session_id
        )
        if record is None:
            return False

        return record.consent_items.get(required_item, False) is True

    async def get_consent_status(
        self,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> ConsentRecord | None:
        """Get the active consent record for a user or session.

        Args:
            user_id: The user to look up.
            session_id: The kiosk session to look up.

        Returns:
            The active ConsentRecord, or None if no active consent.
        """
        query = select(ConsentRecord).where(ConsentRecord.revoked_at.is_(None))

        if user_id is not None:
            query = query.where(ConsentRecord.user_id == user_id)
        elif session_id is not None:
            query = query.where(ConsentRecord.session_id == session_id)
        else:
            return None

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_template(self, org_id: int) -> ConsentTemplate | None:
        """Get the active consent template for an organization.

        Args:
            org_id: The organization's ID.

        Returns:
            The active ConsentTemplate, or None if none configured.
        """
        result = await self.session.execute(
            select(ConsentTemplate).where(
                ConsentTemplate.org_id == org_id,
                ConsentTemplate.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
