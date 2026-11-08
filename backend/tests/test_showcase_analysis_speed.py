"""Showcase analysis budget: one iteration, one fact_map/gap round, tight caps,
low effort on Anthropic JSON calls. Authenticated mode keeps today's behavior.

No network: a fake model answers every LLM call by prompt content.
"""
import asyncio
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.test_showcase_mode import showcase as showcase, guest  # noqa: F401

JURISDICTIONS = ["Minnesota", "Federal", "Hennepin County"]


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    return session


def _settings(monkeypatch, **update):
    from app import config as app_config

    fake = app_config.get_settings().model_copy(update=update)
    monkeypatch.setattr(app_config, "get_settings", lambda: fake)
    return fake


class FakeModel:
    """Routes JSON calls by prompt text; records the stage of every call."""

    retry_limit = 3

    def __init__(self, fact_ids: list[int]):
        self.fact_ids = fact_ids
        self.calls: Counter[str] = Counter()
        self.messages: dict[str, list] = {}

    def _route(self, text: str) -> tuple[str, dict]:
        if "issue-spotting assistant. Given a set of extracted facts" in text:
            claims = [
                {
                    "claim_name": f"Claim {i}", "claim_type": "identified",
                    "jurisdiction": JURISDICTIONS[i % 3], "confidence": 0.8,
                    "rationale": "The client reports the condition.", "is_potential": False,
                    "elements": [{"element_name": "Notice", "element_description": "Landlord knew"}],
                }
                for i in range(12)
            ]
            return "issue_spot", {"claims": claims, "jurisdictions": JURISDICTIONS, "summary": "s"}
        if "legal fact-mapping assistant" in text:
            ids = [int(part.split(":")[0]) for part in text.split("Fact #")[1:]]
            mappings = [
                {"fact_id": fid, "claim_name": "Claim 0", "element_name": "Notice",
                 "llm_confidence": 0.9, "mapping_rationale": "Shows notice."}
                for fid in ids for _ in range(3)
            ]
            return "fact_map", {"mappings": mappings, "unmapped_facts": []}
        if "PROCEDURAL" in text:
            gaps = [{"gap_type": "procedural_requirement", "claim_name": None, "element_name": None,
                     "description": f"Did you get written notice {i}?", "priority": 50}
                    for i in range(20)]
            return "gap_analyze", {"gaps": gaps, "coverage_pct": 0.0, "summary": "s"}
        if "follow-up questions" in text:
            questions = [{"question_text": f"When did it start {i}?", "rationale": "Dates matter.",
                          "priority": 1, "gap_description": "d"} for i in range(20)]
            return "question_gen", {"groups": [{"topic": "Timeline", "questions": questions}],
                                    "total_questions": 20}
        if "issues" in text.lower():
            return "explore", {"issues": [
                {"claim_name": f"Discovered {i}", "description": "d", "confidence": 0.7,
                 "rationale": "The client reports it."} for i in range(5)]}
        return "other", {}

    async def json_async(self, messages=None, **kwargs):
        text = "\n".join(str(m.get("content", "")) for m in messages or [])
        stage, data = self._route(text)
        self.calls[stage] += 1
        self.messages.setdefault(stage, messages)
        return SimpleNamespace(data=data)

    async def chat_async(self, messages=None, **kwargs):
        self.calls["chat"] += 1
        return SimpleNamespace(text="Plain words.")


async def _seed_facts(intake_id: int, count: int) -> list[int]:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.engine import get_engine
    from app.models.fact import ExtractedFact

    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            facts = [ExtractedFact(intake_id=intake_id, message_id=1, fact_type="event",
                                   assertion_text=f"The heat failed on day {i}.", confidence=0.9)
                     for i in range(count)]
            db.add_all(facts)
            await db.commit()
            return [f.id for f in facts]


