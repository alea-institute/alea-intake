"""Public showcase ownership and bounded admission."""
import asyncio
import json
from weakref import WeakValueDictionary
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
from app.db.retention import touch_guest
from app.models.intake import Intake, IntakeSession, IntakeParty
from app.models.user import User


# The deployment runs one uvicorn worker. Multiple workers would require a
# distributed lock shared by sockets, HTTP work, and the retention sweeper.
_guest_locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()
_guest_tasks: dict[int, set[asyncio.Task]] = {}
_erasing_guests: set[int] = set()


def guest_lock(user_id: int) -> asyncio.Lock:
    lock = _guest_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _guest_locks[user_id] = lock
    return lock


@asynccontextmanager
async def guest_task(user_id: int, *, erase: bool = False):
    """Track work, including lock waiters, and prevent new work during erase."""
    if user_id in _erasing_guests:
        raise HTTPException(409, "Session is being erased; retry later")
    task = asyncio.current_task()
    tasks = _guest_tasks.setdefault(user_id, set())
    tasks.add(task)
    if erase:
        _erasing_guests.add(user_id)
    try:
        if erase:
            others = tasks - {task}
            for other in others:
                other.cancel()
            if others:
                # wait_for would wait indefinitely if work suppresses cancellation.
                _, pending = await asyncio.wait(others, timeout=10)
                if pending:
                    raise HTTPException(503, "Work is still stopping; retry erase")
        yield
    finally:
        tasks.discard(task)
        if not tasks:
            _guest_tasks.pop(user_id, None)
        if erase:
            _erasing_guests.discard(user_id)


async def _check_identifiers(request, db, user):
    from app.models.analysis import AnalysisRun
    from app.models.output import OutputDocument

    models = {"intake_id": Intake, "session_id": IntakeSession,
              "document_id": OutputDocument, "run_id": AnalysisRun, "party_id": IntakeParty}
    # Keep sources and duplicate query/form fields separate: no identifier may
    # overwrite another before its ownership has been checked.
    supplied = list(request.path_params.items()) + list(request.query_params.multi_items())
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        content_type = request.headers.get("content-type", "").split(';')[0].strip().lower()
        if content_type == "application/json" or (
            content_type.startswith("application/") and content_type.endswith("+json")
        ):
            try:
                raw_body = await request.body()
                body = json.loads(raw_body) if raw_body else {}
            except (ValueError, json.JSONDecodeError):
                raise HTTPException(422, "Expected a JSON object") from None
            if not isinstance(body, dict):
                raise HTTPException(422, "Expected a JSON object")
            supplied.extend(body.items())
        elif content_type in {"multipart/form-data", "application/x-www-form-urlencoded"}:
            supplied.extend((await request.form()).multi_items())
        elif await request.body():
            raise HTTPException(415, "Unsupported media type")
    intake_ids = set()
    for name, value in supplied:
        if name not in models or value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise HTTPException(422, "Resource identifiers must be integers")
        try:
            identifier = int(value)
        except (ValueError, TypeError):
            raise HTTPException(422, "Resource identifiers must be integers") from None
        resource = await db.get(models[name], identifier)
        if resource is None:
            raise HTTPException(404, "Intake not found")
        intake_ids.add(resource.id if name == "intake_id" else resource.intake_id)
    if intake_ids:
        if len(intake_ids) != 1:
            raise HTTPException(404, "Intake not found")
        await require_owner(db, user, intake_id=intake_ids.pop())


def client_ip(conn):
    return conn.client.host if conn.client else "unknown"


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
    erase = request.method == "POST" and request.url.path.endswith("/end-session")
    # Cancel and await prior work before acquiring its lock or touching rows.
    async with guest_task(user.id, erase=erase), guest_lock(user.id):
        try:
            if not await touch_guest(db, user.id):
                raise HTTPException(404, "Session unavailable")
            await _check_identifiers(request, db, user)
            if request.method != "GET" and not erase:
                admit(request.app, user.id, client_ip(request))
            from app.db.retention import guest_activity
            async with guest_activity(user.id):
                if request.url.path.endswith(("/analyze", "/override")):
                    async with analysis_slot(request.app):
                        yield
                else:
                    yield
                await touch_guest(db, user.id)
                # Finish writes (including erase) before releasing the guest lock.
                await db.commit()
        except BaseException:
            # CancelledError is not an Exception. Roll back before erase can
            # acquire the guest lock and purge this transaction's graph.
            await db.rollback()
            raise


class ShowcaseBodyLimit:
    """Bound actual streamed bytes before multipart parsing or route work."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        settings = config.get_settings()
        if scope["type"] != "http" or not settings.showcase_mode:
            return await self.app(scope, receive, send)
        # FastAPI parses form parameters before dependencies run. Normalize the
        # media type here too, preserving case-sensitive multipart boundaries.
        scope = dict(scope)
        scope["headers"] = [
            (name, value.split(b';', 1)[0].strip().lower()
             + (b';' + value.split(b';', 1)[1] if b';' in value else b''))
            if name.lower() == b'content-type' else (name, value)
            for name, value in scope.get("headers", [])
        ]
        from starlette.datastructures import Headers
        try:
            content_length = int(Headers(scope=scope).get("content-length", "0"))
        except ValueError:
            content_length = 0
        if content_length > settings.showcase_max_body_bytes:
            return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
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
