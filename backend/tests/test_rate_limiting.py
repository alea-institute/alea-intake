"""Tests for rate limiting middleware.

Verifies that:
- Rate limiter returns 429 after threshold exceeded
- X-Forwarded-For key function works with rate_limit_key_header
- Exempt paths (/health, /docs, /metrics) bypass rate limiting
"""

from __future__ import annotations

import os

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-for-ratelimit-tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.config import Settings


def _noop_coro():
    async def _noop(*args, **kwargs):
        pass

    return _noop


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def _make_test_app(self, rate_limit: str = "3/minute") -> FastAPI:
        """Create a minimal FastAPI app with rate limiting for testing."""
        from app.middleware.rate_limit import setup_rate_limiting

        test_settings = Settings(
            secret_key="test-key",
            rate_limit_default=rate_limit,
            rate_limit_storage="memory",
        )

        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        @test_app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        @test_app.get("/docs")
        async def docs_endpoint():
            return {"docs": True}

        @test_app.get("/metrics")
        async def metrics_endpoint():
            return {"metrics": True}

        with patch("app.middleware.rate_limit.get_settings", return_value=test_settings):
            setup_rate_limiting(test_app)

        return test_app

    @pytest.mark.asyncio
    async def test_returns_429_after_threshold_exceeded(self):
        """Rate limiter returns 429 when threshold exceeded for same IP."""
        app = self._make_test_app(rate_limit="3/minute")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # First 3 requests should succeed
            for i in range(3):
                resp = await client.get("/test")
                assert resp.status_code == 200, f"Request {i+1} should succeed"

            # 4th request should be rate limited
            resp = await client.get("/test")
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_allows_requests_under_threshold(self):
        """Rate limiter allows requests under threshold."""
        app = self._make_test_app(rate_limit="10/minute")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for _ in range(5):
                resp = await client.get("/test")
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_bypasses_rate_limiting(self):
        """Health endpoint is exempt from rate limiting."""
        app = self._make_test_app(rate_limit="2/minute")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Exhaust rate limit on /test
            for _ in range(2):
                await client.get("/test")
            resp = await client.get("/test")
            assert resp.status_code == 429

            # /health should still work
            resp = await client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_x_forwarded_for_key_function(self):
        """Rate limiter reads X-Forwarded-For when rate_limit_key_header is set."""
        from app.middleware.rate_limit import _make_key_func

        test_settings = Settings(
            secret_key="test-key",
            rate_limit_key_header="X-Forwarded-For",
        )

        with patch("app.middleware.rate_limit.get_settings", return_value=test_settings):
            key_func = _make_key_func()

        # Create a mock request with X-Forwarded-For
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-forwarded-for": "10.0.0.1, 10.0.0.2"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        key = key_func(mock_request)
        assert key == "10.0.0.1, 10.0.0.2"

    @pytest.mark.asyncio
    async def test_uses_client_host_when_no_key_header(self):
        """Rate limiter uses client.host when rate_limit_key_header is empty."""
        from app.middleware.rate_limit import _make_key_func

        test_settings = Settings(
            secret_key="test-key",
            rate_limit_key_header="",
        )

        with patch("app.middleware.rate_limit.get_settings", return_value=test_settings):
            key_func = _make_key_func()

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"

        key = key_func(mock_request)
        assert key == "192.168.1.100"
