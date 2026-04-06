"""Tests for SecurityHeadersMiddleware.

Verifies that all API responses include the required security headers:
CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
"""

from __future__ import annotations

import os

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-for-security-tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings


def _noop_coro():
    async def _noop(*args, **kwargs):
        pass

    return _noop


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    async def _get_response(self):
        """Make a GET /health request through the full app and return response."""
        from app.main import app

        with (
            patch("app.main.ensure_owl_fresh"),
            patch("app.main.get_folio"),
            patch("app.main.EmbeddingService") as mock_emb_cls,
            patch("app.main.OWLUpdateManager"),
            patch("app.main._periodic_owl_check", new_callable=lambda: _noop_coro),
            patch("app.main.ResearchToolRegistry"),
            patch("app.main.CourtListenerAdapter"),
            patch("app.main._seed_screening_protocols", new_callable=lambda: _noop_coro),
            patch("app.main.get_engine"),
            patch("app.main.dispose_engine", new_callable=lambda: _noop_coro),
            patch("app.main.get_settings") as mock_gs,
            patch("app.observability.telemetry.get_settings") as mock_tel_gs,
            patch("app.observability.logging.get_settings") as mock_log_gs,
            patch("app.observability.health.get_engine") as mock_health_engine,
            patch("app.observability.health.get_owl_status") as mock_owl,
        ):
            test_settings = Settings(
                secret_key="test-key",
                database_backend="sqlite",
            )
            mock_gs.return_value = test_settings
            mock_tel_gs.return_value = test_settings
            mock_log_gs.return_value = test_settings
            mock_owl.return_value = {"cached": True}

            # Mock DB for health
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.execute = AsyncMock()
            mock_health_engine.return_value.connect = MagicMock(return_value=mock_conn)

            mock_emb_cls.get_instance.return_value = MagicMock()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                return await client.get("/health")

    async def test_csp_header_present(self):
        """Response includes Content-Security-Policy header."""
        resp = await self._get_response()
        assert resp.status_code == 200
        csp = resp.headers.get("content-security-policy", "")
        assert "'self'" in csp

    async def test_hsts_header_present(self):
        """Response includes Strict-Transport-Security header."""
        resp = await self._get_response()
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts

    async def test_x_content_type_options_header(self):
        """Response includes X-Content-Type-Options: nosniff."""
        resp = await self._get_response()
        assert resp.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options_header(self):
        """Response includes X-Frame-Options: DENY."""
        resp = await self._get_response()
        assert resp.headers.get("x-frame-options") == "DENY"

    async def test_referrer_policy_header(self):
        """Response includes Referrer-Policy: strict-origin-when-cross-origin."""
        resp = await self._get_response()
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
