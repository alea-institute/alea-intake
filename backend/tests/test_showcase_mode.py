"""Guest isolation and resource bounds for the public showcase."""
import asyncio
import io
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute, APIWebSocketRoute
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
async def showcase(async_client, monkeypatch):
    import app.config as config
    from app.main import mount_routers
    from app.middleware.consent import ConsentMiddleware
    from app.showcase import ShowcaseBodyLimit
    settings = config.get_settings().model_copy(update={
        "showcase_mode": True, "showcase_ws_auth_timeout": 0.5,
        "showcase_upload_max_bytes": 1000, "showcase_pdf_max_pages": 1,
    })
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr("app.routers.intake.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.document.document_service.get_settings", lambda: settings)
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    mount_routers(app, settings)
    app.add_middleware(ConsentMiddleware)
    app.add_middleware(ShowcaseBodyLimit)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, settings, app


async def guest(client, consent=True):
    response = await client.post("/api/v1/auth/guest", json={"consent": consent})
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def test_guest_consent_and_notice(showcase):
    client, _, _ = showcase
    notice = await client.get("/api/v1/auth/showcase-notice")
    assert "not legal advice" in notice.json()["disclaimer"]
    headers = await guest(client, False)
    assert (await client.post("/api/v1/intake/", headers=headers, json={})).status_code == 403
    headers = await guest(client)
    assert (await client.post("/api/v1/intake/", headers=headers, json={})).status_code == 201


@pytest.mark.parametrize("path", ["admin", "auth/oauth/google", "cms", "autonomy", "organizations"])
async def test_hidden_routes(showcase, path):
    assert (await showcase[0].get("/api/v1/" + path)).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("POST", "query"), ("POST", "verify"),
    ("GET", "tools"), ("POST", "tools"),
])
async def test_research_routes_are_not_mounted(showcase, method, path):
    client, _, _ = showcase
    headers = await guest(client)
    response = await client.request(method, "/api/v1/research/" + path, headers=headers)
    assert response.status_code == 404, response.text


async def test_showcase_route_ownership_coverage(showcase):
    from app.routers.intake import websocket_access
    from app.showcase import showcase_access

    allowed_parameters = {"intake_id", "session_id", "document_id", "run_id", "party_id", "format"}
    for route in showcase[2].routes:
        for parameter in route.param_convertors:
            assert parameter in allowed_parameters, (
                f"Route {route.path} parameter {parameter} has no ownership handling"
            )
        if route.path.startswith("/api/v1/auth/") or route.path == "/health":
            continue
        assert isinstance(route, (APIRoute, APIWebSocketRoute)), (
            f"Route {route.path} has no ownership dependency"
        )
        ownership_dependency = (websocket_access if isinstance(route, APIWebSocketRoute)
                                else showcase_access)
        assert any(dependency.call is ownership_dependency
                   for dependency in route.dependant.dependencies), (
            f"Route {route.path} has no ownership dependency"
        )


async def test_other_guest_cannot_access_intake(showcase):
    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    assert owner != other
    created = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    intake, session = created["id"], created["session_id"]
    for path in [f"intake/{intake}/messages?session_id={session}", *[
        f"analysis/{intake}/{suffix}" for suffix in ("results", "audit", "visualization", "status")]]:
        assert (await client.get("/api/v1/" + path, headers=other)).status_code == 404, path
    for path in (f"analysis/{intake}/analyze", f"intake/{intake}/end-session"):
        assert (await client.post("/api/v1/" + path, headers=other)).status_code == 404
    assert (await client.get("/api/v1/intake/", headers=other)).json() == []
    assert (await client.get(f"/api/v1/intake/{intake}/messages?session_id={session}", headers=owner)).status_code == 200
    own = (await client.post("/api/v1/intake/", headers=other, json={})).json()
    assert (await client.get(f'/api/v1/intake/{own["id"]}/messages?session_id={session}', headers=other)).status_code == 404
    assert (await client.post("/api/v1/output/generate", headers=other, json={"intake_id": intake, "run_id": 1})).status_code == 404


