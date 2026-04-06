"""Integration tests for OAuth router: login redirect, exchange endpoint, error cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sso_service import SSOService


@pytest.fixture(autouse=True)
def clear_nonces():
    """Ensure nonce store is clean between tests."""
    SSOService._nonces.clear()
    yield
    SSOService._nonces.clear()


@pytest.mark.asyncio
class TestOAuthRouter:
    """Integration tests for /api/v1/auth/oauth/* endpoints."""

    async def test_unknown_provider_404(self, async_client):
        res = await async_client.get("/api/v1/auth/oauth/login/yahoo")
        assert res.status_code == 404

    async def test_google_login_redirects(self, async_client, monkeypatch):
        """GET /login/google returns 302 redirect (mocked provider)."""
        from starlette.responses import RedirectResponse

        from app.core import oauth as oauth_module

        fake_client = MagicMock()
        fake_client.authorize_redirect = AsyncMock(
            return_value=RedirectResponse(
                url="https://accounts.google.com/o/oauth2/v2/auth?response_type=code",
                status_code=302,
            )
        )
        monkeypatch.setattr(
            oauth_module.oauth,
            "create_client",
            lambda name: fake_client if name == "google" else None,
        )
        res = await async_client.get(
            "/api/v1/auth/oauth/login/google", follow_redirects=False
        )
        assert res.status_code == 302
        assert "accounts.google.com" in res.headers.get("location", "")

    async def test_microsoft_login_redirects(self, async_client, monkeypatch):
        """GET /login/microsoft returns 302 redirect (mocked provider)."""
        from starlette.responses import RedirectResponse

        from app.core import oauth as oauth_module

        fake_client = MagicMock()
        fake_client.authorize_redirect = AsyncMock(
            return_value=RedirectResponse(
                url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                status_code=302,
            )
        )
        monkeypatch.setattr(
            oauth_module.oauth,
            "create_client",
            lambda name: fake_client if name == "microsoft" else None,
        )
        res = await async_client.get(
            "/api/v1/auth/oauth/login/microsoft", follow_redirects=False
        )
        assert res.status_code == 302
        assert "microsoftonline.com" in res.headers.get("location", "")

    async def test_exchange_endpoint_valid_code(self, async_client):
        """POST /exchange with valid nonce returns access_token + user."""
        # First, register a user via the API so we have one in the DB
        reg_res = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "ssoexchange@example.com",
                "password": "TestPass123!",
                "full_name": "SSO Exchange User",
            },
        )
        assert reg_res.status_code == 201
        user_data = reg_res.json()

        # Parse the access token to get user_id
        import jwt as pyjwt

        payload = pyjwt.decode(
            user_data["access_token"],
            options={"verify_signature": False},
        )
        user_id = payload["sub"]

        # Manually generate a nonce for this user
        nonce = SSOService.generate_exchange_code(str(user_id), "access-tok-from-sso")

        res = await async_client.post(
            "/api/v1/auth/oauth/exchange", json={"code": nonce}
        )
        assert res.status_code == 200
        body = res.json()
        assert body["access_token"] == "access-tok-from-sso"
        assert body["user"]["email"] == "ssoexchange@example.com"

    async def test_exchange_invalid_code(self, async_client):
        """POST /exchange with bogus nonce returns 400."""
        res = await async_client.post(
            "/api/v1/auth/oauth/exchange", json={"code": "bogus-nonce"}
        )
        assert res.status_code == 400

    async def test_exchange_single_use(self, async_client):
        """POST /exchange with same nonce twice: second call returns 400."""
        # Register user first
        reg_res = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "ssoonce@example.com",
                "password": "TestPass123!",
                "full_name": "SSO Once User",
            },
        )
        assert reg_res.status_code == 201
        user_data = reg_res.json()

        import jwt as pyjwt

        payload = pyjwt.decode(
            user_data["access_token"],
            options={"verify_signature": False},
        )
        user_id = payload["sub"]

        nonce = SSOService.generate_exchange_code(str(user_id), "tok")
        res1 = await async_client.post(
            "/api/v1/auth/oauth/exchange", json={"code": nonce}
        )
        assert res1.status_code == 200
        res2 = await async_client.post(
            "/api/v1/auth/oauth/exchange", json={"code": nonce}
        )
        assert res2.status_code == 400
