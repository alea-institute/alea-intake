"""Structured logging with OTel trace correlation.

Configures structlog with JSON rendering and an OTel context processor
that injects trace_id and span_id into every log event when an active
span is present.
"""

from __future__ import annotations

import logging

import structlog
from opentelemetry import trace

from app.config import get_settings as get_settings  # Existing monitoring/test patch interface.
from app.observability.redaction import redact_event
from app.observability.third_party_logs import install_third_party_log_guard


def add_otel_context(
    logger: object,
    method_name: str | None,
    event_dict: dict,
) -> dict:
    """Structlog processor: inject OTel trace_id and span_id if active span exists."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and getattr(ctx, "is_valid", False):
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def setup_logging() -> None:
    """Configure structlog with JSON/console renderer and OTel correlation.

    Reads log_level and log_format from Settings.
    """
    from app import config
    settings = config.get_settings()
    # f-string messages from LLM-path libraries embed reply text; rewrite them
    # at record creation so no handler ever sees that content.
    install_third_party_log_guard()
    logging.getLogger("uvicorn.access").disabled = settings.showcase_mode or bool(settings.preview_passphrase)
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        add_otel_context,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_event,
    ]

    if settings.log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Replace existing handlers with structlog formatter
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    # Dependency loggers may own non-propagating file/console handlers.
    for named_logger in logging.Logger.manager.loggerDict.values():
        if isinstance(named_logger, logging.Logger):
            for handler in named_logger.handlers:
                handler.setFormatter(formatter)

    # Ensure at least one handler exists
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
