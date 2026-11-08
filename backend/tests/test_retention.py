"""Guest retention and observability privacy contracts."""
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import structlog
import app.models.audio  # noqa: F401 -- register before async_client creates tables
import app.models.document  # noqa: F401
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from tests.test_showcase_mode import showcase as showcase, guest  # noqa: F401,F811


@pytest.fixture(autouse=True)
def restore_logging_state():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    access = logging.getLogger("uvicorn.access")
    disabled = access.disabled
    loggers = [root, *(value for value in logging.Logger.manager.loggerDict.values()
                       if isinstance(value, logging.Logger))]
    formatters = {handler: handler.formatter for logger in loggers for handler in logger.handlers}
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    access.disabled = disabled
    for handler, formatter in formatters.items():
        handler.setFormatter(formatter)
    structlog.reset_defaults()


@pytest.fixture
async def retention(showcase, monkeypatch, tmp_path):
    from app.db.engine import get_engine
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import MetaData
    from app.db.base import TenantBase, SharedBase
    client, settings, app = showcase
    from app.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
    settings.intake_upload_dir = str(tmp_path / 'uploads')
    engine = get_engine()
    url = os.environ.get('TEST_POSTGRES_URL')
    if url:
        from uuid import uuid4
        from sqlalchemy import text
        schema = 'retention_test_' + uuid4().hex
        admin_engine = create_async_engine(url.replace('postgresql://', 'postgresql+asyncpg://', 1))
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url.replace('postgresql://', 'postgresql+asyncpg://', 1),
                                     connect_args={'server_settings': {'search_path': schema}})
        monkeypatch.setattr('app.db.engine._engine', engine)
        metadata = MetaData()
        for base in (SharedBase, TenantBase):
            for table in base.metadata.tables.values():
                table.to_metadata(metadata, schema=None)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
    yield client, settings, app, engine
    if url:
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


async def seed_graph(engine, intake_id, user_id):
    """Seed every graph table, independently of the purge's deletion list."""
    from app.db.base import TenantBase
    from sqlalchemy import Integer, Boolean, Float, LargeBinary, JSON, DateTime, Date
    links = dict(intake_id=intake_id, session_id=101, message_id=102, fact_id=103,
                 run_id=104, iteration_id=105, claim_id=106, element_id=107,
                 gap_id=108, document_id=109, recording_id=110, authority_id=111,
                 user_id=user_id, actor_id=user_id)
    ids = dict(intake_sessions=101, messages=102, extracted_facts=103, analysis_runs=104,
               analysis_iterations=105, analysis_claims=106, claim_elements=107,
               analysis_gaps=108, uploaded_documents=109, audio_recordings=110, authorities=111)
    tables = []
    async with engine.begin() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None, 'shared': None})
        for table in TenantBase.metadata.tables.values():
            if table.name in ('intakes', 'users', 'consent_records', 'refresh_tokens', 'kb_chunks'):
                continue
            if not (set(table.c.keys()) & set(links)):
                continue
            values = {'id': ids.get(table.name, 120)}
            for col in table.c:
                if col.name == 'id':
                    continue
                if col.name in links:
                    values[col.name] = links[col.name]
                elif not col.nullable and col.default is None and col.server_default is None:
                    typ = col.type
                    values[col.name] = (False if isinstance(typ, Boolean) else 1 if isinstance(typ, (Integer, Float))
                        else b'private narrative' if isinstance(typ, LargeBinary) else {} if isinstance(typ, JSON)
                        else datetime.now(timezone.utc) if isinstance(typ, DateTime)
                        else datetime.now().date() if isinstance(typ, Date) else 'private narrative')
            await conn.execute(table.insert().values(**values))
            tables.append(table)
    return tables


