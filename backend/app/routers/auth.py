"""Authentication API endpoints: register, login, refresh, logout."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_current_active_user
from app.core.security import decode_token
from app.config import get_settings
from app.db.session import get_tenant_session
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_org_id(request: Request) -> int:
    """Extract org_id from tenant context. Default to 1 for testing."""
    return getattr(request.state, "org_id", 1)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Register a new user and return JWT tokens."""
    org_id = _get_org_id(request)
    auth_service = AuthService(session)
    _user, access_token, refresh_token = await auth_service.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        org_id=org_id,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Authenticate a user and return JWT tokens."""
    org_id = _get_org_id(request)
    auth_service = AuthService(session)
    _user, access_token, refresh_token = await auth_service.login(
        email=body.email,
        password=body.password,
        org_id=org_id,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Exchange a refresh token for new access + refresh tokens."""
    auth_service = AuthService(session)
    access_token, refresh_token = await auth_service.refresh_tokens(
        refresh_token_str=body.refresh_token,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Invalidate the current refresh token family."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1] if " " in auth_header else ""
    payload = decode_token(token, settings.secret_key)
    token_family = payload.get("family", "")

    # If the access token doesn't have a family, revoke all tokens for user
    if token_family:
        auth_service = AuthService(session)
        await auth_service.logout(user_id=current_user.id, token_family=token_family)
    else:
        # Access tokens don't have family; revoke all families for user
        from sqlalchemy import update
        from app.models.refresh_token import RefreshToken

        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.id)
            .values(is_revoked=True)
        )
        await session.flush()

    return {"message": "Logged out successfully"}