async def test_output_export_is_owned(showcase):
    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    intake = (await client.post("/api/v1/intake/", headers=owner, json={})).json()["id"]
    from app.db.engine import get_engine
    from app.models.output import OutputDocument
    from sqlalchemy.ext.asyncio import AsyncSession
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            doc = OutputDocument(run_id=1, intake_id=intake, profile_type="law_firm", markdown_content="Private example")
            db.add(doc)
            await db.commit()
            document_id = doc.id
    for path in (f"/api/v1/output/{document_id}", f"/api/v1/output/{document_id}/export/json",
                 f"/api/v1/output/intake/{intake}"):
        assert (await client.get(path, headers=other)).status_code == 404
    assert (await client.get(f"/api/v1/output/{document_id}", headers=owner)).status_code == 200


async def test_websocket_auth_boundaries(showcase):
    client, _, app = showcase
    owner, other = await guest(client), await guest(client)
    created = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    path = f'/api/ws/intake/{created["session_id"]}'
    with TestClient(app) as sync:
        with sync.websocket_connect(path) as ws:
            ws.send_json({"type": "auth", "token": other["Authorization"][7:]})
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
            assert exc.value.code == 4003
        for url in (path, path + "?token=" + owner["Authorization"][7:]):
            with sync.websocket_connect(url) as ws:
                with pytest.raises(WebSocketDisconnect) as exc:
                    ws.receive_json()
                assert exc.value.code == 4001


async def test_upload_caps_before_extraction(showcase, monkeypatch):
    client, _, _ = showcase
    from app.routers.intake import DocumentService
    extract = AsyncMock(side_effect=AssertionError("extraction must not start"))
    monkeypatch.setattr(DocumentService, "process_document", extract)
    headers = await guest(client)
    headers["X-LLM-API-Key"] = "test-visitor-key"
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    pdf = io.BytesIO(b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Count 2 /Kids [3 0 R 4 0 R] >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >> endobj\n"
        b"4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >> endobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF")
    settings = showcase[1]
    settings.showcase_upload_max_bytes = 10000
    for content, mime in ((b"x" * 10001, "application/pdf"), (pdf.getvalue(), "application/pdf")):
        response = await client.post(f'/api/v1/intake/{created["id"]}/document', headers=headers,
            data={"session_id": created["session_id"]}, files={"file": ("input.pdf", content, mime)})
        assert response.status_code == 413, response.text
    extract.assert_not_called()


async def test_body_and_admission_limits(showcase, monkeypatch):
    client, settings, _ = showcase
    headers = await guest(client)
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    settings.showcase_max_body_bytes = 10
    assert (await client.post("/api/v1/intake/", headers=headers, content=b"x" * 11)).status_code == 413
    settings.showcase_max_body_bytes = 10000
    call = AsyncMock(side_effect=AssertionError("LLM must not run"))
    monkeypatch.setattr("app.services.llm_service.LLMService.acomplete", call)
    for field in ("showcase_guest_limit", "showcase_ip_limit"):
        setattr(settings, field, "0/minute")
        response = await client.post(f'/api/v1/analysis/{created["id"]}/analyze', headers=headers)
        assert response.status_code == 429, response.text
        setattr(settings, field, "1000/minute")
    call.assert_not_called()


async def test_analysis_queue_is_bounded(showcase):
    _, settings, app = showcase
    from app.showcase import analysis_slot
    settings.showcase_concurrent_analyses = 1
    settings.showcase_analysis_queue = 1
    entered, release = asyncio.Event(), asyncio.Event()
    async def hold():
        async with analysis_slot(app):
            entered.set()
            await release.wait()
    first = asyncio.create_task(hold())
    await entered.wait()
    second = asyncio.create_task(hold())
    await asyncio.sleep(0)
    with pytest.raises(HTTPException) as exc:
        async with analysis_slot(app):
            pytest.fail("overfull queue admitted")
    assert exc.value.status_code == 429
    assert "retry" in exc.value.detail.lower()
    release.set()
    await asyncio.gather(first, second)


