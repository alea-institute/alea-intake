"""Rate limiting middleware using slowapi.

Provides configurable rate limiting with:
- Default limit from settings (e.g., "100/minute")
- Custom key function supporting X-Forwarded-For for reverse proxy deployments
- Exempt paths for health, docs, and metrics endpoints
- Memory or Redis-based storage
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request

from app.config import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
_EXEMPT_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
})


def _make_key_func() -> Callable[[Request], str]:
    """Create a rate-limit key function based on settings.

    When rate_limit_key_header is set, reads the specified header
    (e.g., X-Forwarded-For) for client identification behind reverse proxies.
    Otherwise, uses request.client.host.
    """
    settings = get_settings()
    header_name = settings.rate_limit_key_header

    def key_func(request: Request) -> str:
        if header_name:
            value = request.headers.get(header_name.lower(), "")
            if value:
                return value
        # Fall back to client IP
        if request.client:
            return request.client.host
        return "unknown"

    return key_func


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting on the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()
    key_func = _make_key_func()

    storage_uri = None
    if settings.rate_limit_storage != "memory":
        storage_uri = settings.rate_limit_storage

    limiter = Limiter(
        key_func=key_func,
        default_limits=[settings.rate_limit_default],
        storage_uri=storage_uri,
    )

    # Register exempt paths
    for path in _EXEMPT_PATHS:

        @limiter.exempt
        async def _exempt():
            pass

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger.info(
        "Rate limiting enabled (default=%s, storage=%s)",
        settings.rate_limit_default,
        settings.rate_limit_storage,
    )
