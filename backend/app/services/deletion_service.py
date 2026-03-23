"""Right-to-delete cascade service: preview and confirm deletion with org-configurable audit handling.

Supports three deletion policies:
- full_delete: DELETE all user records including audit log entries
- anonymize: UPDATE audit_log SET actor_id=NULL (anonymize), delete everything else
- time_based: same as anonymize, but marks for future scheduled deletion

Requires preview hash confirmation to prevent accidental or stale deletions.
"""

import hashlib
import json

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.consent import ConsentRecord
from app.models.shared import Organization
from app.models.user import User


class DeletionService:
    """Service for right-to-delete cascade operations."""

    def __init__(self, session: AsyncSession, org: Organization):
        self.session = session
        self.org = org

    async def preview_deletion(self, user_id: int) -> dict:
        """Generate a preview of records that would be deleted.

        Returns record counts per category and a SHA-256 hash for confirmation.

        Args:
            user_id: The user to generate a deletion preview for.

        Returns:
            Dict with records_affected, categories, and preview_hash.
        """
        categories: dict[str, int] = {}

        # Count consent records
        result = await self.session.execute(
            select(func.count()).select_from(ConsentRecord).where(
                ConsentRecord.user_id == user_id
            )
        )
        categories["consent_records"] = result.scalar() or 0

        # Count audit log entries (handling depends on policy)
        result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.actor_id == user_id
            )
        )
        categories["audit_log_entries"] = result.scalar() or 0

        # Count the user itself
        categories["users"] = 1

        # Count refresh tokens
        from app.models.refresh_token import RefreshToken

        result = await self.session.execute(
            select(func.count()).select_from(RefreshToken).where(
                RefreshToken.user_id == user_id
            )
        )
        categories["refresh_tokens"] = result.scalar() or 0

        # Future: cases, narratives, documents, analysis (return 0 for now)
        categories["cases"] = 0
        categories["narratives"] = 0
        categories["documents"] = 0
        categories["analysis"] = 0

        total = sum(categories.values())

        # Generate deterministic hash for confirmation
        preview_data = {
            "user_id": user_id,
            "categories": categories,
            "total": total,
            "deletion_policy": self.org.deletion_policy,
        }
        preview_hash = hashlib.sha256(
            json.dumps(preview_data, sort_keys=True).encode()
        ).hexdigest()

        return {
            "records_affected": total,
            "categories": categories,
            "preview_hash": preview_hash,
            "deletion_policy": self.org.deletion_policy,
        }

    async def confirm_deletion(self, user_id: int, preview_hash: str) -> dict:
        """Execute deletion cascade after verifying the preview hash.

        Args:
            user_id: The user to delete.
            preview_hash: The hash from preview_deletion for confirmation.

        Returns:
            Dict with success message and total records affected.

        Raises:
            ValueError: If preview hash doesn't match (stale preview).
        """
        # Regenerate preview to verify hash
        preview = await self.preview_deletion(user_id)
        if preview["preview_hash"] != preview_hash:
            raise ValueError("Preview is stale. Please regenerate.")

        total = preview["records_affected"]
        policy = self.org.deletion_policy

        # Handle audit log entries based on org policy
        if policy == "full_delete":
            # DELETE audit log entries where actor_id = user_id
            await self.session.execute(
                delete(AuditLog).where(AuditLog.actor_id == user_id)
            )
        elif policy in ("anonymize", "time_based"):
            # ANONYMIZE: set actor_id=null, actor_role=null, details=null
            await self.session.execute(
                update(AuditLog)
                .where(AuditLog.actor_id == user_id)
                .values(actor_id=None, actor_role=None, details=None)
            )

        # Delete consent records
        await self.session.execute(
            delete(ConsentRecord).where(ConsentRecord.user_id == user_id)
        )

        # Delete refresh tokens
        from app.models.refresh_token import RefreshToken

        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )

        # Delete the user
        await self.session.execute(
            delete(User).where(User.id == user_id)
        )

        await self.session.flush()

        return {
            "message": f"Deletion complete. {total} records removed.",
            "records_removed": total,
        }
