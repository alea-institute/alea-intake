"""Request credentials never fall back to deployment credentials."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.permissions import get_current_active_user
from app.db.session import get_tenant_session
from app.routers import analysis, intake, output
from app.services import llm_service


@pytest.mark.parametrize("provider", ["vllm", "unknown"])
def test_visitor_headers_reject_noncloud_providers(provider):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        llm_service.llm_service_from_headers({
            "X-LLM-API-Key": "visitor-key", "X-LLM-Provider": provider,
        })
    assert exc.value.status_code == 400
    assert exc.value.detail == "Unsupported LLM provider"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_visitor_headers_allow_cloud_providers(provider):
    service = llm_service.llm_service_from_headers({
        "X-LLM-API-Key": "visitor-key", "X-LLM-Provider": provider,
        "X-LLM-Model": "visitor-model",
    })
    assert (service.provider, service.model, service.api_key) == (provider, "visitor-model", "visitor-key")


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr("app.services.folio.folio_service.get_folio", lambda: None)
    monkeypatch.setattr(
        "app.services.analysis.trigger.AnalysisTrigger.manual_trigger",
        AsyncMock(return_value=SimpleNamespace(id=8, status="converged")),
    )
    monkeypatch.setattr("app.services.extraction.backfill.backfill_intake_facts", AsyncMock(return_value=0))
    monkeypatch.setattr(
        "app.services.analysis.stages.deadline_detect.DeadlineDetectStage.detect_and_persist",
        AsyncMock(return_value=[]),
    )
    app = FastAPI()
    for router in (analysis.router, intake.router, output.router):
        app.include_router(router)

    async def user():
        return SimpleNamespace(id=1)

    async def db():
        session = AsyncMock()
        session.execute.return_value = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []
        return session

    app.dependency_overrides[get_current_active_user] = user
    app.dependency_overrides[get_tenant_session] = db
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.parametrize(
    "path,kwargs",
    [
        ("/api/v1/analysis/1/analyze", {}),
        ("/api/v1/analysis/1/override", {}),
        ("/api/v1/output/generate", {"json": {"run_id": 1, "intake_id": 1}}),
        (
            "/api/v1/intake/1/document",
            {"data": {"session_id": "1"}, "files": {"file": ("story.txt", b"I was fired.", "text/plain")}},
        ),
    ],
)
async def test_missing_visitor_key_rejects_before_client(client, monkeypatch, path, kwargs):
    monkeypatch.setenv("ALEA_LLM_API_KEY", "server-alea")
    monkeypatch.setenv("OPENAI_API_KEY", "server-openai")
    factory = MagicMock(side_effect=AssertionError("client must not be constructed"))
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    response = await client.post(path, **kwargs)
    assert response.status_code == 400, response.text
    factory.assert_not_called()


async def test_request_keys_are_isolated_and_not_logged(client, monkeypatch, caplog):
    def build(*, api_key, model):
        reply = {"visitor-one": "First visitor reply", "visitor-two": "Second visitor reply"}[api_key]

        async def chat(*, messages):
            await asyncio.sleep(0)
            return SimpleNamespace(text=reply)

        return SimpleNamespace(chat_async=chat)

    factory = MagicMock(side_effect=build)
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    # Exercise the same dependency used by REST endpoints concurrently.
    from app.services.llm_service import get_request_llm_service

    app = client._transport.app
    from fastapi import Depends

    @app.post("/reply")
    async def reply(service=Depends(get_request_llm_service)):
        from app.services.intake.conversation import ConversationService

        return {
            "reply": await ConversationService(llm_service=service).generate_response(
                [{"role": "user", "content": "My employer fired me."}]
            )
        }

    results = await asyncio.gather(
        *[client.post("/reply", headers={"X-LLM-API-Key": key}) for key in ("visitor-one", "visitor-two")]
    )
    assert [r.json()["reply"] for r in results] == ["First visitor reply", "Second visitor reply"]
    assert [c.kwargs["api_key"] for c in factory.call_args_list] == ["visitor-one", "visitor-two"]
    assert "visitor-one" not in caplog.text and "visitor-two" not in caplog.text


async def test_nonreference_model_still_analyzes(client, monkeypatch):
    monkeypatch.setenv("ALEA_REFERENCE_MODEL", "reference-model")
    monkeypatch.setattr("app.services.folio.folio_service.get_folio", lambda: None)
    monkeypatch.setattr("app.services.extraction.backfill.backfill_intake_facts", AsyncMock(return_value=0))
    start = MagicMock()
    monkeypatch.setattr("app.services.analysis.background.start_analysis", start)
    response = await client.post(
        "/api/v1/analysis/1/analyze", headers={"X-LLM-API-Key": "visitor-key", "X-LLM-Model": "other-model"}
    )
    assert response.status_code == 202, response.text
    assert response.json()["is_reference_model"] is False
    assert response.json()["status"] == "running"
    start.assert_called_once()
    # The visitor's service (key + model) is what the background job runs with.
    assert start.call_args.args[2].model == "other-model"


async def test_visitor_key_reaches_structured_stages(monkeypatch, caplog):
    from app.services.analysis.stages.issue_spot import IssueSpotStage
    from app.services.analysis.stages.fact_map import FactMapStage
    from app.services.analysis.stages.deadline_detect import DeadlineDetectStage
    from app.services.extraction.fact_extraction import FactExtractionService
    from app.services.exploration.layers import _create_llm_model
    from app.services.llm_service import llm_service_from_headers

    factory = MagicMock(
        return_value=SimpleNamespace(
            json_async=AsyncMock(return_value=SimpleNamespace(data={"marker": "model output"}))
        )
    )
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    # Explore delegates model creation to the exploration layers.
    monkeypatch.setattr("alea_llm_client.OpenAIModel", factory)
    service = llm_service_from_headers({"X-LLM-API-Key": "stage-visitor-key", "X-LLM-Model": "chosen-model"})
    db = AsyncMock()
    calls = [
        IssueSpotStage(service, db)._call_llm([]),
        FactMapStage(service, db)._call_llm([], []),
        FactExtractionService(service, db)._call_llm_extraction("I was fired."),
        DeadlineDetectStage(service, db)._call_llm_extraction("I was fired yesterday."),
    ]
    for call in calls:
        assert await call == {"marker": "model output"}
    assert await _create_llm_model(service).json_async(messages=[]) == SimpleNamespace(data={"marker": "model output"})
    assert len(factory.call_args_list) == 5
    for call in factory.call_args_list:
        assert call.kwargs["api_key"] == "stage-visitor-key"
        assert call.kwargs["model"] == "chosen-model"
    assert "stage-visitor-key" not in caplog.text


@pytest.mark.parametrize(
    "handler", [intake._handle_text_message, intake._handle_transcript_approve, intake._handle_transcript_edit]
)
async def test_chat_without_key_does_not_construct_client(handler, async_engine, monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.audio import AudioRecording, Transcript
    from app.models.intake import Message
    from app.services.intake.session_service import IntakeSessionService

    content = "My employer fired me."
    data = {"content": content, "edited_text": "Corrected transcript"}
    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            svc = IntakeSessionService(db)
            record = await svc.create_intake(org_id=1, user_id=None)
            session = await svc.create_session(record.id)
            if handler != intake._handle_text_message:
                message = await svc.store_message(
                    session_id=session.id, sender_type="consumer", modality="voice", content=content
                )
                recording = AudioRecording(
                    message_id=message.id, intake_id=record.id, original_format="wav"
                )
                db.add(recording)
                await db.flush()
                db.add(Transcript(
                    recording_id=recording.id, text_encrypted=content.encode(), asr_provider="test"
                ))
                data["recording_id"] = recording.id
            await db.commit()

    websocket = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace()), headers={}, send_json=AsyncMock()
    )
    factory = MagicMock()
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    monkeypatch.setenv("ALEA_LLM_API_KEY", "server-key")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    screen = AsyncMock(return_value=None)
    monkeypatch.setattr(intake, "screen_message_fast", screen)
    await handler(websocket, session.id, 1, data, async_engine)
    frames = [call.args[0] for call in websocket.send_json.await_args_list]
    assert frames[-1] == {
        "type": "error", "status": 400, "message": "A visitor LLM API key is required"
    }
    assert not any(frame["type"] == "system_message" for frame in frames)
    factory.assert_not_called()
    expected_text = data["edited_text"] if handler == intake._handle_transcript_edit else content
    assert screen.await_args.args[:2] == (expected_text, session.id)
    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn) as db:
            rows = (await db.execute(select(Message).where(Message.session_id == session.id))).scalars().all()
            assert len(rows) == 1
            assert rows[0].sender_type == "consumer"
            assert rows[0].content_encrypted == content.encode()
            if handler != intake._handle_text_message:
                transcript = (await db.execute(select(Transcript).where(
                    Transcript.recording_id == data["recording_id"]
                ))).scalar_one()
                assert transcript.status == (
                    "edited" if handler == intake._handle_transcript_edit else "approved"
                )
                assert transcript.text_encrypted == expected_text.encode()


@pytest.mark.parametrize("handler", [
    intake._handle_text_message, intake._handle_transcript_approve, intake._handle_transcript_edit,
])
async def test_acknowledged_input_survives_llm_failure(handler, async_engine, monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.audio import AudioRecording, Transcript
    from app.models.intake import Message
    from app.models.screening import ScreeningEvent
    from app.services.intake.session_service import IntakeSessionService

    content = "My employer fired me."
    data = {"content": content, "edited_text": "Corrected transcript"}
    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            svc = IntakeSessionService(db)
            record = await svc.create_intake(org_id=1, user_id=None)
            session = await svc.create_session(record.id)
            if handler != intake._handle_text_message:
                message = await svc.store_message(session.id, "consumer", "voice", content)
                recording = AudioRecording(message_id=message.id, intake_id=record.id, original_format="wav")
                db.add(recording)
                await db.flush()
                db.add(Transcript(recording_id=recording.id, text_encrypted=content.encode(), asr_provider="test"))
                data["recording_id"] = recording.id
            await db.commit()

    async def assert_persisted():
        async with async_engine.connect() as conn:
            conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
            async with AsyncSession(bind=conn) as db:
                messages = (await db.execute(select(Message).where(Message.session_id == session.id))).scalars().all()
                assert len(messages) == 1
                assert messages[0].sender_type == "consumer"
                assert messages[0].content_encrypted == content.encode()
                event = (await db.execute(select(ScreeningEvent).where(
                    ScreeningEvent.session_id == session.id))).scalar_one()
                assert event.action_taken == "immediate_alert"
                if handler != intake._handle_text_message:
                    transcript = (await db.execute(select(Transcript).where(
                        Transcript.recording_id == data["recording_id"]))).scalar_one()
                    assert transcript.status == ("edited" if handler == intake._handle_transcript_edit else "approved")
                    assert transcript.reviewed_at is not None
                    assert transcript.text_encrypted == (
                        data["edited_text"] if handler == intake._handle_transcript_edit else content
                    ).encode()

    websocket = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()), send_json=AsyncMock())
    monkeypatch.setattr(intake, "screen_message_fast", AsyncMock(return_value=SimpleNamespace(
        has_critical=True, has_elevated=False, has_advisory=False,
        safety_resources=[], mandatory_questions=[], triggered_protocols=[{
            "protocol_id": 1, "version_id": 1, "severity_tier": "critical",
        }],
    )))
    generate = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    monkeypatch.setattr(intake.ConversationService, "generate_response", generate)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await handler(websocket, session.id, 1, data, async_engine, llm_service=object())
    assert any(call.args[0]["type"] == "message_ack" for call in websocket.send_json.await_args_list)
    assert not any(call.args[0]["type"] == "system_message" for call in websocket.send_json.await_args_list)
    await assert_persisted()


async def test_chat_handler_returns_model_reply(async_engine, monkeypatch, caplog):
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.services.intake.session_service import IntakeSessionService
    from app.services.llm_service import llm_service_from_headers

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            svc = IntakeSessionService(db)
            record = await svc.create_intake(org_id=1, user_id=None)
            session = await svc.create_session(record.id)
            await db.commit()
    factory = MagicMock(
        return_value=SimpleNamespace(
            chat_async=AsyncMock(return_value=SimpleNamespace(text="When did your employer fire you?"))
        )
    )
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    service = llm_service_from_headers({"X-LLM-API-Key": "chat-visitor-key"})
    websocket = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()), send_json=AsyncMock())
    await intake._handle_text_message(
        websocket, session.id, 1, {"content": "My employer fired me."}, async_engine, llm_service=service
    )
    replies = [c.args[0] for c in websocket.send_json.await_args_list if c.args[0].get("type") == "system_message"]
    assert replies[-1]["content"] == "When did your employer fire you?"
    factory.assert_called_once()
    assert factory.call_args.kwargs["api_key"] == "chat-visitor-key"
    assert "chat-visitor-key" not in caplog.text
    from sqlalchemy import select
    from app.models.intake import Message

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn) as db:
            rows = (await db.execute(select(Message))).scalars().all()
            assert len(rows) == 2
            assert all("chat-visitor-key" not in str(row.__dict__) for row in rows)


def test_folio_loader_never_enables_ambient_llm(monkeypatch):
    from app.services.folio import folio_service

    factory = MagicMock()

    def construct(**kwargs):
        if kwargs.get("llm") is None:
            factory()
        return SimpleNamespace(classes=[], object_properties=[], llm=kwargs.get("llm"))

    monkeypatch.setattr(folio_service, "FOLIO", construct)
    monkeypatch.setattr(folio_service, "_folio_instance", None)
    instance = folio_service.get_folio(branch="main")
    factory.assert_not_called()
    assert instance.llm is None


async def test_exploration_keeps_visitor_provider_and_model(monkeypatch):
    from app.services.analysis.stages.explore import ExploreStage
    from app.services.llm_service import llm_service_from_headers

    factory = MagicMock(return_value=SimpleNamespace(
        json_async=AsyncMock(return_value=SimpleNamespace(data={"issues": []}))
    ))
    other_factory = MagicMock(return_value=factory.return_value)
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", factory)
    monkeypatch.setattr("alea_llm_client.OpenAIModel", factory)
    monkeypatch.setattr("alea_llm_client.GoogleModel", other_factory)
    monkeypatch.setattr(
        "app.services.screening.protocol_service.ProtocolService.get_active_protocols",
        AsyncMock(return_value=[]),
    )
    service = llm_service_from_headers({
        "X-LLM-API-Key": "exploration-visitor-key", "X-LLM-Model": "visitor-model"
    })
    stage = ExploreStage(service, AsyncMock(), org_config={"exploration": {
        "max_rounds": 1, "cheap_llm_provider": "google", "cheap_llm_model": "org-model"
    }})
    result = await stage.execute(
        SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), [],
        [SimpleNamespace(assertion_text="My employer fired me.")],
    )
    assert result["rounds_completed"] == 1
    other_factory.assert_not_called()
    assert factory.call_count == 2
    for call in factory.call_args_list:
        assert call.kwargs == {"api_key": "exploration-visitor-key", "model": "visitor-model"}


async def test_exploration_allows_same_provider_cheap_model(monkeypatch):
    from app.services.analysis.stages.explore import ExploreStage

    factory = MagicMock(return_value=SimpleNamespace(
        json_async=AsyncMock(return_value=SimpleNamespace(data={"issues": []}))
    ))
    monkeypatch.setattr("alea_llm_client.OpenAIModel", factory)
    monkeypatch.setattr(
        "app.services.screening.protocol_service.ProtocolService.get_active_protocols",
        AsyncMock(return_value=[]),
    )
    service = llm_service.llm_service_from_headers({
        "X-LLM-API-Key": "exploration-visitor-key", "X-LLM-Model": "visitor-model",
    })
    stage = ExploreStage(service, AsyncMock(), org_config={"exploration": {
        "max_rounds": 1, "cheap_llm_provider": "openai", "cheap_llm_model": "cheap-model",
    }})
    result = await stage.execute(
        SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), [],
        [SimpleNamespace(assertion_text="My employer fired me.")],
    )
    assert result["rounds_completed"] == 1
    assert factory.call_count == 2
    assert sorted(call.kwargs["model"] for call in factory.call_args_list) == ["cheap-model", "visitor-model"]
    assert all(call.kwargs["api_key"] == "exploration-visitor-key" for call in factory.call_args_list)
