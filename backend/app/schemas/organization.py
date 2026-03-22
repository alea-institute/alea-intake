"""Organization request/response schemas."""

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    """Organization data returned to clients."""

    id: int
    name: str
    slug: str
    auth_mode: str
    is_active: bool


class OrganizationCreate(BaseModel):
    """Organization creation payload."""

    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_-]+$")
