"""OAuth SSO endpoints: login redirect, callback, and one-time code exchange.

Implements the Pitfall 4 safe pattern:
  1. /login/{provider} -> 302 to provider consent screen
  2. /callback/{provider} -> provider exchanges code for tokens, upserts user,
     mints JWTs, sets refresh cookie, redirects to /oauth/finish?code=<nonce>
  3. /exchange -> frontend POSTs nonce, receives {access_token, user} JSON

Access tokens never appear in URLs or browser history.
"""

import uuid
from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.oauth import oauth
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_tenant_session
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.sso_service import SSOService

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])

SUPPORTED_PROVIDERS = {"google", "microsoft"}


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for secure storage (same as AuthService)."""
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request):
    """Redirect user to OAuth provider's consent screen."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Unknown provider: {provider}")
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(503, f"{provider} SSO not configured")
    settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Handle OAuth provider callback: exchange code, upsert user, redirect with nonce."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(404, f"Unknown provider: {provider}")
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(503, f"{provider} SSO not configured")

    settings = get_settings()

    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(400, f"OAuth exchange failed: {e}")

    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await client.parse_id_token(request, token)

    email = userinfo.get("email")
    if not email:
        raise HTTPException(400, "Provider did not return email")

    sso_service = SSOService(session)

    # Determine org: use request org context or default to 1 (seeded org)
    org_id = getattr(request.state, "org_id", None) or 1

    user = await sso_service.upsert_user(
        email=email,
        provider=provider,
        provider_id=userinfo.get("sub", ""),
        full_name=userinfo.get("name"),
        org_id=org_id,
    )
    await session.commit()

    # Mint tokens using same approach as AuthService
    token_family = uuid.uuid4().hex
    access_token = create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
        secret_key=settings.secret_key,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        org_id=user.org_id,
        token_family=token_family,
        secret_key=settings.secret_key,
    )

    # Store refresh token (hashed)
    rt = RefreshToken(
        user_id=user.id,
        token_family=token_family,
        token_hash=_hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(rt)
    await session.flush()

    # Generate one-time exchange code (Pitfall 4 -- no token in URL)
    nonce = SSOService.generate_exchange_code(str(user.id), access_token)

    response = RedirectResponse(
        url=f"{settings.frontend_base_url}/oauth/finish?code={nonce}",
        status_code=302,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=(settings.debug is False and "localhost" not in settings.frontend_base_url),
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/v1/auth/refresh",
    )
    return response


class ExchangeRequest(BaseModel):
    """Request body for OAuth token exchange."""

    code: str


@router.post("/exchange")
async def oauth_exchange(
    body: ExchangeRequest,
    session: AsyncSession = Depends(get_tenant_session),
):
    """Exchange a one-time nonce for access_token + user data."""
    try:
        user_id, access_token = SSOService.redeem_exchange_code(body.code)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Look up user by ID
    result = await session.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    return JSONResponse({
        "access_token": access_token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role if isinstance(user.role, str) else user.role.value,
            "org_id": str(user.org_id),
            "full_name": user.full_name.decode("utf-8") if isinstance(user.full_name, bytes) else user.full_name,
        },
    })
