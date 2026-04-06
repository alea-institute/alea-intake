"""Tests for observability stack: Settings extensions, OTel, health, metrics, logging."""

from __future__ import annotations

import os

# Set env var before any module-level get_settings() calls from app.main imports
os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-for-monitoring-tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import DeploymentMode, PersistenceMode, Settings


# ---------------------------------------------------------------------------
# Test 1-2: Settings enum and field extensions
# ---------------------------------------------------------------------------


class TestSettingsExtensions:
    """Tests for new Phase 11 Settings fields."""

    def test_deployment_mode_defaults_single_tenant(self):
        s = Settings(secret_key="test-key")
        assert s.deployment_mode == DeploymentMode.SINGLE_TENANT

    def test_persistence_mode_defaults_persistent(self):
        s = Settings(secret_key="test-key")
        assert s.persistence_mode == PersistenceMode.PERSISTENT

    def test_deployment_mode_enum_values(self):
        assert DeploymentMode.MULTI_TENANT == "multi_tenant"
        assert DeploymentMode.SINGLE_TENANT == "single_tenant"

    def test_persistence_mode_enum_values(self):
        assert PersistenceMode.EPHEMERAL == "ephemeral"
        assert PersistenceMode.PERSISTENT == "persistent"
        assert PersistenceMode.CMS_INTEGRATED == "cms_integrated"

    def test_otel_fields_defaults(self):
        s = Settings(secret_key="test-key")
        assert s.otel_endpoint == ""
        assert s.otel_service_name == "alea-intake"

    def test_log_fields_defaults(self):
        s = Settings(secret_key="test-key")
        assert s.log_level == "INFO"
        assert s.log_format == "json"

    def test_rate_limit_fields_defaults(self):
        s = Settings(secret_key="test-key")
        assert s.rate_limit_default == "100/minute"
        assert s.rate_limit_key_header == ""
        assert s.rate_limit_storage == "memory"

    def test_security_fields_defaults(self):
        s = Settings(secret_key="test-key")
        assert s.csp_script_src == "'self'"
        assert s.hsts_max_age == 31536000
        assert s.max_request_size_mb == 50

    def test_cms_fields_defaults(self):
        s = Settings(secret_key="test-key")
        assert s.cms_enabled is False
        assert s.cms_sync_interval_seconds == 300

    def test_tenant_signup_mode_default(self):
        s = Settings(secret_key="test-key")
        assert s.tenant_signup_mode == "admin_approval"

    def test_settings_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("ALEA_SECRET_KEY", "env-secret")
        monkeypatch.setenv("ALEA_DEPLOYMENT_MODE", "multi_tenant")
        monkeypatch.setenv("ALEA_OTEL_ENDPOINT", "http://otel:4318")
        monkeypatch.setenv("ALEA_CMS_ENABLED", "true")
        s = Settings()
        assert s.deployment_mode == DeploymentMode.MULTI_TENANT
        assert s.otel_endpoint == "http://otel:4318"
        assert s.cms_enabled is True


# ---------------------------------------------------------------------------
# Test 3-4: OTel telemetry setup
# ---------------------------------------------------------------------------


class TestTelemetrySetup:
    """Tests for setup_telemetry no-op and active modes."""

    def test_noop_when_otel_endpoint_empty(self):
        """OTel is a no-op when ALEA_OTEL_ENDPOINT is empty."""
        from app.observability.telemetry import setup_telemetry

        app = MagicMock()
        # Should not crash, should not create any exporter
        with patch("app.observability.telemetry.get_settings") as mock_settings:
            mock_settings.return_value = Settings(secret_key="test-key", otel_endpoint="")
            setup_telemetry(app)
        # No exporter should have been set up -- just ensure no exception

    def test_creates_tracer_when_otel_endpoint_set(self):
        """OTel TracerProvider created when endpoint is non-empty."""
        from app.observability.telemetry import setup_telemetry

        app = MagicMock()
        with (
            patch("app.observability.telemetry.get_settings") as mock_settings,
            patch("app.observability.telemetry.TracerProvider") as mock_tp,
            patch("app.observability.telemetry.BatchSpanProcessor"),
            patch("app.observability.telemetry.OTLPSpanExporter"),
            patch("app.observability.telemetry.trace") as mock_trace,
            patch("app.observability.telemetry.FastAPIInstrumentor") as mock_fai,
        ):
            mock_settings.return_value = Settings(
                secret_key="test-key",
                otel_endpoint="http://otel:4318",
            )
            setup_telemetry(app)
            mock_tp.assert_called_once()
            mock_trace.set_tracer_provider.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5-6: structlog setup and OTel correlation
# ---------------------------------------------------------------------------