async def test_pdf_worker_has_a_hard_deadline(showcase, tmp_path):
    from app.services.document.bounded import run_document_worker
    path = tmp_path / "input.pdf"
    path.write_bytes(b"%PDF-1.4")
    showcase[1].showcase_extraction_timeout_seconds = 0.000001
    with pytest.raises(TimeoutError):
        await run_document_worker("pdf", path=path)


@pytest.mark.parametrize('reference', ['gpt-4o-mini', 'candidate-model'])
async def test_notice_and_llm_share_reference_model(monkeypatch, reference):
    from app.config import Settings
    import logging.handlers
    monkeypatch.setattr(logging.handlers, "RotatingFileHandler", lambda *a, **kw: logging.NullHandler())
    from app.services.llm_service import LLMService
    assert Settings.model_fields['reference_model'].default == 'gpt-4o-mini'
    import app.config as config
    from app.routers.auth import guest_router
    settings = Settings(secret_key="test-only", reference_model=reference, _env_file=None)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(guest_router)
    monkeypatch.setenv("ALEA_REFERENCE_MODEL", reference)
    monkeypatch.delenv('ALEA_LLM_MODEL', raising=False)
    monkeypatch.delenv('ALEA_LLM_PROVIDER', raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/api/v1/auth/showcase-notice')).json()['reference_model'] == reference
    service = LLMService(api_key='test-only')
    assert service.model == reference
    assert service.is_reference_model


async def test_showcase_websocket_chat_reply(showcase, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.services import llm_service
    from app.routers import intake

    client, _, app = showcase
    owner = await guest(client)
    created = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    factory = MagicMock(return_value=SimpleNamespace(
        chat_async=AsyncMock(return_value=SimpleNamespace(text="When did your employer fire you?"))))
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)

    def surface_socket_error(message, session_id, error):
        raise error

    monkeypatch.setattr(intake.logger, "error", surface_socket_error)
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({"type": "auth", "token": owner["Authorization"][7:],
                          "llm_api_key": "chat-visitor-key"})
            assert ws.receive_json()["type"] == "session_state"
            ws.send_json({"type": "text_message", "content": "My employer fired me.",
                          "client_id": "first-message"})
            messages = []
            while not messages or messages[-1]["type"] != "system_message":
                messages.append(ws.receive_json())
            assert any(message["type"] == "message_ack" for message in messages)
            assert messages[-1]["content"] == "When did your employer fire you?"
    assert factory.call_args.kwargs["api_key"] == "chat-visitor-key"


async def test_oversized_content_length_rejected_before_reading(showcase):
    from app.showcase import ShowcaseBodyLimit

    receive = AsyncMock(side_effect=AssertionError("body must not be read"))
    send = AsyncMock()
    downstream = AsyncMock()
    await ShowcaseBodyLimit(downstream)(
        {"type": "http", "method": "POST", "path": "/", "headers": [
            (b"content-length", str(showcase[1].showcase_max_body_bytes + 1).encode())]},
        receive, send)
    assert send.await_args_list[0].args[0]["status"] == 413
    receive.assert_not_called()
    downstream.assert_not_called()


async def _seed_output(intake_id):
    from app.db.engine import get_engine
    from app.models.output import OutputDocument
    from app.models.analysis import AnalysisRun
    from sqlalchemy.ext.asyncio import AsyncSession

    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            run = AnalysisRun(intake_id=intake_id, trigger_type="manual", status="completed")
            db.add(run)
            await db.flush()
            document = OutputDocument(run_id=run.id, intake_id=intake_id, profile_type="law_firm",
                                      markdown_content="private")
            db.add(document)
            await db.commit()
            return document.id


@pytest.mark.parametrize("source", ["query", "body", "duplicate_query", "body_intake"])
async def test_identifier_sources_cannot_replace_ownership(showcase, source):
    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    own = (await client.post("/api/v1/intake/", headers=other, json={})).json()
    await _seed_output(victim["id"])
    document = await _seed_output(own["id"])
    assert (await client.get(f'/api/v1/analysis/{victim["id"]}/results', headers=owner)).status_code == 200
    if source == "query":
        response = await client.get(f'/api/v1/analysis/{victim["id"]}/results',
                                    params={"document_id": document}, headers=other)
    elif source == "body":
        response = await client.post(f'/api/v1/analysis/{victim["id"]}/analyze',
                                     json={"document_id": document}, headers=other)
    elif source == "body_intake":
        response = await client.post(f'/api/v1/analysis/{own["id"]}/analyze',
                                     json={"intake_id": victim["id"]}, headers=other)
    else:
        response = await client.get(f'/api/v1/analysis/{own["id"]}/results',
                                    params=[("document_id", 999999), ("document_id", document)],
                                    headers=other)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("identifier", ["intake_id", "session_id", "document_id", "run_id", "party_id"])
async def test_invalid_resource_identifier_is_422(showcase, identifier):
    client, _, _ = showcase
    headers = await guest(client)
    response = await client.get("/api/v1/intake/", params={identifier: "invalid"}, headers=headers)
    assert response.status_code == 422


@pytest.mark.parametrize("body", [[], "text", None, 42])
async def test_non_object_body_is_422(showcase, body):
    import json
    client, _, _ = showcase
    headers = await guest(client)
    response = await client.post("/api/v1/intake/", content=json.dumps(body),
                                 headers={**headers, "Content-Type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("query_token", [False, True])
async def test_standard_socket_without_llm_key_stores_and_screens_message_then_errors(showcase, monkeypatch, query_token):
    from app.db.engine import get_engine
    from app.models.intake import Message
    from sqlalchemy import select

    client, settings, app = showcase
    headers = await guest(client)
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    settings.showcase_mode = False
    screen = AsyncMock(return_value=None)
    monkeypatch.setattr("app.routers.intake.screen_message_fast", screen)
    path = f'/api/ws/intake/{created["session_id"]}'
    if query_token:
        path += "?token=" + headers["Authorization"][7:]
    with TestClient(app) as sync:
        with sync.websocket_connect(path) as ws:
            if not query_token:
                ws.send_json({"type": "auth", "token": headers["Authorization"][7:]})
            assert ws.receive_json()["type"] == "session_state"
            ws.send_json({"type": "text_message", "content": "My wages are unpaid."})
            assert ws.receive_json()["type"] == "message_ack"
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["status"] == 400
    assert screen.await_args.args[:2] == ("My wages are unpaid.", created["session_id"])
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None})
        rows = (await conn.execute(select(Message.content_encrypted).where(
            Message.session_id == created["session_id"], Message.sender_type == "consumer"))).scalars().all()
        assert b"My wages are unpaid." in rows


async def _seed_transcript(session_id, intake_id):
    from app.db.engine import get_engine
    from app.models.audio import AudioRecording, Transcript
    from app.services.intake.session_service import IntakeSessionService
    from sqlalchemy.ext.asyncio import AsyncSession

    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            message = await IntakeSessionService(db).store_message(
                session_id=session_id, sender_type="consumer", modality="voice", content="original")
            recording = AudioRecording(message_id=message.id, intake_id=intake_id, original_format="wav")
            db.add(recording)
            await db.flush()
            transcript = Transcript(recording_id=recording.id, text_encrypted=b"private transcript",
                                    asr_provider="test")
            db.add(transcript)
            await db.commit()
            return recording.id


@pytest.mark.parametrize("message_type", ["transcript_approve", "transcript_edit"])
async def test_socket_cannot_change_other_guests_transcript(showcase, monkeypatch, message_type):
    from app.db.engine import get_engine
    from app.models.audio import Transcript
    from sqlalchemy import select

    client, _, app = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    own = (await client.post("/api/v1/intake/", headers=other, json={})).json()
    recording_id = await _seed_transcript(victim["session_id"], victim["id"])
    monkeypatch.setattr("app.routers.intake.llm_service_from_headers", lambda headers: object())
    monkeypatch.setattr("app.routers.intake.ConversationService.generate_response", AsyncMock(return_value="reply"))
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{own["session_id"]}') as ws:
            ws.send_json({"type": "auth", "token": other["Authorization"][7:], "llm_api_key": "test"})
            assert ws.receive_json()["type"] == "session_state"
            ws.send_json({"type": message_type, "recording_id": recording_id, "edited_text": "tampered"})
            assert ws.receive_json()["type"] == "error"
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None})
        row = (await conn.execute(select(Transcript.status, Transcript.text_encrypted).where(
            Transcript.recording_id == recording_id))).one()
        assert row == ("pending_review", b"private transcript")


