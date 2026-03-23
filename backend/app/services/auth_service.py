"""Authentication service: registration, login, token refresh, and logout.

Handles all auth business logic including refresh token rotation with
family-based reuse detection (invalidating entire families on replay).
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Authentication and token management service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        org_id: int,
        role: str = "consumer",
    ) -> tuple[User, str, str]:
        """Register a new user and return tokens.

        Args:
            email: User's email address.
            password: Plaintext password to hash.
            full_name: User's full name (stored as bytes for future encryption).
            org_id: Organization ID for the tenant.
            role: User role (defaults to consumer).

        Returns:
            Tuple of (user, access_token, refresh_token).

        Raises:
            HTTPException 409: If email already exists in this tenant.
        """
        # Check for duplicate email in the tenant
        result = await self.session.execute(
            select(User).where(User.email == email, User.org_id == org_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        # Create user
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name.encode("utf-8"),
            role=role,
            org_id=org_id,
        )
        self.session.add(user)
        await self.session.flush()

        # Generate tokens
        token_family = uuid.uuid4().hex
        access_token = create_access_token(
            user_id=user.id,
            org_id=user.org_id,
            role=user.role,
            secret_key=self.settings.secret_key,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            org_id=user.org_id,
            token_family=token_family,
            secret_key=self.settings.secret_key,
        )

        # Store refresh token (hashed)
        rt = RefreshToken(
            user_id=user.id,
            token_family=token_family,
            token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(rt)
        await self.session.flush()

        return user, access_token, refresh_token

    async def login(self, email: str, password: str, org_id: int) -> tuple[User, str, str]:
        """Authenticate a user and return tokens.

        Args:
            email: User's email address.
            password: Plaintext password to verify.
            org_id: Organization ID for the tenant.

        Returns:
            Tuple of (user, access_token, refresh_token).

        Raises:
            HTTPException 401: If credentials are invalid.
        """
        result = await self.session.execute(
            select(User).where(User.email == email, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Generate new token family
        token_family = uuid.uuid4().hex
        access_token = create_access_token(
            user_id=user.id,
            org_id=user.org_id,
            role=user.role,
            secret_key=self.settings.secret_key,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            org_id=user.org_id,
            token_family=token_family,
            secret_key=self.settings.secret_key,
        )

        # Store refresh token
        rt = RefreshToken(
            user_id=user.id,
            token_family=token_family,
            token_hash=_hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(rt)
        await self.session.flush()

        return user, access_token, refresh_token

    async def refresh_tokens(self, refresh_token_str: str) -> tuple[str, str]:
        """Rotate a refresh token, returning new access + refresh tokens.

        Implements reuse detection: if a previously-used refresh token is
        replayed, the entire token family is revoked (potential theft).

        Args:
            refresh_token_str: The JWT refresh token string.

        Returns:
            Tuple of (new_access_token, new_refresh_token).

        Raises:
            HTTPException 401: If token is invalid, expired, revoked, or reused.
        """
        import jwt as pyjwt

        try:
            payload = decode_token(refresh_token_str, self.settings.secret_key)
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )
        except pyjwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        token_hash = _hash_token(refresh_token_str)
        token_family = payload["family"]
        user_id = int(payload["sub"])
        org_id = int(payload["org"])

        # Look up the stored refresh token by hash
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored_token = result.scalar_one_or_none()

        if stored_token is None or stored_token.is_revoked:
            # Reuse detected or token not found -- revoke entire family
            await self.session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.token_family == token_family,
                )
                .values(is_revoked=True)
            )
            await self.session.flush()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        # Mark the current token as revoked (single use)
        stored_token.is_revoked = True
        await self.session.flush()

        # Create new tokens in the same family
        new_access_token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=payload.get("role", "consumer"),
            secret_key=self.settings.secret_key,
            expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
        )

        # Fetch user to get current role (in case it changed)
        user_result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            new_access_token = create_access_token(
                user_id=user.id,
                org_id=user.org_id,
                role=user.role,
                secret_key=self.settings.secret_key,
                expires_delta=timedelta(minutes=self.settings.access_token_expire_minutes),
            )

        new_refresh_token = create_refresh_token(
            user_id=user_id,
            org_id=org_id,
            token_family=token_family,
            secret_key=self.settings.secret_key,
        )

        # Store new refresh token
        new_rt = RefreshToken(
            user_id=user_id,
            token_family=token_family,
            token_hash=_hash_token(new_refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(new_rt)
        await self.session.flush()

        return new_access_token, new_refresh_token

    async def logout(self, user_id: int, token_family: str) -> None:
        """Revoke all refresh tokens in a family for a user.

        Args:
            user_id: The user's database ID.
            token_family: The token family to revoke.
        """
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_family == token_family,
            )
            .values(is_revoked=True)
        )
        await self.session.flush()