async def test_end_session_erases_full_graph_and_pdf(retention, monkeypatch):
    from app.models import Intake, User, ConsentRecord
    client, settings, _, engine = retention
    headers = await guest(client)
    created = (await client.post('/api/v1/intake/', headers=headers, json={})).json()
    intake_id = created['id']
    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        user_id = (await conn.execute(select(Intake.created_by_user_id).where(Intake.id == intake_id))).scalar_one()
    tables = await seed_graph(engine, intake_id, user_id)
    from unittest.mock import AsyncMock
    monkeypatch.setattr('app.services.intake.conversation.ConversationService.generate_response',
                        AsyncMock(return_value='Document received'))
    headers['X-LLM-API-Key'] = 'test-visitor-key'
    pdf = (b'%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n'
           b'2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n'
           b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >> endobj\n'
           b'trailer << /Root 1 0 R >>\n%%EOF')
    response = await client.post(f'/api/v1/intake/{intake_id}/document', headers=headers,
        data={'session_id': created['session_id']}, files={'file': ('input.pdf', pdf, 'application/pdf')})
    assert response.status_code == 201, response.text
    assert response.json()['extraction_status'] == 'completed'
    assert list(Path(settings.intake_upload_dir).rglob('*.pdf'))
    response = await client.post(f'/api/v1/intake/{intake_id}/end-session', headers=headers)
    assert response.status_code == 200, response.text
    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        for table in [*tables, Intake.__table__, User.__table__, ConsentRecord.__table__]:
            assert (await conn.execute(select(func.count()).select_from(table))).scalar_one() == 0, table.name
    assert not list(Path(settings.intake_upload_dir).iterdir())


async def test_idle_sweep_retries_interruption_and_preserves_active(retention, monkeypatch):
    from app.db.retention import sweep_showcase_sessions
    from app.models import Intake, User
    client, _, _, engine = retention
    old_headers, active_headers = await guest(client), await guest(client)
    old = (await client.post('/api/v1/intake/', headers=old_headers, json={})).json()['id']
    active = (await client.post('/api/v1/intake/', headers=active_headers, json={})).json()['id']
    async with engine.begin() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        await conn.execute(update(Intake).where(Intake.id == old).values(updated_at=datetime.now(timezone.utc)-timedelta(hours=2)))
        await conn.execute(update(User).where(User.id == select(Intake.created_by_user_id).where(Intake.id == old).scalar_subquery()).values(updated_at=datetime.now(timezone.utc)-timedelta(hours=2)))
    original = AsyncSession.execute
    interrupted = False
    async def interrupt(self, statement, *args, **kwargs):
        nonlocal interrupted
        if getattr(statement, 'is_delete', False) and not interrupted:
            interrupted = True
            await original(self, statement, *args, **kwargs)
            raise RuntimeError('simulated interruption after delete')
        return await original(self, statement, *args, **kwargs)
    monkeypatch.setattr(AsyncSession, 'execute', interrupt)
    await sweep_showcase_sessions()
    assert interrupted
    monkeypatch.setattr(AsyncSession, 'execute', original)
    await sweep_showcase_sessions()
    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        assert (await conn.execute(select(Intake.id))).scalars().all() == [active]
    assert (await client.get('/api/v1/auth/showcase-notice')).json()['idle_ttl_seconds'] == 3600


async def test_observability_and_error_payload_scrub(retention):
    import structlog
    from app.observability.logging import setup_logging
    from app.observability.telemetry import RedactingSpanProcessor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    client, settings, app, _ = retention
    settings.preview_passphrase = 'preview-private-example'
    narrative, key, token = 'My employer stole my wages', 'sk-private-example-key', 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature'
    setup_logging()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.getLogger().handlers[0].formatter)
    logging.getLogger().addHandler(handler)
    try:
        structlog.get_logger().error('request failed', narrative=narrative, message=narrative, document_text=narrative, headers={'Authorization': token, 'Cookie': token, 'X-LLM-API-Key': key, 'X-Preview-Key': settings.preview_passphrase}, token=token)
        structlog.get_logger().warning('Health check: database down')
        structlog.get_logger().info('Preview configured', value=settings.preview_passphrase)
        logging.getLogger('uvicorn.access').info('GET /?token=%s&key=%s %s', token, key, narrative)
        logging.getLogger('proxy').info('GET /?token=%s&key=%s %s', token, key, narrative)
    finally:
        logging.getLogger().removeHandler(handler)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(RedactingSpanProcessor(SimpleSpanProcessor(exporter)))
    with provider.get_tracer('test').start_as_current_span('request') as span:
        span.set_attribute('message.content', narrative)
        span.add_event('exception', {'exception.message': narrative + key + token})
        span.set_attribute('http.url', 'https://test/?key=' + key + '&token=' + token)
    exported = exporter.get_finished_spans()[0]
    attrs = str(exported.attributes) + str([dict(e.attributes) for e in exported.events])
    @app.post('/force-error')
    async def force_error():
        raise RuntimeError(narrative + key + token)
    # The production privacy middleware returns a generic error response.
    from app.showcase import ShowcasePrivacy
    app.add_middleware(ShowcasePrivacy)
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as errors:
        response = await errors.post('/force-error', json={'narrative': narrative, 'key': key, 'token': token})
    assert response.status_code == 500
    for secret in (narrative, key, token, settings.preview_passphrase):
        assert secret not in stream.getvalue() + attrs + response.text
    assert 'Health check: database down' in stream.getvalue()
    assert '"level": "warning"' in stream.getvalue()
    assert 'request failed' in stream.getvalue()
    assert logging.getLogger('uvicorn.access').disabled
    provider.shutdown()


