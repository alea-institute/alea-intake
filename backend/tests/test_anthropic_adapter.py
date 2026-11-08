"""Anthropic calls send a top-level system prompt and a real output limit.

Regression for a live measurement: 39 of 129 Anthropic calls returned HTTP 400
("use the top-level 'system' parameter") and every successful call stopped at
alea-llm-client's 128-token default. No test here touches the network.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import llm_service
from app.services.llm_service import (
    ANTHROPIC_CHAT_MAX_TOKENS,
    ANTHROPIC_JSON_MAX_TOKENS,
    AnthropicAdapter,
    LLMService,
    _PROVIDER_MODEL_MAP,
)


class FakeAnthropicModel:
    """Records the kwargs each call receives."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.calls: list[tuple[str, dict]] = []
        self.marker = "delegated"

    async def chat_async(self, *args, **kwargs):
        self.calls.append(("chat_async", kwargs))
        return SimpleNamespace(text="hello")

    async def json_async(self, *args, **kwargs):
        self.calls.append(("json_async", kwargs))
        return SimpleNamespace(data={"answer": "yes"})


def _service(provider="anthropic", model="claude-sonnet-5-5"):
    return LLMService(api_key="test-visitor-key", provider=provider, model=model)


@pytest.fixture
def fake_anthropic():
    with patch.dict(_PROVIDER_MODEL_MAP, {"anthropic": FakeAnthropicModel}):
        yield


def test_default_anthropic_model_is_sonnet_5_5(monkeypatch):
    monkeypatch.delenv("ALEA_LLM_MODEL", raising=False)
    service = LLMService(api_key="k", provider="anthropic")
    assert service.model == "claude-sonnet-5-5"


def test_create_client_wraps_anthropic(fake_anthropic):
    client = _service().create_client()
    assert isinstance(client, AnthropicAdapter)
    assert client.marker == "delegated"  # other attributes delegate


@pytest.mark.parametrize("provider", ["openai", "google", "vllm"])
def test_non_anthropic_providers_get_unwrapped_model(provider):
    instance = MagicMock()
    with patch.dict(_PROVIDER_MODEL_MAP, {provider: MagicMock(return_value=instance)}):
        client = _service(provider=provider, model="m").create_client()
    assert client is instance


def test_replay_factory_is_not_wrapped():
    sentinel = object()
    with llm_service.replay_client_factory(lambda *_: sentinel):
        assert _service().create_client() is sentinel


async def test_system_message_becomes_system_kwarg(fake_anthropic):
    client = _service().create_client()
    await client.json_async(messages=[
        {"role": "system", "content": "be precise"},
        {"role": "user", "content": "hi"},
    ])
    _, kwargs = client._model.calls[0]
    assert kwargs["system"] == "be precise"
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


async def test_two_system_messages_join_in_order(fake_anthropic):
    client = _service().create_client()
    await client.chat_async(messages=[
        {"role": "system", "content": "first"},
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "second"},
    ])
    _, kwargs = client._model.calls[0]
    assert kwargs["system"] == "first\n\nsecond"
    assert all(m["role"] != "system" for m in kwargs["messages"])


async def test_no_system_message_sends_no_system_kwarg(fake_anthropic):
    client = _service().create_client()
    await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    assert "system" not in client._model.calls[0][1]


async def test_max_tokens_default_per_method(fake_anthropic):
    client = _service().create_client()
    await client.json_async(messages=[{"role": "user", "content": "hi"}])
    await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    (_, json_kwargs), (_, chat_kwargs) = client._model.calls
    assert json_kwargs["max_tokens"] == ANTHROPIC_JSON_MAX_TOKENS == 8192
    assert chat_kwargs["max_tokens"] == ANTHROPIC_CHAT_MAX_TOKENS == 4096


async def test_caller_max_tokens_wins(fake_anthropic):
    client = _service().create_client()
    await client.json_async(messages=[{"role": "user", "content": "hi"}], max_tokens=300)
    await client.chat_async(messages=[{"role": "user", "content": "hi"}], max_tokens=50)
    assert [kw["max_tokens"] for _, kw in client._model.calls] == [300, 50]


async def test_sampling_params_dropped(fake_anthropic):
    client = _service().create_client()
    await client.json_async(
        messages=[{"role": "user", "content": "hi"}], temperature=0.2, top_p=0.9, top_k=5
    )
    await client.chat_async(messages=[{"role": "user", "content": "hi"}], temperature=0.0)
    for _, kwargs in client._model.calls:
        assert not {"temperature", "top_p", "top_k"} & kwargs.keys()


async def test_caller_messages_list_not_mutated(fake_anthropic):
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    await _service().create_client().json_async(messages=messages)
    assert len(messages) == 2


async def test_service_acomplete_and_json_async_route_system(fake_anthropic):
    from pydantic import BaseModel

    class Result(BaseModel):
        answer: str

    service = _service()
    captured: list[FakeAnthropicModel] = []
    original = service.create_client

    def create_client():
        client = original()
        captured.append(client._model)
        return client

    service.create_client = create_client
    assert await service.acomplete([{"role": "user", "content": "hi"}], system_prompt="sys") == "hello"
    result = await service.json_async("give json", Result, system_prompt="sys")
    assert result.answer == "yes"
    (_, chat_kwargs), = captured[0].calls
    (_, json_kwargs), = captured[1].calls
    assert chat_kwargs["system"] == "sys"
    assert json_kwargs["system"] == "sys"
    assert all(m["role"] == "user" for m in chat_kwargs["messages"] + json_kwargs["messages"])


async def test_stage_create_client_json_async_moves_system(fake_anthropic):
    """A stage that builds [system, user] itself reaches the model with system moved."""
    from app.services.analysis.stages.fact_map import FACT_MAP_SYSTEM_PROMPT, FactMapStage

    service = _service()
    models: list[AnthropicAdapter] = []
    original = service.create_client

    def create_client():
        client = original()
        models.append(client)
        return client

    service.create_client = create_client

    stage = FactMapStage(llm_service=service, db_session=AsyncMock())
    fact = SimpleNamespace(id=1, fact_type="event", confidence=0.9, assertion_text="I was fired.")
    data = await stage._call_llm([fact], [])

    assert data == {"answer": "yes"}
    (_, kwargs), = models[0]._model.calls
    assert kwargs["system"] == FACT_MAP_SYSTEM_PROMPT
    assert [m["role"] for m in kwargs["messages"]] == ["user"]
    assert kwargs["max_tokens"] == ANTHROPIC_JSON_MAX_TOKENS


async def test_real_client_request_body_carries_system_and_max_tokens():
    """Through the real AnthropicModel, `system` and `max_tokens` reach the HTTP body."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": '{"answer": "yes"}'}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "stop_reason": "end_turn",
        })

    client = _service().create_client()
    assert isinstance(client, AnthropicAdapter)
    client._model.async_client = httpx.AsyncClient(
        base_url="https://api.anthropic.test", transport=httpx.MockTransport(handler)
    )
    response = await client.json_async(
        messages=[
            {"role": "system", "content": "Respond with JSON."},
            {"role": "user", "content": "hi"},
        ],
        temperature=0.3,
    )
    assert response.data == {"answer": "yes"}
    body = seen[0]
    assert body["system"] == "Respond with JSON."
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["max_tokens"] == ANTHROPIC_JSON_MAX_TOKENS
    assert "temperature" not in body
    # No assistant prefill: the last message stays the user's turn.
    assert body["messages"][-1]["role"] == "user"