async def test_showcase_guest_run_is_one_iteration_one_round_and_memo_generates(showcase, monkeypatch):
    from app.services.analysis import background
    from app.services.llm_service import LLMService

    client, settings, _ = showcase
    assert settings.showcase_max_iterations == 1  # default, no extra env
    monkeypatch.setattr("app.services.extraction.backfill.backfill_intake_facts",
                        AsyncMock(return_value=0))
    monkeypatch.setattr("app.services.folio.folio_service.get_folio", lambda: None)
    monkeypatch.setattr(
        "app.services.analysis.stages.deadline_detect.DeadlineDetectStage.detect_and_persist",
        AsyncMock(return_value=[]))

    headers = {**await guest(client), "X-LLM-API-Key": "visitor-key"}
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    fact_ids = await _seed_facts(created["id"], 50)
    fake = FakeModel(fact_ids)
    monkeypatch.setattr(LLMService, "create_client", lambda self: fake)

    started = await client.post(f'/api/v1/analysis/{created["id"]}/analyze', headers=headers)
    assert started.status_code == 202, started.text
    run_id = started.json()["run_id"]
    task = background._tasks.get(run_id)
    if task is not None:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)

    status = (await client.get(f'/api/v1/analysis/{created["id"]}/status', headers=headers)).json()
    assert status["status"] in {"completed", "complete", "converged", "max_iterations"}, status

    # Exactly one iteration and one fact_map/gap round although issue_spot
    # reported three jurisdictions: 50 facts = 3 fact_map batches, 1 gap call.
    assert fake.calls["issue_spot"] == 1
    assert fake.calls["fact_map"] == 3
    assert fake.calls["gap_analyze"] == 1
    assert fake.calls["question_gen"] == 1

    results = await client.get(f'/api/v1/analysis/{created["id"]}/results', headers=headers)
    assert results.status_code == 200, results.text
    body = results.json()
    claims = body.get("claims") or []
    assert 0 < len(claims) <= settings.showcase_max_claims

    memo = await client.post("/api/v1/output/generate", headers=headers,
                             json={"run_id": run_id, "intake_id": created["id"]})
    assert memo.status_code == 201, memo.text
    print("SHOWCASE_LLM_CALLS", dict(fake.calls))


@pytest.mark.parametrize("showcase_mode,iterations,rounds", [(True, 1, 1), (False, 10, 3)])
async def test_rounds_and_iterations_by_mode(monkeypatch, showcase_mode, iterations, rounds):
    from app.services.analysis.orchestrator import AnalysisOrchestrator

    _settings(monkeypatch, showcase_mode=showcase_mode)
    orch = AnalysisOrchestrator(db_session=_empty_session(), llm_service=MagicMock())
    assert orch._analysis_config.max_iterations == iterations

    seen: list[tuple[str, str | None]] = []

    async def execute(stage_name, run, iteration, ws_manager, jurisdiction=None):
        seen.append((stage_name, jurisdiction))
        return {"jurisdictions": JURISDICTIONS} if stage_name == "issue_spot" else {}

    monkeypatch.setattr(orch, "_execute_stage", execute)
    monkeypatch.setattr(orch, "_start_procedural_prefetch", AsyncMock())
    await orch._run_iteration(SimpleNamespace(id=1, intake_id=1), 1, None)
    assert [s for s, _ in seen].count("fact_map") == rounds
    assert [s for s, _ in seen].count("gap_analyze") == rounds
    assert seen[-1][0] == "question_gen"


async def test_exploration_rounds_capped_only_in_showcase(monkeypatch):
    from app.services.analysis.orchestrator import AnalysisOrchestrator

    _settings(monkeypatch, showcase_mode=True)
    orch = AnalysisOrchestrator(db_session=_empty_session(), llm_service=MagicMock(),
                                org_config={"exploration": {"max_rounds": 3}})
    assert orch._org_config["exploration"]["max_rounds"] == 1

    _settings(monkeypatch, showcase_mode=False)
    orch = AnalysisOrchestrator(db_session=_empty_session(), llm_service=MagicMock(),
                                org_config={"exploration": {"max_rounds": 3}})
    assert orch._org_config["exploration"]["max_rounds"] == 3


class _Inner:
    def __init__(self):
        self.calls = []

    async def json_async(self, **kwargs):
        self.calls.append(("json", kwargs))
        return SimpleNamespace(data={})

    async def chat_async(self, **kwargs):
        self.calls.append(("chat", kwargs))
        return SimpleNamespace(text="")


