"""Audit log request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Audit log entry returned to clients."""

    id: int
    timestamp: datetime
    actor_id: int | None
    actor_role: str | None
    action: str
    resource_type: str | None
    resource_id: int | None
    details: dict | None
    ip_address: str | None
    request_id: str | None

    model_config = ConfigDict(from_attributes=True)


class AuditLogQuery(BaseModel):
    """Audit log query parameters."""

    action: str | None = None
    actor_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = 50
    offset: int = 0
