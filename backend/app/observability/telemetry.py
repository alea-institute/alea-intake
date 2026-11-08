"""OpenTelemetry tracing and Prometheus instrumentation setup.

When ALEA_OTEL_ENDPOINT is non-empty, creates a TracerProvider with
BatchSpanProcessor + OTLPSpanExporter and instruments FastAPI.
When empty, OTel is a complete no-op.

Prometheus metrics are always enabled via prometheus-fastapi-instrumentator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor, ReadableSpan
from app.observability.redaction import scrub
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(app: FastAPI) -> None:
    """Configure OTel tracing (opt-in).

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()

    # --- OTel tracing (opt-in) ---
    if settings.otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider = TracerProvider()
        provider.add_span_processor(RedactingSpanProcessor(BatchSpanProcessor(exporter)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OTel tracing enabled (endpoint=%s)", settings.otel_endpoint)
    else:
        logger.debug("OTel tracing disabled (ALEA_OTEL_ENDPOINT is empty)")


def setup_prometheus(app: FastAPI) -> None:
    """Instrument FastAPI with Prometheus metrics and expose /metrics endpoint.

    Should be called at app creation time (not during lifespan) so the
    /metrics route is registered before route resolution.

    Args:
        app: The FastAPI application instance.
    """
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus /metrics endpoint enabled")


class RedactingSpanProcessor(SpanProcessor):
    """Sanitize immutable export snapshots, including exception events."""
    def __init__(self, downstream):
        self.downstream = downstream

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        from opentelemetry.trace import Status
        from opentelemetry.sdk.trace import Event
        clean = ReadableSpan(
            name=scrub(span.name), context=span.context, parent=span.parent,
            resource=span.resource, attributes=scrub(dict(span.attributes or {})),
            events=[Event('event', attributes=scrub(dict(e.attributes or {})), timestamp=e.timestamp) for e in span.events],
            links=[], kind=span.kind, status=Status(span.status.status_code),
            start_time=span.start_time, end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )
        self.downstream.on_end(clean)

    def shutdown(self):
        self.downstream.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.downstream.force_flush(timeout_millis)