def test_redaction_keeps_operations_and_removes_visitor_fields(monkeypatch):
    from app import config
    from app.observability.redaction import scrub
    settings = config.Settings(_env_file=None, secret_key='app-signing-secret',
                               showcase_mode=True, preview_passphrase='shared-preview-secret')
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    result = scrub({'event': 'Health check: database down', 'level': 'warning',
                    'narrative': 'My employer stole my wages',
                    'message': 'My employer stole my wages', 'document_text': 'private document',
                    'headers': {'Authorization': 'Bearer guest-opaque', 'Cookie': 'session=opaque',
                                'X-LLM-API-Key': 'opaque-api-secret', 'X-Preview-Key': 'shared-preview-secret'},
                    'diagnostic': 'configured shared-preview-secret app-signing-secret'})
    assert result['event'] == 'Health check: database down'
    assert result['level'] == 'warning'
    import structlog
    from app.observability.logging import setup_logging
    setup_logging()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.getLogger().handlers[0].formatter)
    logging.getLogger().addHandler(handler)
    try:
        structlog.get_logger().warning('Health check: database down',
                                      narrative='My employer stole my wages',
                                      preview_passphrase=settings.preview_passphrase)
    finally:
        logging.getLogger().removeHandler(handler)
    assert 'Health check: database down' in stream.getvalue()
    assert '"level": "warning"' in stream.getvalue()
    assert 'My employer' not in stream.getvalue()
    assert settings.preview_passphrase not in stream.getvalue()
    for value in ('My employer', 'private document', 'guest-opaque', 'session=opaque',
                  'opaque-api-secret', 'shared-preview-secret', 'app-signing-secret'):
        assert value not in str(result)


def test_preview_access_logging_omits_query_credentials(monkeypatch):
    from app import config
    from app.observability.logging import setup_logging
    settings = config.Settings(_env_file=None, secret_key='app-signing-secret',
                               showcase_mode=False, preview_passphrase='shared-preview-secret')
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    access = logging.getLogger('uvicorn.access')
    previous = access.disabled
    try:
        setup_logging()
        assert access.disabled
    finally:
        access.disabled = previous


async def test_fact_resolution_failure_never_logs_narrative(monkeypatch, caplog):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.extraction.schemas import ExtractionResultSchema

    from app.config import Settings
    monkeypatch.setattr("app.services.extraction.fact_extraction.get_settings",
                        lambda: Settings(_env_file=None, secret_key="test-key"))
    sentinel = "NARRATIVE_SENTINEL_employee_private_story"
    service = FactExtractionService(MagicMock(), MagicMock(flush=AsyncMock()),
                                    folio=MagicMock(), embedding_service=MagicMock())
    service.extract_facts = AsyncMock(return_value=ExtractionResultSchema(facts=[{
        "assertion": sentinel, "fact_type": "event", "entities": [], "confidence": 0.9,
        "source_start": 0, "source_end": len(sentinel),
    }], entities=[]))
    monkeypatch.setattr("app.services.extraction.fact_extraction.resolve_concepts",
                        AsyncMock(side_effect=ValueError(sentinel)))
    with caplog.at_level(logging.WARNING):
        await service.extract_and_persist(SimpleNamespace(text=sentinel), intake_id=1, message_id=2)
    assert "Concept resolution failed" in caplog.text
    assert sentinel not in caplog.text


def test_showcase_stdlib_bridge_keeps_only_event_template(monkeypatch):
    from app import config
    from app.observability.logging import setup_logging
    settings = config.Settings(_env_file=None, secret_key="test-key", showcase_mode=True)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    setup_logging()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.getLogger().handlers[0].formatter)
    logging.getLogger().addHandler(handler)
    sentinel = "NARRATIVE_SENTINEL_private_bridge_args"
    try:
        try:
            raise ValueError(sentinel)
        except ValueError:
            logging.getLogger("test.bridge").warning("Operation failed: %s", sentinel, exc_info=True,
                                                      extra={"guest_id": 17})
    finally:
        logging.getLogger().removeHandler(handler)
    assert "Operation failed: %s" in stream.getvalue()
    assert sentinel not in stream.getvalue()
    import json
    assert json.loads(stream.getvalue())["guest_id"] == 17


