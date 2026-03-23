"""Audit logging service: creating and querying immutable audit trail entries.

All state-changing API requests produce an audit log entry with timestamp,
actor, action, resource, IP, and request ID.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    """Service for creating and querying audit log entries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(
        self,
        action: str,
        actor_id: int | None = None,
        actor_role: str | None = None,
        resource_type: str | None = None,
        resource_id: int | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry with all provided fields.

        Args:
            action: The action performed (e.g., "user.login", "case.view").
            actor_id: The ID of the user performing the action (None for system/anonymous).
            actor_role: The role of the actor (e.g., "admin", "consumer").
            resource_type: The type of resource affected (e.g., "user", "case").
            resource_id: The ID of the affected resource.
            details: Additional JSON details about the action.
            ip_address: The client's IP address.
            request_id: The correlation ID for request tracing.

        Returns:
            The created AuditLog entry.
        """
        entry = AuditLog(
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            request_id=request_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def query_logs(
        self,
        action: str | None = None,
        actor_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query audit log entries with optional filters.

        Args:
            action: Filter by action string (exact match).
            actor_id: Filter by actor ID.
            start_date: Filter entries on or after this date.
            end_date: Filter entries on or before this date.
            limit: Maximum number of results (default 50).
            offset: Number of results to skip (default 0).

        Returns:
            List of matching AuditLog entries, ordered by timestamp DESC.
        """
        query = select(AuditLog)

        if action is not None:
            query = query.where(AuditLog.action == action)
        if actor_id is not None:
            query = query.where(AuditLog.actor_id == actor_id)
        if start_date is not None:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date is not None:
            query = query.where(AuditLog.timestamp <= end_date)

        query = query.order_by(AuditLog.timestamp.desc())
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())
