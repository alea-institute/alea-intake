"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    """New user registration."""

    email: EmailStr
    password: str = ""  # min_length enforced at service layer; empty for kiosk
    full_name: str


class RefreshRequest(BaseModel):
    """Refresh token exchange."""

    refresh_token: str