async def test_garbage_pdf_returns_422(showcase):
    client, _, _ = showcase
    headers = await guest(client)
    headers["X-LLM-API-Key"] = "test-visitor-key"
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    response = await client.post(f'/api/v1/intake/{created["id"]}/document', headers=headers,
        data={"session_id": created["session_id"]},
        files={"file": ("garbage.pdf", b"garbage bytes", "application/pdf")})
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "PDF could not be read"


@pytest.mark.parametrize("identifier", ["intake_id", "session_id", "document_id", "run_id", "party_id"])
async def test_each_identifier_requires_ownership_without_path_intake(showcase, identifier):
    from app.db.engine import get_engine
    from app.models.analysis import AnalysisRun
    from app.models.intake import IntakeParty
    from sqlalchemy.ext.asyncio import AsyncSession

    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post("/api/v1/intake/", headers=owner, json={})).json()
    ids = {"intake_id": victim["id"], "session_id": victim["session_id"]}
    ids["document_id"] = await _seed_output(victim["id"])
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            run = AnalysisRun(intake_id=victim["id"], trigger_type="manual")
            party = IntakeParty(intake_id=victim["id"])
            db.add_all([run, party])
            await db.commit()
            ids.update(run_id=run.id, party_id=party.id)
    response = await client.get("/api/v1/intake/", params={identifier: ids[identifier]}, headers=other)
    assert response.status_code == 404