class TestLoggingSetup:
    """Tests for structlog configuration and OTel correlation processor."""

    def test_setup_logging_configures_structlog(self):
        from app.observability.logging import setup_logging

        with patch("app.observability.logging.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                secret_key="test-key", log_level="DEBUG", log_format="json"
            )
            setup_logging()
        # Should not crash; structlog is configured
        import structlog

        logger = structlog.get_logger()
        assert logger is not None

    def test_add_otel_context_injects_trace_ids(self):
        from app.observability.logging import add_otel_context

        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_ctx.span_id = 0x1234567890ABCDEF
        mock_ctx.trace_flags = MagicMock()
        mock_ctx.trace_flags.__int__ = lambda self: 1
        mock_span.get_span_context.return_value = mock_ctx

        with patch("app.observability.logging.trace") as mock_trace_mod:
            mock_trace_mod.get_current_span.return_value = mock_span
            # is_valid is on the span context
            mock_ctx.is_valid = True
            result = add_otel_context(None, None, {"existing": "data"})

        assert "trace_id" in result
        assert "span_id" in result
        assert result["existing"] == "data"

    def test_add_otel_context_noop_without_active_span(self):
        from app.observability.logging import add_otel_context

        mock_span = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.is_valid = False
        mock_span.get_span_context.return_value = mock_ctx

        with patch("app.observability.logging.trace") as mock_trace_mod:
            mock_trace_mod.get_current_span.return_value = mock_span
            result = add_otel_context(None, None, {"existing": "data"})

        assert "trace_id" not in result
        assert result["existing"] == "data"


# ---------------------------------------------------------------------------
# Test 7-8: Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for extended /health component checks."""

    @pytest.mark.asyncio
    async def test_check_health_returns_component_status(self):
        from app.observability.health import check_health

        app = MagicMock()
        app.state = MagicMock()
        app.state.folio_mcp_client = MagicMock()
        app.state.folio_mcp_client.is_connected = True

        with (
            patch("app.observability.health.get_engine") as mock_engine,
            patch("app.observability.health.get_owl_status") as mock_owl,
            patch("app.observability.health.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(secret_key="test-key")
            mock_owl.return_value = {"cached": True, "etag": "abc"}

            # Mock DB engine
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.execute = AsyncMock()
            mock_engine.return_value.connect = MagicMock(return_value=mock_conn)

            result = await check_health(app)

        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert "database" in result
        assert "folio_owl" in result
        assert "folio_mcp" in result
        assert "llm_provider" in result

    @pytest.mark.asyncio
    async def test_check_health_degraded_on_db_failure(self):
        from app.observability.health import check_health

        app = MagicMock()
        app.state = MagicMock()
        app.state.folio_mcp_client = None

        with (
            patch("app.observability.health.get_engine") as mock_engine,
            patch("app.observability.health.get_owl_status") as mock_owl,
            patch("app.observability.health.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Settings(secret_key="test-key")
            mock_owl.return_value = {"cached": True}

            # DB connection fails
            mock_engine.return_value.connect = MagicMock(
                side_effect=Exception("Connection refused")
            )

            result = await check_health(app)

        assert result["status"] == "degraded"
        assert result["database"]["status"] == "down"


# ---------------------------------------------------------------------------
# Test 9: Custom Prometheus metrics
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    """Tests for custom Prometheus counters and histograms."""

    def test_metrics_importable_and_increment(self):
        from app.observability.metrics import (
            ANALYSIS_STAGE_DURATION,
            INTAKE_COUNTER,
            LLM_COST_HISTOGRAM,
            SCREENING_TRIGGER_COUNTER,
        )

        # Counters should be incrementable
        INTAKE_COUNTER.labels(org_slug="test", mode="consumer").inc()
        LLM_COST_HISTOGRAM.labels(provider="openai", model="gpt-4").observe(0.05)
        SCREENING_TRIGGER_COUNTER.labels(
            protocol_name="dv_screening", trigger_type="auto"
        ).inc()
        ANALYSIS_STAGE_DURATION.labels(stage_name="issue_spotting").observe(1.5)

        # Verify counter value is at least 1
        assert (
            INTAKE_COUNTER.labels(org_slug="test", mode="consumer")._value.get() >= 1
        )


# ---------------------------------------------------------------------------
# Test 10-11: /metrics and /health endpoints
# ---------------------------------------------------------------------------


class TestEndpoints:
    """Tests for /metrics and /health HTTP endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(self):
        """GET /metrics returns Prometheus text format.

        The /metrics route is registered at module level (setup_prometheus),
        so it's already on the app when we import it.
        """
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
        ):
            test_settings = Settings(
                secret_key="test-key",
                database_backend="sqlite",
            )
            mock_gs.return_value = test_settings
            mock_tel_gs.return_value = test_settings
            mock_log_gs.return_value = test_settings
            mock_emb_cls.get_instance.return_value = MagicMock()
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/metrics")

            # prometheus-fastapi-instrumentator exposes /metrics
            assert resp.status_code == 200
            body = resp.text
            assert "python_" in body or "process_" in body or "alea_" in body or "http_" in body

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_extended_json(self):
        """GET /health returns extended component status JSON."""
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
            patch("app.main.get_engine") as mock_engine,
            patch("app.main.dispose_engine", new_callable=lambda: _noop_coro),
            patch("app.main.get_settings") as mock_gs,
            patch("app.observability.health.get_engine") as mock_health_engine,
            patch("app.observability.health.get_owl_status") as mock_owl,
        ):
            mock_gs.return_value = Settings(
                secret_key="test-key",
                database_backend="sqlite",
            )
            mock_emb_cls.get_instance.return_value = MagicMock()
            mock_owl.return_value = {"cached": True, "etag": "abc"}

            # Mock DB for health
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.execute = AsyncMock()
            mock_health_engine.return_value.connect = MagicMock(return_value=mock_conn)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/health")

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] in ("healthy", "degraded")
            assert data["version"] == "1.0.0"
            assert "database" in data
            assert "folio_owl" in data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noop_coro():
    """Return an async noop function for patching coroutines."""

    async def _noop(*args, **kwargs):
        pass

    return _noop
