"""Offline replay contract, using deliberately synthetic responses."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def replay():
    spec = importlib.util.spec_from_file_location("regression_replay", ROOT / "scripts/regression_replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def accepted():
    return {"issues": ["Unpaid wages", "Retaliation"], "folio_iris": ["urn:synthetic:wages"],
            "deadlines": [{"date": "2026-12-01", "trigger": "served"}], "citations": ["Synthetic statute 1"]}


def test_dropped_issue_fails_and_names_issue(replay, accepted):
    current = {**accepted, "issues": ["Unpaid wages"]}
    diff = replay.compare(accepted, current)
    assert diff["lost"]["issues"] == ["Retaliation"]
    assert not replay.passes(diff)


def test_extra_concept_is_addition(replay, accepted):
    diff = replay.compare(accepted, {**accepted, "folio_iris": [*accepted["folio_iris"], "urn:synthetic:extra"]})
    assert diff["added"]["folio_iris"] == ["urn:synthetic:extra"]
    assert replay.passes(diff)


def test_unchanged_passes(replay, accepted):
    assert replay.passes(replay.compare(accepted, accepted))


@pytest.mark.parametrize("category", ["folio_iris", "deadlines", "citations"])
def test_each_lost_category_fails(replay, accepted, category):
    assert not replay.passes(replay.compare(accepted, {**accepted, category: []}))


@pytest.mark.asyncio
async def test_changed_prompt_fails_closed_with_stage_and_hash(replay, tmp_path):
    store = replay.RecordingStore(tmp_path)
    client = store.client("issue_spot", "synthetic", "test-model")
    with pytest.raises(replay.MissingRecording, match=r"issue_spot.*[0-9a-f]{64}"):
        await client.json_async(messages=[{"role": "user", "content": "changed narrative"}])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_record_then_replay_and_prompt_model_identity(replay, tmp_path):
    messages = [{"role": "system", "content": "Return JSON"}, {"role": "user", "content": "Unpaid wages"}]
    class Live:
        async def json_async(self, **kwargs):
            return SimpleNamespace(data={"claims": ["Unpaid wages"]}, text="")
    recording = replay.RecordingStore(tmp_path, record=True, operator_key="synthetic-test-key")
    reply = await recording.client("issue_spot", "synthetic", "test-model", Live()).json_async(messages=messages)
    assert reply.data == {"claims": ["Unpaid wages"]}
    store = replay.RecordingStore(tmp_path)
    assert (await store.client("issue_spot", "synthetic", "test-model").json_async(messages=messages)).data == reply.data
    with pytest.raises(replay.MissingRecording):
        await store.client("issue_spot", "synthetic", "other-model").json_async(messages=messages)
    assert "synthetic-test-key" not in next(tmp_path.glob("*.json")).read_text()


def test_record_requires_explicit_key(replay, tmp_path):
    with pytest.raises(ValueError, match="operator key"):
        replay.RecordingStore(tmp_path, record=True)


def test_accept_records_reason_prompt_and_issue_diff(replay, tmp_path, accepted):
    path = tmp_path / "persona.json"
    replay.accept(path, accepted, [{"stage": "issue_spot", "hash": "old"}], "Initial synthetic baseline")
    changed = {**accepted, "issues": ["Unpaid wages"]}
    replay.accept(path, changed, [{"stage": "issue_spot", "hash": "new"}], "Reviewed removal")
    saved = json.loads(path.read_text())
    assert saved["history"][-1]["reason"] == "Reviewed removal"
    assert saved["history"][-1]["issue_diff"]["lost"]["issues"] == ["Retaliation"]
    assert saved["history"][-1]["prompt_diff"]["before"] == [{"stage": "issue_spot", "hash": "old"}]
    with pytest.raises(ValueError, match="reason"):
        replay.accept(path, changed, [], "  ")


@pytest.mark.asyncio
async def test_service_seam_intercepts_stage_and_swallowed_miss(replay, tmp_path):
    from app.services.llm_service import LLMService
    from app.services.analysis.stages.issue_spot import IssueSpotStage
    service = LLMService(api_key="replay-no-network", provider="openai", model="gpt-4")
    store = replay.RecordingStore(tmp_path)
    with pytest.raises(replay.MissingRecording, match="issue_spot"):
        with replay.recorded_clients(store, service):
            try:
                await IssueSpotStage(service, None)._call_llm([])
            except replay.MissingRecording:
                pass  # Reproduce production's graceful degradation.


@pytest.mark.asyncio
async def test_synthetic_stage_replays_unchanged_and_detects_seeded_loss(replay):
    from app.services.llm_service import LLMService
    from app.services.analysis.stages.issue_spot import IssueSpotStage
    fixture = ROOT / "backend/tests/regression/fixtures"
    fact = SimpleNamespace(fact_type="other", confidence=1.0,
                           assertion_text=(fixture / "personas/synthetic-worker/narrative.txt").read_text().strip())
    store = replay.RecordingStore(ROOT / "docs/evidence/regression/recordings")
    with replay.recorded_clients(store, LLMService(api_key="replay-no-network", provider="openai", model="gpt-4")):
        response = await IssueSpotStage(LLMService(api_key="replay-no-network", provider="openai", model="gpt-4"), None)._call_llm([fact])
    snapshot = {"issues": sorted(c["claim_name"] for c in response["claims"]),
                "folio_iris": [], "deadlines": [], "citations": []}
    baseline = json.loads((ROOT / "docs/evidence/regression/baseline/synthetic-worker.json").read_text())
    assert replay.passes(replay.compare(baseline["snapshot"], snapshot))
    snapshot["issues"].remove("Retaliation")  # Seed the regression in this run's output.
    diff = replay.compare(baseline["snapshot"], snapshot)
    assert diff["lost"]["issues"] == ["Retaliation"]
    assert not replay.passes(diff)


@pytest.mark.asyncio
async def test_invalid_recording_cannot_be_swallowed(replay, tmp_path):
    messages = [{"role": "user", "content": "Synthetic"}]
    digest, _ = replay.prompt_identity("openai", "test-model", messages)
    (tmp_path / f"{digest}.json").write_text("{invalid json")
    store = replay.RecordingStore(tmp_path)
    try:
        await store.client("issue_spot", "openai", "test-model").json_async(messages=messages)
    except ValueError:
        pass
    with pytest.raises(ValueError):
        store.check()


def test_prompt_normalizes_message_key_order_and_system_transport(replay):
    first = replay.prompt_identity("openai", "model", [{"role": "user", "content": "Facts"}], "System")
    second = replay.prompt_identity("openai", "model", [{"content": "System", "role": "system"},
                                                       {"content": "Facts", "role": "user"}])
    assert first == second


@pytest.mark.parametrize("key", [None, "", "   "])
def test_replay_still_requires_explicit_key(monkeypatch, key):
    from app.services.llm_service import LLMService, replay_client_factory
    monkeypatch.setenv("ALEA_LLM_API_KEY", "ambient-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-test-key")
    with replay_client_factory(lambda *args: pytest.fail("Replay bypassed key requirement")):
        with pytest.raises(ValueError, match="visitor LLM API key is required"):
            LLMService(api_key=key).create_client()


def test_replay_client_is_scoped_and_placeholder_never_reaches_provider(monkeypatch):
    from app.services import llm_service
    service = llm_service.LLMService(api_key="replay-no-network", provider="openai", model="gpt-4")
    def provider(**kwargs):
        pytest.fail("Replay placeholder reached a real provider")
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", provider)
    client = SimpleNamespace()
    with llm_service.replay_client_factory(lambda *args: client):
        assert service.create_client() is client
    # After replay exits, normal callers use their own credential again.
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai", lambda **kwargs: kwargs)
    assert llm_service.LLMService(api_key="visitor-key", provider="openai", model="visitor-model").create_client() == {
        "api_key": "visitor-key", "model": "visitor-model"}


@pytest.mark.asyncio
async def test_exploration_replay_catches_swallowed_miss(replay, tmp_path, monkeypatch):
    from app.services import llm_service
    from app.services.exploration.layers import _create_llm_model
    monkeypatch.setitem(llm_service._PROVIDER_MODEL_MAP, "openai",
                        lambda **kwargs: pytest.fail("Replay reached a real provider"))
    service = llm_service.LLMService(api_key="replay-no-network", provider="openai", model="gpt-4")
    store = replay.RecordingStore(tmp_path)
    with pytest.raises(replay.MissingRecording, match="llm_service"):
        with replay.recorded_clients(store, service):
            try:
                await _create_llm_model(service).json_async(messages=[])
            except replay.MissingRecording:
                pass


@pytest.mark.asyncio
async def test_command_supplies_explicit_replay_placeholder(replay, tmp_path, monkeypatch, accepted):
    async def run_persona(persona, store, service):
        assert service.api_key == "replay-no-network"
        assert (service.provider, service.model) == ("openai", "gpt-4")
        return accepted
    monkeypatch.setattr(replay, "run_persona", run_persona)
    args = SimpleNamespace(recordings=tmp_path / "recordings", record=False,
                           provider="openai", model="gpt-4",
                           personas=ROOT / "backend/tests/regression/fixtures/personas",
                           baseline=tmp_path / "baseline", accept=True, reason="Synthetic baseline")
    assert await replay.main_async(args) == 0
