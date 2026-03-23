"""Consent enforcement middleware -- blocks AI-processing endpoints without consent.

Checks active consent for any request to AI-processing prefixes. Returns 403
with appropriate error messages if consent is missing or has been revoked.

Skips enforcement for auth, admin, consent, health, and docs endpoints.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Endpoint prefixes that require active AI processing consent
AI_PROCESSING_PREFIXES = [
    "/api/v1/analysis",
    "/api/v1/intake",
    "/api/v1/research",
]


class ConsentMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces consent before allowing AI-processing requests.

    Checks if the user/session has active consent with ai_processing=True.
    Returns 403 with specific error messages:
    - "Consent required before AI processing can begin" (no consent)
    - "Consent has been revoked. AI processing is paused." (revoked consent)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"

        # Only enforce consent on AI processing endpoints
        requires_consent = any(
            path.startswith(prefix) for prefix in AI_PROCESSING_PREFIXES
        )

        if not requires_consent:
            return await call_next(request)

        # Check consent using a separate DB session
        try:
            has_consent = await self._check_consent(request)
        except Exception:
            # If consent check fails, block the request for safety
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Consent required before AI processing can begin"
                },
            )

        if has_consent is False:
            # Determine if consent was revoked or never granted
            was_revoked = await self._was_consent_revoked(request)
            if was_revoked:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Consent has been revoked. AI processing is paused."
                    },
                )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Consent required before AI processing can begin"
                },
            )

        return await call_next(request)

    async def _check_consent(self, request: Request) -> bool:
        """Check if the current user/session has active AI processing consent."""
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.db.engine import get_engine
        from app.services.consent_service import ConsentService

        # Extract user info from auth header
        user_id = await self._extract_user_id(request)
        session_id = request.headers.get("X-Session-ID")

        if user_id is None and session_id is None:
            return False

        engine = get_engine()
        is_sqlite = "sqlite" in str(engine.url)
        schema_map = (
            {"tenant": None, "shared": None}
            if is_sqlite
            else {
                "tenant": getattr(request.state, "tenant_schema", None),
                "shared": "shared",
            }
        )

        async with engine.connect() as conn:
            conn = await conn.execution_options(schema_translate_map=schema_map)
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                svc = ConsentService(session)
                return await svc.check_consent(
                    user_id=user_id, session_id=session_id
                )

    async def _was_consent_revoked(self, request: Request) -> bool:
        """Check if the user/session had consent that was revoked."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.db.engine import get_engine
        from app.models.consent import ConsentRecord

        user_id = await self._extract_user_id(request)
        session_id = request.headers.get("X-Session-ID")

        if user_id is None and session_id is None:
            return False

        engine = get_engine()
        is_sqlite = "sqlite" in str(engine.url)
        schema_map = (
            {"tenant": None, "shared": None}
            if is_sqlite
            else {
                "tenant": getattr(request.state, "tenant_schema", None),
                "shared": "shared",
            }
        )

        async with engine.connect() as conn:
            conn = await conn.execution_options(schema_translate_map=schema_map)
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                query = select(ConsentRecord).where(
                    ConsentRecord.revoked_at.isnot(None)
                )
                if user_id is not None:
                    query = query.where(ConsentRecord.user_id == user_id)
                elif session_id is not None:
                    query = query.where(ConsentRecord.session_id == session_id)

                result = await session.execute(query)
                return result.scalar_one_or_none() is not None

    async def _extract_user_id(self, request: Request) -> int | None:
        """Extract user_id from the Authorization header JWT."""
        import jwt as pyjwt

        from app.config import get_settings
        from app.core.security import decode_token

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1]
        settings = get_settings()

        try:
            payload = decode_token(token, settings.secret_key)
            return int(payload["sub"])
        except (pyjwt.InvalidTokenError, KeyError, ValueError):
            return None
