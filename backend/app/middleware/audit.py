"""Audit logging middleware -- captures all API requests and logs to audit trail.

Generates a unique request_id (UUID) per request, adds X-Request-ID response
header, and logs the action to the audit log in a background task using a
separate session (audit must succeed even if the request transaction rolls back).

Skips logging for health, docs, and OpenAPI endpoints.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db.engine import get_engine

# Paths to skip audit logging for
SKIP_AUDIT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

# Map common request patterns to human-readable action names
ACTION_MAP: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/auth/login"): "auth.login",
    ("POST", "/api/v1/auth/register"): "auth.register",
    ("POST", "/api/v1/auth/refresh"): "auth.refresh",
    ("POST", "/api/v1/auth/logout"): "auth.logout",
    ("GET", "/api/v1/users/me"): "user.profile.read",
}


def _path_to_action(method: str, path: str) -> str:
    """Convert a request method + path to an action string.

    Uses ACTION_MAP for known routes, falls back to a generic
    method.path-segments format.
    """
    key = (method.upper(), path.rstrip("/"))
    if key in ACTION_MAP:
        return ACTION_MAP[key]

    # Generic: strip /api/v1/ prefix, replace / with .
    clean_path = path.rstrip("/")
    if clean_path.startswith("/api/v1/"):
        clean_path = clean_path[len("/api/v1/"):]
    elif clean_path.startswith("/"):
        clean_path = clean_path[1:]

    segments = clean_path.replace("/", ".")
    return f"{segments}.{method.lower()}"


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every API request to the audit trail.

    - Generates a UUID request_id for correlation
    - Adds X-Request-ID response header
    - Logs the action, actor, IP, and request_id to audit_log table
    - Uses a separate DB session for audit logging (isolation from request tx)
    - Skips /health, /docs, /openapi.json, /redoc
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/") or "/"

        # Skip audit for non-API paths
        if path in SKIP_AUDIT_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Generate request ID and store in request state
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Process the request
        response: Response = await call_next(request)

        # Add X-Request-ID header
        response.headers["X-Request-ID"] = request_id

        # Log audit in a separate session (background-ish but inline to keep it simple)
        try:
            await self._log_audit(request, response, request_id)
        except Exception as e:
            # Audit logging must not break the response
            import logging
            logging.getLogger(__name__).warning("Audit logging failed: %s", e)

        return response

    async def _log_audit(
        self, request: Request, response: Response, request_id: str
    ) -> None:
        """Log the request to the audit trail using a separate DB session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        method = request.method
        path = request.url.path.rstrip("/") or "/"

        action = _path_to_action(method, path)

        # Extract actor info from request state (set by auth dependency)
        actor_id = getattr(request.state, "actor_id", None)
        actor_role = getattr(request.state, "actor_role", None)

        # Try to get actor info from the user if auth has been processed
        if actor_id is None:
            user = getattr(request.state, "user", None)
            if user is not None:
                actor_id = getattr(user, "id", None)
                actor_role = getattr(user, "role", None)

        # Extract IP address
        ip_address = None
        if request.client:
            ip_address = request.client.host

        # Determine resource from path
        resource_type = None
        resource_id = None
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 3:
            # /api/v1/{resource_type}/...
            resource_type = path_parts[2] if len(path_parts) > 2 else None

        # Use SQLite-aware schema mapping
        engine = get_engine()
        is_sqlite = "sqlite" in str(engine.url)

        if is_sqlite:
            schema_map = {"tenant": None, "shared": None}
        else:
            tenant_schema = getattr(request.state, "tenant_schema", None)
            schema_map = {"tenant": tenant_schema} if tenant_schema else {"tenant": None, "shared": None}

        async with engine.begin() as conn:
            conn = await conn.execution_options(schema_translate_map=schema_map)
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                from app.services.audit_service import AuditService

                svc = AuditService(session)
                await svc.log_action(
                    action=action,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip_address,
                    request_id=request_id,
                    details={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                    },
                )
                await session.flush()
