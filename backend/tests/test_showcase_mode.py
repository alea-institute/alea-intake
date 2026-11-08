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
