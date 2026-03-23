"""JWT token creation/validation and password hashing.

Uses PyJWT for JWT operations and pwdlib with Argon2 for password hashing.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

# Argon2 hasher via pwdlib (recommended by FastAPI docs)
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2.

    Returns:
        Argon2 hash string (starts with $argon2).
    """
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Returns:
        True if the password matches, False otherwise.
    """
    return password_hash.verify(plain, hashed)


def create_access_token(
    user_id: int,
    org_id: int,
    role: str,
    secret_key: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's database ID.
        org_id: The user's organization ID.
        role: The user's role string (admin, professional, consumer).
        secret_key: The signing secret.
        expires_delta: Custom expiry duration (defaults to 30 minutes).

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def create_refresh_token(
    user_id: int,
    org_id: int,
    token_family: str,
    secret_key: str,
) -> str:
    """Create a JWT refresh token with family tracking for rotation detection.

    Args:
        user_id: The user's database ID.
        org_id: The user's organization ID.
        token_family: UUID family identifier for reuse detection.
        secret_key: The signing secret.

    Returns:
        Encoded JWT string with type=refresh and family claim.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "family": token_family,
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT string.
        secret_key: The signing secret used to create the token.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
    """
    return jwt.decode(token, secret_key, algorithms=["HS256"])
