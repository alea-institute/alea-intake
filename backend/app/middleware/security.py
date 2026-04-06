"""Security headers middleware.

Adds standard security headers to all HTTP responses:
- Content-Security-Policy (configurable script-src)
- Strict-Transport-Security (configurable max-age)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 0 (deprecated; CSP supersedes)
- Referrer-Policy: strict-origin-when-cross-origin
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        settings = get_settings()

        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; script-src {settings.csp_script_src}; "
            f"style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            f"font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
