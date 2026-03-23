"""Tests for JWT token creation/validation and password hashing.

TDD RED: These tests define the expected behavior of backend/app/core/security.py
before the implementation exists.
"""

import time
from datetime import timedelta

import jwt
import pytest


class TestAccessToken:
    """create_access_token should produce valid JWT access tokens."""

    def test_returns_jwt_string(self):
        from app.core.security import create_access_token

        token = create_access_token(user_id=1, org_id=1, role="consumer", secret_key="test-key")
        assert isinstance(token, str)

    def test_contains_required_claims(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token(user_id=1, org_id=1, role="consumer", secret_key="test-key")
        payload = decode_token(token, "test-key")
        assert payload["sub"] == "1"
        assert payload["org"] == "1"
        assert payload["role"] == "consumer"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_custom_expiry(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            user_id=1, org_id=1, role="admin", secret_key="test-key",
            expires_delta=timedelta(minutes=60),
        )
        payload = decode_token(token, "test-key")
        assert payload["role"] == "admin"


class TestRefreshToken:
    """create_refresh_token should produce JWT refresh tokens with family tracking."""

    def test_returns_jwt_with_refresh_type(self):
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(user_id=1, org_id=1, token_family="abc", secret_key="test-key")
        payload = decode_token(token, "test-key")
        assert payload["type"] == "refresh"
        assert payload["family"] == "abc"

    def test_contains_user_and_org(self):
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(user_id=5, org_id=3, token_family="xyz", secret_key="test-key")
        payload = decode_token(token, "test-key")
        assert payload["sub"] == "5"
        assert payload["org"] == "3"


class TestDecodeToken:
    """decode_token should validate and decode JWTs."""

    def test_valid_token(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token(user_id=1, org_id=1, role="consumer", secret_key="test-key")
        payload = decode_token(token, "test-key")
        assert isinstance(payload, dict)
        assert payload["sub"] == "1"

    def test_expired_token_raises(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            user_id=1, org_id=1, role="consumer", secret_key="test-key",
            expires_delta=timedelta(seconds=0),
        )
        # Wait briefly for token to expire
        time.sleep(1)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token, "test-key")

    def test_invalid_secret_raises(self):
        from app.core.security import create_access_token, decode_token

        token = create_access_token(user_id=1, org_id=1, role="consumer", secret_key="test-key")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token, "wrong-key")


class TestPasswordHashing:
    """Password hashing should use Argon2 via pwdlib."""

    def test_hash_produces_argon2_string(self):
        from app.core.security import hash_password

        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert hashed.startswith("$argon2")

    def test_verify_correct_password(self):
        from app.core.security import hash_password, verify_password

        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        from app.core.security import hash_password, verify_password

        hashed = hash_password("mypassword")
        assert verify_password("wrong", hashed) is False
