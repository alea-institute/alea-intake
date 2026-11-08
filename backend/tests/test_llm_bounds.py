"""Bounded analysis LLM calls: batching, at most two attempts, terse prompts.

No network: fake models stand in for a reply that stopped at max_tokens
(alea-llm-client raises on the truncated JSON) or returned the wrong shape.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from app.services.llm_bounds import (
    MAX_JSON_ATTEMPTS,
    batched,
    bounded_call,
    gather_bounded,
    validate_items,
)

pytestmark = pytest.mark.asyncio


class TruncatedModel:
    """A model whose every JSON reply hit max_tokens and failed to parse."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self.retry_limit = 3

    async def json_async(self, **kwargs):
        self.calls.append(kwargs["messages"])
        raise ValueError("The cleaned response is not a valid JSON or JSONL object.")


def _service(model) -> MagicMock:
    service = MagicMock()
    service.create_client = MagicMock(return_value=model)
    return service


def _fact(i: int) -> SimpleNamespace:
    return SimpleNamespace(id=i, fact_type="event", confidence=0.9, assertion_text=f"fact {i}")


def _empty_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    return session


async def test_bounded_call_stops_after_two_attempts_and_degrades():
    call = AsyncMock(side_effect=ValueError("truncated"))
    result = await bounded_call(call, lambda raw: raw, stage="t", default="fallback")
    assert result == "fallback"
    assert call.await_count == MAX_JSON_ATTEMPTS == 2
    assert [c.args[0] for c in call.await_args_list] == [False, True]  # 2nd is compact


async def test_bounded_call_logs_stage_and_type_never_content():
    call = AsyncMock(side_effect=ValueError("visitor says secret thing"))
    with capture_logs() as logs:
        await bounded_call(call, lambda raw: raw, stage="fact_map", default=None)
    assert logs and all(entry.get("stage") == "fact_map" for entry in logs)
    assert "visitor says secret thing" not in repr(logs)
    assert logs[0]["exc_type"] == "ValueError"


async def test_validate_items_drops_and_counts_bad_items():
    from app.services.analysis.schemas import FactMappingSchema

    good = {"fact_id": 1, "claim_name": "A", "llm_confidence": 0.5, "mapping_rationale": "r"}
    bad = {"fact_id": "x", "claim_name": "A", "llm_confidence": 9, "mapping_rationale": "r"}
    with capture_logs() as logs:
        items = validate_items([good, bad, "junk"], FactMappingSchema, stage="fact_map")
    assert [i.fact_id for i in items] == [1]
    assert logs[0]["dropped"] == 2 and logs[0]["total"] == 3


async def test_gather_bounded_respects_concurrency():
    active = peak = 0

    async def work():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return 1

    assert await gather_bounded([work] * 10, concurrency=3) == [1] * 10
    assert peak <= 3


async def test_batched_splits_large_inputs():
    assert [len(b) for b in batched(list(range(45)), 20)] == [20, 20, 5]


async def test_fact_map_truncated_reply_two_calls_per_batch_and_returns():
    from app.services.analysis.stages.fact_map import FACT_BATCH_SIZE, FactMapStage

    model = TruncatedModel()
    stage = FactMapStage(llm_service=_service(model), db_session=_empty_session())
    facts = [_fact(i) for i in range(FACT_BATCH_SIZE)]  # exactly one batch
    claims = [SimpleNamespace(id=1, claim_name="A", claim_type="identified", jurisdiction="MN")]
    result = await stage.execute(SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), facts, claims)
    assert result["mappings_created"] == 0
    assert len(model.calls) == 2
    assert model.retry_limit == 1  # client's identical-request retries are off
    # The retry is compact: half the facts and a stricter instruction.
    assert model.calls[1][-1]["role"] == "system"
    assert "at most" in model.calls[1][-1]["content"]
    assert model.calls[1][1]["content"].count("- Fact #") == FACT_BATCH_SIZE // 2


async def test_fact_map_batches_large_inputs():
    from app.services.analysis.stages.fact_map import FACT_BATCH_SIZE, FactMapStage

    stage = FactMapStage(llm_service=MagicMock(), db_session=_empty_session())
    seen: list[int] = []

    async def fake_call(facts, claims, compact=False, claims_text=None):
        assert claims_text is not None  # batches never read the shared session
        seen.append(len(facts))
        return {"mappings": [], "unmapped_facts": [f.id for f in facts]}

    facts = [_fact(i) for i in range(93)]
    claims = [SimpleNamespace(id=1, claim_name="A", claim_type="identified", jurisdiction="MN")]
    with patch.object(stage, "_call_llm", side_effect=fake_call):
        result = await stage.execute(SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), facts, claims)
    assert sorted(seen) == sorted([len(b) for b in batched(facts, FACT_BATCH_SIZE)])
    assert max(seen) <= FACT_BATCH_SIZE
    assert len(result["unmapped_facts"]) == 93


async def test_issue_spot_truncated_reply_two_calls_and_returns():
    from app.services.analysis.stages.issue_spot import IssueSpotStage

    model = TruncatedModel()
    stage = IssueSpotStage(llm_service=_service(model), db_session=_empty_session())
    result = await stage.execute(SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), [_fact(1)])
    assert result["claims_count"] == 0
    assert len(model.calls) == 2