@pytest.mark.parametrize("message_type", ["transcript_approve", "transcript_edit"])
async def test_standard_transcript_without_key_is_stored_and_screened_then_errors(showcase, monkeypatch, message_type):
    from app.db.engine import get_engine
    from app.models.audio import Transcript
    from sqlalchemy import select

    client, settings, app = showcase
    headers = await guest(client)
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    recording_id = await _seed_transcript(created["session_id"], created["id"])
    settings.showcase_mode = False
    screen = AsyncMock(return_value=None)
    monkeypatch.setattr("app.routers.intake.screen_message_fast", screen)
    with TestClient(app) as sync:
        with sync.websocket_connect(f'/api/ws/intake/{created["session_id"]}') as ws:
            ws.send_json({"type": "auth", "token": headers["Authorization"][7:]})
            assert ws.receive_json()["type"] == "session_state"
            ws.send_json({"type": message_type, "recording_id": recording_id, "edited_text": "corrected text"})
            assert ws.receive_json()["type"] == "message_ack"
            error = ws.receive_json()
            assert error["type"] == "error"
            assert error["status"] == 400
    expected_text = "corrected text" if message_type == "transcript_edit" else "private transcript"
    assert screen.await_args.args[:2] == (expected_text, created["session_id"])
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None})
        row = (await conn.execute(select(Transcript.status, Transcript.text_encrypted).where(
            Transcript.recording_id == recording_id))).one()
        assert row == ("edited" if message_type == "transcript_edit" else "approved", expected_text.encode())


@pytest.mark.parametrize("content_type", ["Application/JSON", "application/vnd.test+json",
                                         " Application/JSON ; charset=utf-8", "MULTIPART/FORM-DATA"])
