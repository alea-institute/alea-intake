"""SSO service: user upsert/link and one-time exchange code pattern.

Implements Pitfall 4 safe pattern: after OAuth callback, backend stores
the access token server-side keyed by a short-lived nonce. Frontend
exchanges the nonce for the token via POST (never in URL).
"""

import secrets
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@dataclass
class _NonceEntry:
    """In-memory nonce store entry with TTL."""

    user_id: str
    access_token: str
    expires_at: float


class SSOService:
    """OAuth user upsert + one-time-code exchange (Pitfall 4 safe pattern)."""

    # In-memory nonce store (MVP; Redis in production for multi-worker)
    _nonces: dict[str, _NonceEntry] = {}
    _NONCE_TTL_SEC = 60

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_user(
        self,
        *,
        email: str,
        provider: str,
        provider_id: str,
        full_name: Optional[str] = None,
        org_id: Optional[int] = None,
    ) -> User:
        """Find or create a user by SSO identity.

        Lookup order:
        1. By (sso_provider, sso_subject) -- strongest identity match
        2. By email -- link existing email-based account to SSO
        3. Create new user with consumer role

        Args:
            email: Email from OIDC provider userinfo.
            provider: Provider name ('google' or 'microsoft').
            provider_id: Provider's subject identifier (sub claim).
            full_name: Display name from provider (optional).
            org_id: Organization to create user in (required for new users).

        Returns:
            User instance (existing linked or newly created).

        Raises:
            ValueError: If org_id is not provided for new user creation.
        """
        # Try by (provider, subject) first -- strongest identity
        stmt = select(User).where(
            User.sso_provider == provider,
            User.sso_subject == provider_id,
        )
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            return user

        # Fallback: by email (link existing account)
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.sso_provider = provider
            user.sso_subject = provider_id
            if full_name and not user.full_name:
                user.full_name = full_name.encode("utf-8") if isinstance(full_name, str) else full_name
            await self._session.flush()
            return user

        # Create new user
        if not org_id:
            raise ValueError("org_id required for new SSO user creation")
        user = User(
            email=email,
            full_name=full_name.encode("utf-8") if full_name else None,
            role="consumer",
            org_id=org_id,
            sso_provider=provider,
            sso_subject=provider_id,
            hashed_password=None,  # SSO-only user, no password
        )
        self._session.add(user)
        await self._session.flush()
        return user

    @classmethod
    def generate_exchange_code(cls, user_id: str, access_token: str) -> str:
        """Create a short-lived one-time nonce for OAuth token exchange.

        The nonce is stored in memory keyed to (user_id, access_token).
        Expired entries are reaped on each call.

        Args:
            user_id: The user's database ID (as string).
            access_token: The JWT access token to store.

        Returns:
            A URL-safe nonce string (32+ characters).
        """
        now = time.time()
        # Reap expired entries
        expired = [n for n, e in cls._nonces.items() if e.expires_at < now]
        for n in expired:
            cls._nonces.pop(n, None)

        nonce = secrets.token_urlsafe(32)
        cls._nonces[nonce] = _NonceEntry(
            user_id=user_id,
            access_token=access_token,
            expires_at=now + cls._NONCE_TTL_SEC,
        )
        return nonce

    @classmethod
    def redeem_exchange_code(cls, nonce: str) -> tuple[str, str]:
        """Redeem a one-time exchange code for (user_id, access_token).

        The nonce is invalidated immediately (single-use).

        Args:
            nonce: The exchange code from the OAuth callback redirect.

        Returns:
            Tuple of (user_id, access_token).

        Raises:
            ValueError: If the nonce is invalid, already used, or expired.
        """
        entry = cls._nonces.pop(nonce, None)
        if not entry:
            raise ValueError("Invalid or already-used code")
        if entry.expires_at < time.time():
            raise ValueError("Code expired")
        return entry.user_id, entry.access_token
