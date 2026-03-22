"""Consent request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsentGrantRequest(BaseModel):
    """Request to grant consent."""

    consent_version: str
    consent_items: dict[str, bool]


class ConsentResponse(BaseModel):
    """Consent record returned to clients."""

    id: int
    user_id: int | None
    session_id: str | None
    consent_version: str
    granted_at: datetime
    revoked_at: datetime | None
    consent_items: dict
    ip_address: str | None

    model_config = ConfigDict(from_attributes=True)


class ConsentTemplateResponse(BaseModel):
    """Consent template returned to clients."""

    id: int
    org_id: int
    version: str
    items: list
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
