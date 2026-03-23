"""Tenant resolution middleware.

Reads tenant identification from the X-Tenant-Slug header or JWT token's
org claim and sets request.state.tenant_schema for downstream session routing.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Routes that don't require tenant identification
PUBLIC_ROUTES = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
}


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from request headers or JWT and set on request state."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant resolution for public routes
        if path in PUBLIC_ROUTES or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Try X-Tenant-Slug header first
        tenant_slug = request.headers.get("X-Tenant-Slug")

        # Fall back to JWT org claim (will be implemented in Plan 02)
        if not tenant_slug:
            # Placeholder: extract from JWT token when auth is implemented
            # For now, check if there's a tenant_slug in request state
            # set by auth middleware
            tenant_slug = getattr(request.state, "tenant_slug", None)

        if not tenant_slug:
            return JSONResponse(
                status_code=400,
                content={"detail": "Tenant identification required"},
            )

        request.state.tenant_schema = f"tenant_{tenant_slug}"
        request.state.tenant_slug = tenant_slug

        return await call_next(request)