@pytest.mark.parametrize("identifier", ["run_id", "intake_id", "session_id"])
async def test_json_media_types_enforce_foreign_identifiers(showcase, content_type, identifier):
    import json
    from app.db.engine import get_engine
    from app.models.output import OutputDocument
    from sqlalchemy import select

    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    document_id = await _seed_output(victim['id'])
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={'tenant': None})
        run_id = (await conn.execute(select(OutputDocument.run_id).where(
            OutputDocument.id == document_id))).scalar_one()
    ids = {'intake_id': victim['id'], 'session_id': victim['session_id'], 'run_id': run_id}
    # Output generation has no path identifier to rescue a missed body check.
    body = {'run_id': run_id, 'intake_id': victim['id']} if identifier == 'run_id' else {identifier: ids[identifier]}
    headers = {**other, 'X-LLM-API-Key': 'visitor-key'}
    if content_type == 'MULTIPART/FORM-DATA':
        request = client.build_request('POST', '/api/v1/output/generate', headers=headers,
                                       files=[(k, (None, str(v))) for k, v in body.items()])
        request.headers['Content-Type'] = request.headers['Content-Type'].replace(
            'multipart/form-data', content_type)
        response = await client.send(request)
    else:
        response = await client.post('/api/v1/output/generate', content=json.dumps(body),
                                    headers={**headers, 'Content-Type': content_type})
    assert response.status_code == 404, response.text


@pytest.mark.parametrize('duplicate', [False, True])
@pytest.mark.parametrize('content_type', ['multipart/form-data', 'MULTIPART/FORM-DATA'])
async def test_multipart_media_types_enforce_all_session_ids(showcase, monkeypatch, duplicate, content_type):
    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    own = (await client.post('/api/v1/intake/', headers=other, json={})).json()
    process = AsyncMock(side_effect=AssertionError('Foreign upload must not be processed'))
    monkeypatch.setattr('app.routers.intake.DocumentService.process_document', process)
    files = [('session_id', (None, str(victim['session_id'])))]
    if duplicate:
        files.append(('session_id', (None, str(own['session_id']))))
    files.append(('file', ('story.txt', b'private narrative', 'text/plain')))
    request = client.build_request('POST', f'/api/v1/intake/{own["id"]}/document',
                                   headers={**other, 'X-LLM-API-Key': 'visitor-key'}, files=files)
    request.headers['Content-Type'] = request.headers['Content-Type'].replace('multipart/form-data', content_type)
    response = await client.send(request)
    assert response.status_code == 404, response.text
    process.assert_not_called()


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
async def test_unknown_mutating_media_type_is_415(showcase, method):
    client, _, app = showcase
    from fastapi import Depends
    from app.showcase import showcase_access

    @app.api_route('/media-probe', methods=[method], dependencies=[Depends(showcase_access)])
    async def probe():
        return {'ok': True}

    headers = await guest(client)
    response = await client.request(method, '/media-probe', content=b'intake_id=1',
                                    headers={**headers, 'Content-Type': 'text/plain'})
    assert response.status_code == 415


@pytest.mark.parametrize('content_type', ['application/json', 'Application/JSON', 'application/vnd.test+json'])
async def test_empty_json_is_allowed_and_malformed_json_is_422(showcase, content_type):
    client, _, _ = showcase
    headers = {**await guest(client), 'Content-Type': content_type}
    assert (await client.post('/api/v1/intake/', headers=headers, content=b'')).status_code == 201
    assert (await client.post('/api/v1/intake/', headers=headers, content=b'{')).status_code == 422


async def test_urlencoded_form_checks_foreign_identifiers(showcase):
    client, _, _ = showcase
    owner, other = await guest(client), await guest(client)
    victim = (await client.post('/api/v1/intake/', headers=owner, json={})).json()
    response = await client.post('/api/v1/output/generate', headers=other,
                                 data={'intake_id': victim['id']})
    assert response.status_code == 404


async def test_two_owned_intakes_cannot_be_combined(showcase):
    client, _, _ = showcase
    headers = await guest(client)
    first = (await client.post('/api/v1/intake/', headers=headers, json={})).json()
    second = (await client.post('/api/v1/intake/', headers=headers, json={})).json()
    response = await client.get(f'/api/v1/intake/{first["id"]}/messages', headers=headers,
                                params={'session_id': second['session_id']})
    assert response.status_code == 404


