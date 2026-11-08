"""Guest retention and observability privacy contracts."""
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from tests.test_showcase_mode import showcase, guest
from app.db.retention import sweep_showcase_sessions


@pytest.fixture
async def retention(showcase, monkeypatch, tmp_path):
    from app.db.engine import get_engine
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import MetaData
    from app.db.base import TenantBase, SharedBase
    import app.models.audio, app.models.document
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
    from app.services.document.document_service import DocumentService
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
