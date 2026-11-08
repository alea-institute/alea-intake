"""Public showcase ownership and bounded admission."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app import config
from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.models.intake import Intake, IntakeSession, IntakeParty
from app.models.user import User


async def require_owner(db, user, *, intake_id=None, session_id=None):
    """Resolve both identifiers and reject cross-intake session combinations."""
    if session_id is not None:
        session = await db.get(IntakeSession, int(session_id))
        if session is None or (intake_id is not None and session.intake_id != int(intake_id)):
            raise HTTPException(404, "Intake not found")
        intake_id = session.intake_id
    intake = await db.get(Intake, int(intake_id)) if intake_id is not None else None
    if intake is None or intake.created_by_user_id != user.id or intake.org_id != user.org_id:
        raise HTTPException(404, "Intake not found")
    from datetime import datetime, timezone
    intake.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return intake


def admit(app, user_id, ip):
    settings = config.get_settings()
    if not hasattr(app.state, "showcase_limiter"):
        existing = getattr(app.state, "limiter", None)
        app.state.showcase_limiter = FixedWindowRateLimiter(existing._storage if existing else MemoryStorage())
    limiter = app.state.showcase_limiter
    for category, identity, limit in (("ip", ip, settings.showcase_ip_limit),
                                       ("guest", user_id, settings.showcase_guest_limit)):
        if identity is not None and not limiter.hit(parse(limit), "showcase", category, str(identity)):
            raise HTTPException(429, "Admission limit reached; retry later", headers={"Retry-After": "60"})


@asynccontextmanager
async def analysis_slot(app):
    settings = config.get_settings()
    if not hasattr(app.state, "analysis_semaphore"):
        app.state.analysis_semaphore = asyncio.Semaphore(settings.showcase_concurrent_analyses)
        app.state.analysis_admitted = 0
    if app.state.analysis_admitted >= settings.showcase_concurrent_analyses + settings.showcase_analysis_queue:
        raise HTTPException(429, "Analysis queue full; retry later", headers={"Retry-After": "5"})
    app.state.analysis_admitted += 1
    try:
        async with app.state.analysis_semaphore:
            yield
    finally:
        app.state.analysis_admitted -= 1


async def showcase_access(request: Request, user: User = Depends(get_current_active_user),
                          db: AsyncSession = Depends(get_tenant_session)):
    """One dependency covers every mounted showcase resource interface."""
    if not config.get_settings().showcase_mode:
        yield
        return
    from datetime import datetime, timezone
    from sqlalchemy import update
    # Serialize active request work with the sweeper's guest-row lock.
    touched = await db.execute(update(User).where(User.id == user.id).values(updated_at=datetime.now(timezone.utc)))
    if not touched.rowcount:
        raise HTTPException(404, "Session unavailable")
    data = dict(request.query_params)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if "application/json" in request.headers.get("content-type", ""):
            data.update(await request.json())
        elif "multipart/form-data" in request.headers.get("content-type", ""):
            data.update(await request.form())
    data.update(request.path_params)
    intake_id, session_id = data.get("intake_id"), data.get("session_id")
    if "document_id" in data:
        from app.models.output import OutputDocument
        document = await db.get(OutputDocument, int(data["document_id"]))
        if document is None:
            raise HTTPException(404, "Document not found")
        intake_id = document.intake_id
    if intake_id is not None or session_id is not None:
        intake = await require_owner(db, user, intake_id=intake_id, session_id=session_id)
        if data.get("run_id") is not None:
            from app.models.analysis import AnalysisRun
            run = await db.get(AnalysisRun, int(data["run_id"]))
            if run is None or run.intake_id != intake.id:
                raise HTTPException(404, "Analysis not found")
        if data.get("party_id") is not None:
            party = await db.get(IntakeParty, int(data["party_id"]))
            if party is None or party.intake_id != intake.id:
                raise HTTPException(404, "Party not found")
    if request.method != "GET":
        admit(request.app, user.id, request.client.host if request.client else "unknown")
    from app.db.retention import guest_activity
    async with guest_activity(user.id):
        try:
            if request.url.path.endswith(("/analyze", "/override")):
                async with analysis_slot(request.app):
                    yield
            else:
                yield
        finally:
            await db.execute(update(User).where(User.id == user.id).values(updated_at=datetime.now(timezone.utc)))


class ShowcaseBodyLimit:
    """Bound actual streamed bytes before multipart parsing or route work."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        settings = config.get_settings()
        if scope["type"] != "http" or not settings.showcase_mode:
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > settings.showcase_max_body_bytes:
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        iterator = iter(chunks)
        async def replay():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()
        await self.app(scope, replay, send)


class ShowcasePrivacy:
    """Keep request bodies and exception text out of showcase error reports."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not config.get_settings().showcase_mode:
            return await self.app(scope, receive, send)
        started = False
        error_response = False
        async def safe_send(message):
            nonlocal started, error_response
            if message['type'] == 'http.response.start':
                started = True
                error_response = message['status'] >= 400
                if error_response:
                    # Framework validation errors include rejected body values.
                    message = dict(message)
                    message['headers'] = [(k, v) for k, v in message.get('headers', [])
                                          if k.lower() not in (b'content-length', b'content-type')]
                    message['headers'].append((b'content-type', b'application/json'))
            if message['type'] == 'http.response.body' and error_response:
                if message.get('more_body', False):
                    return
                message = {'type': 'http.response.body', 'body': b'{"detail":"Request failed; retry or start a new session"}'}
            await send(message)
        try:
            await self.app(scope, receive, safe_send)
        except Exception:
            # Do not forward the exception to server logs or report request data.
            if not started:
                await JSONResponse({'detail': 'Internal server error'}, status_code=500)(scope, receive, send)