@pytest.mark.parametrize("showcase_mode,setting,expected", [
    (True, "", "low"), (False, "", None), (True, "none", None),
    (False, "medium", "medium"), (True, "max", "max"),
])
async def test_json_effort_reaches_anthropic_json_calls_only(monkeypatch, showcase_mode, setting, expected):
    from app.services.llm_service import AnthropicAdapter

    _settings(monkeypatch, showcase_mode=showcase_mode, anthropic_json_effort=setting)
    inner = _Inner()
    adapter = AnthropicAdapter(inner)
    await adapter.json_async(messages=[{"role": "user", "content": "json"}])
    await adapter.chat_async(messages=[{"role": "user", "content": "hi"}])
    json_kwargs = inner.calls[0][1]
    assert json_kwargs.get("output_config") == ({"effort": expected} if expected else None)
    assert "output_config" not in inner.calls[1][1]


async def test_json_effort_reaches_request_body(monkeypatch):
    """alea-llm-client copies output_config into the HTTP request body."""
    import alea_llm_client

    from app.services.llm_service import AnthropicAdapter

    _settings(monkeypatch, showcase_mode=True)
    model = alea_llm_client.AnthropicModel(api_key="synthetic", model="claude-sonnet-5-5")
    bodies = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"type": "text", "text": "{\"a\": 1}"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1}, "stop_reason": "end_turn"}

    async def post(url, json=None, headers=None, **kwargs):
        bodies.append(json)
        return Response()

    monkeypatch.setattr(model, "async_client", SimpleNamespace(post=post), raising=False)
    adapter = AnthropicAdapter(model)
    try:
        await adapter.json_async(messages=[{"role": "user", "content": "Return JSON"}])
    except Exception:
        pass  # response parsing is not under test; the request body is
    assert bodies and bodies[0]["output_config"] == {"effort": "low"}


def test_json_effort_setting_rejects_unknown_value():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key="k", anthropic_json_effort="turbo")
    assert Settings(_env_file=None, secret_key="k", anthropic_json_effort="XHigh").anthropic_json_effort == "xhigh"


async def test_issue_spot_prompt_unchanged_outside_showcase_and_capped_inside(monkeypatch):
    from app.services.analysis.stages import issue_spot

    fake = FakeModel([])
    llm = SimpleNamespace(create_client=lambda: fake)
    facts = [SimpleNamespace(fact_type="event", confidence=0.9, assertion_text="Heat failed.")]

    _settings(monkeypatch, showcase_mode=False)
    stage = issue_spot.IssueSpotStage(llm_service=llm, db_session=_empty_session())
    await stage._call_llm(facts)
    plain = fake.messages.pop("issue_spot")
    assert plain == [
        {"role": "system", "content": issue_spot.ISSUE_SPOT_SYSTEM_PROMPT},
        {"role": "user", "content": "Extracted facts:\n- [event] (confidence: 0.90) Heat failed."},
    ]

    _settings(monkeypatch, showcase_mode=True)
    await stage._call_llm(facts)
    capped = fake.messages.pop("issue_spot")
    assert capped[:2] == plain and "at most 6 claims" in capped[2]["content"]


async def test_showcase_caps_reach_gap_question_and_fact_map_prompts(monkeypatch):
    from app.services.analysis.stages.fact_map import FactMapStage
    from app.services.analysis.stages.gap_analyze import GapAnalyzeStage

    _settings(monkeypatch, showcase_mode=True)
    prompts = []

    async def json_async(prompt, schema, system_prompt=None):
        prompts.append(prompt)
        return schema.model_validate({"gaps": []})

    llm = SimpleNamespace(json_async=json_async)
    claims = [SimpleNamespace(id=1, claim_name="Habitability", rationale="r")]
    await GapAnalyzeStage(llm_service=llm, db_session=_empty_session()).procedural_gap_schemas(claims)
    assert "Return at most 8 gaps" in prompts[0] and "under 20 words" in prompts[0]

    fake = FakeModel([1])
    stage = FactMapStage(llm_service=SimpleNamespace(create_client=lambda: fake),
                         db_session=_empty_session())
    fact = SimpleNamespace(id=1, fact_type="event", confidence=0.9, assertion_text="Heat failed.")
    await stage._call_llm([fact], claims, claims_text="Claim: Habitability")
    addendum = fake.messages["fact_map"][-1]["content"]
    assert "at most 2 mappings per fact" in addendum and "under 12 words" in addendum

    _settings(monkeypatch, showcase_mode=False)
    prompts.clear()
    await GapAnalyzeStage(llm_service=llm, db_session=_empty_session()).procedural_gap_schemas(claims)
    assert "Return at most 12 gaps" in prompts[0] and "under 30 words" in prompts[0]