async def test_deadline_detect_truncated_reply_two_calls_and_returns():
    from app.services.analysis.stages.deadline_detect import DeadlineDetectStage

    model = TruncatedModel()
    stage = DeadlineDetectStage(_service(model), _empty_session())
    with patch.object(stage, "_gather_text", AsyncMock(return_value="Served on 2026-11-01.")):
        assert await stage.detect_and_persist(intake_id=1, run_id=1) == []
    assert len(model.calls) == 2


async def test_gap_analyze_invalid_reply_two_calls_and_returns():
    from app.services.analysis.stages.gap_analyze import GapAnalyzeStage

    service = MagicMock()
    service.json_async = AsyncMock(side_effect=ValueError("truncated"))
    stage = GapAnalyzeStage(llm_service=service, db_session=_empty_session())
    claims = [SimpleNamespace(id=1, claim_name="Habitability", rationale="mold")]
    gaps = await stage._detect_procedural_and_doctrine_gaps(
        claims, SimpleNamespace(iteration_number=1), SimpleNamespace(id=1), set()
    )
    assert gaps == []
    assert service.json_async.await_count == 2
    prompts = [c.kwargs["prompt"] for c in service.json_async.await_args_list]
    assert "at most 12 gaps" in prompts[0]
    assert "previous reply was cut off" in prompts[1]


async def test_question_gen_invalid_reply_two_calls_then_fallback():
    from app.services.analysis.stages.question_gen import QuestionGenStage

    service = MagicMock()
    service.json_async = AsyncMock(side_effect=ValueError("truncated"))
    stage = QuestionGenStage(llm_service=service, db_session=_empty_session())
    gap = SimpleNamespace(id=1, status="open", priority=50, gap_type="procedural_requirement",
                          description="Was notice given?", claim_id=None, element_id=None)
    with patch.object(stage, "_fallback_questions", AsyncMock(return_value={"questions_generated": 1})):
        result = await stage.execute(SimpleNamespace(id=1), SimpleNamespace(iteration_number=1), [gap])
    assert result == {"questions_generated": 1}
    assert service.json_async.await_count == 2


async def test_exploration_layer_truncated_two_calls_and_no_placeholder_prompt():
    from app.services.exploration import layers

    model = TruncatedModel()
    with patch.object(layers, "_create_llm_model", return_value=model):
        assert await layers.layer_cheap_llm(MagicMock(), "facts", [], {}) == []
        assert await layers.layer_expensive_llm(MagicMock(), "facts", [], [], [], {}) == []
    assert len(model.calls) == 4  # two layers, two attempts each
    system = model.calls[0][0]["content"]
    assert "no placeholder" in system and '"Correction:"' in system
    assert "at most 8 issues" in system


async def test_exploration_layer_caps_and_tolerates_bad_items():
    from app.services.exploration import layers

    issues = [{"claim_name": f"I{i}", "description": "d", "confidence": "high"} for i in range(20)]
    model = SimpleNamespace(json_async=AsyncMock(return_value=SimpleNamespace(data={"issues": [*issues, "junk"]})))
    with patch.object(layers, "_create_llm_model", return_value=model):
        results = await layers.layer_cheap_llm(MagicMock(), "facts", [], {})
    assert len(results) == layers.MAX_EXPLORATION_ISSUES
    assert all(r.confidence == 0.5 for r in results)
    assert model.json_async.await_count == 1


async def test_stage_failure_log_names_stage_and_type_only():
    from app.services.analysis.orchestrator import AnalysisOrchestrator

    orch = AnalysisOrchestrator(db_session=_empty_session(), llm_service=MagicMock())
    failing = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("visitor narrative")))
    loaders = {name: AsyncMock(return_value=[]) for name in (
        "_load_facts", "_load_claims", "_load_elements", "_load_mappings", "_load_gaps", "_load_questions")}
    with patch.multiple(orch, _get_stage_instance=MagicMock(return_value=failing), **loaders):
        with capture_logs() as logs:
            result = await orch._execute_stage_inner(
                "fact_map", SimpleNamespace(id=1, intake_id=1),
                SimpleNamespace(id=1, iteration_number=1), None,
            )
    entry = next(e for e in logs if e["event"] == "analysis_stage_failed")
    assert entry["stage"] == "fact_map" and entry["exc_type"] == "RuntimeError"
    assert "visitor narrative" not in repr(logs) + repr(result)


@pytest.mark.parametrize("showcase,expected", [(True, 2), (False, 10)])
async def test_iteration_cap_applies_only_in_showcase_mode(monkeypatch, showcase, expected):
    from app import config as app_config
    from app.services.analysis.orchestrator import AnalysisOrchestrator

    real = app_config.get_settings()
    fake = real.model_copy(update={"showcase_mode": showcase, "showcase_max_iterations": 2})
    monkeypatch.setattr(app_config, "get_settings", lambda: fake)
    orch = AnalysisOrchestrator(db_session=_empty_session(), llm_service=MagicMock())
    assert orch._analysis_config.max_iterations == expected


async def test_llm_service_json_data_async_turns_client_retries_off():
    from app.services.llm_service import LLMService

    model = SimpleNamespace(retry_limit=3, json_async=AsyncMock(return_value=SimpleNamespace(data={"a": 1})))
    service = LLMService(api_key="synthetic", provider="openai", model="gpt-4")
    with patch.object(service, "create_client", return_value=model):
        assert await service.json_data_async("Return JSON") == {"a": 1}
    assert model.retry_limit == 1