async def test_sweep_logs_failure_and_continues_other_guests(retention, monkeypatch, caplog):
    from app.db import retention as module
    from app.models import Intake, User
    client, _, _, engine = retention
    ids = []
    for _ in range(2):
        headers = await guest(client)
        ids.append((await client.post('/api/v1/intake/', headers=headers, json={})).json()['id'])
    stale = datetime.now(timezone.utc) - timedelta(hours=2)
    async with engine.begin() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        await conn.execute(update(Intake).values(updated_at=stale))
        await conn.execute(update(User).values(updated_at=stale))
        guest_id = (await conn.execute(select(Intake.created_by_user_id).where(Intake.id == ids[0]))).scalar_one()
    original = module.purge_intake
    async def purge(session, intake_id):
        if intake_id == ids[0]:
            raise OSError("simulated storage failure")
        await original(session, intake_id)
    monkeypatch.setattr(module, "purge_intake", purge)
    with caplog.at_level(logging.WARNING):
        await module.sweep_showcase_sessions()
    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        assert (await conn.execute(select(Intake.id))).scalars().all() == [ids[0]]
    record = next(r for r in caplog.records if 'purge interrupted' in r.getMessage())
    assert str(guest_id) in record.getMessage()
    assert record.exc_info is not None


async def test_erase_waits_for_inflight_socket_and_prevents_later_writes(retention, monkeypatch):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    from threading import Event
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.models.intake import Message

    client, _, app, engine = retention
    headers = await guest(client)
    created = (await client.post('/api/v1/intake/', headers=headers, json={})).json()
    release = asyncio.Event()
    reply_started = Event()
    async def slow_reply(*args, **kwargs):
        reply_started.set()
        await release.wait()
        return 'reply after waiting'
    # Release SQLite's database-wide writer lock before the slow provider call.
    # Otherwise SQLite itself serializes erase and hides the application race
    # that PostgreSQL's per-row locks allow.
    from app.services.intake.session_service import IntakeSessionService
    store_message = IntakeSessionService.store_message
    async def store_consumer_then_commit(self, *args, **kwargs):
        message = await store_message(self, *args, **kwargs)
        if kwargs.get("sender_type") == "consumer":
            await self._session.commit()
        return message
    monkeypatch.setattr(IntakeSessionService, "store_message", store_consumer_then_commit)
    monkeypatch.setattr('app.routers.intake.ConversationService.generate_response', slow_reply)
    monkeypatch.setattr('app.routers.intake.llm_service_from_headers', lambda headers: object())
    from unittest.mock import AsyncMock
    monkeypatch.setattr('app.routers.intake.screen_message_fast', AsyncMock(return_value=None))
    erase_entered = Event()
    async def observed_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"].endswith("/end-session"):
            erase_entered.set()
        await app(scope, receive, send)
    with TestClient(observed_app) as sync, ThreadPoolExecutor() as executor:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({'type': 'auth', 'token': headers['Authorization'][7:], 'llm_api_key': 'test'})
            assert ws.receive_json()['type'] == 'session_state'
            ws.send_json({'type': 'text_message', 'content': 'private text'})
            assert ws.receive_json()['type'] == 'message_ack'
            assert reply_started.wait(timeout=10)
            # Both requests run on TestClient's event loop, as in one uvicorn worker.
            erase = executor.submit(sync.post, f'/api/v1/intake/{created["id"]}/end-session', headers=headers)
            assert erase_entered.wait(timeout=10)
            try:
                with pytest.raises(FutureTimeoutError):
                    erase.result(timeout=1)
            finally:
                sync.portal.call(release.set)
            assert erase.result(timeout=10).status_code == 200
            assert ws.receive_json()['type'] == 'system_message'
            ws.send_json({'type': 'text_message', 'content': 'must not survive erase'})
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4004
    async with engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        assert (await conn.execute(select(func.count()).select_from(Message).where(
            Message.session_id == created['session_id']))).scalar_one() == 0


def test_graph_models_registered_before_database_setup():
    from app.db.base import TenantBase
    assert {'tenant.audio_recordings', 'tenant.transcripts', 'tenant.uploaded_documents',
            'tenant.document_extractions'} <= set(TenantBase.metadata.tables)
