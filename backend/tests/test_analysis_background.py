"""POST /analyze starts work in the background; /status reports its outcome."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from tests.test_showcase_mode import showcase as showcase, guest  # noqa: F401


@pytest.fixture
def stubbed_stages(monkeypatch):
    """Gate backfill on an event; let a fake orchestrator finish the run."""
    from app.services.analysis.orchestrator import AnalysisOrchestrator

    gate, started, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    outcome = {"error": None}

    async def backfill(db, intake_id, *args, **kwargs):
        started.set()
        try:
            await gate.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return 0

    async def run(self, intake_id, session_id, ws_manager=None, run=None, commit_progress=False):
        if outcome["error"]:
            raise outcome["error"]
        run.status = "converged"
        run.current_iteration_number = 1
        await self._session.flush()
        return run

    monkeypatch.setattr("app.services.extraction.backfill.backfill_intake_facts", backfill)
    monkeypatch.setattr(AnalysisOrchestrator, "run", run)
    monkeypatch.setattr("app.services.folio.folio_service.get_folio", lambda: None)
    monkeypatch.setattr(
        "app.services.analysis.stages.deadline_detect.DeadlineDetectStage.detect_and_persist",
        AsyncMock(return_value=[]))
    return gate, started, cancelled, outcome


async def _start(client):
    headers = {**await guest(client), "X-LLM-API-Key": "visitor-key"}
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    response = await asyncio.wait_for(
        client.post(f'/api/v1/analysis/{created["id"]}/analyze', headers=headers), 2)
    assert response.status_code == 202, response.text
    return headers, created, response.json()


async def _finish(run_id):
    from app.services.analysis import background

    task = background._tasks.get(run_id)
    if task is not None:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_analyze_returns_promptly_and_status_reaches_terminal(showcase, stubbed_stages):
    client, _, app = showcase
    gate, started, _, _ = stubbed_stages
    headers, created, body = await _start(client)
    assert body["status"] == "running" and body["run_id"]
    await asyncio.wait_for(started.wait(), 2)

    status = (await client.get(f'/api/v1/analysis/{created["id"]}/status', headers=headers)).json()
    assert status == {**status, "run_id": body["run_id"], "status": "running"}
    again = await client.post(f'/api/v1/analysis/{created["id"]}/analyze', headers=headers)
    assert again.json()["run_id"] == body["run_id"]  # no duplicate run while in flight

    gate.set()
    await _finish(body["run_id"])
    status = (await client.get(f'/api/v1/analysis/{created["id"]}/status', headers=headers)).json()
    assert status["status"] == "converged"
    assert app.state.analysis_admitted == 0


async def test_background_failure_sets_failed_status(showcase, stubbed_stages):
    client, _, app = showcase
    gate, _, _, outcome = stubbed_stages
    outcome["error"] = RuntimeError("stage exploded")
    gate.set()
    headers, created, body = await _start(client)
    await _finish(body["run_id"])
    status = (await client.get(f'/api/v1/analysis/{created["id"]}/status', headers=headers)).json()
    assert status["status"] == "failed"
    assert app.state.analysis_admitted == 0


async def test_erase_cancels_background_analysis(showcase, stubbed_stages):
    from sqlalchemy import func, select

    from app.db.engine import get_engine
    from app.db.retention import _active
    from app.models.analysis import AnalysisRun
    from app.services.analysis import background
    from app.showcase import _guest_tasks

    client, _, app = showcase
    _, started, cancelled, _ = stubbed_stages
    headers, created, body = await _start(client)
    await asyncio.wait_for(started.wait(), 2)
    task = background._tasks[body["run_id"]]

    erased = await asyncio.wait_for(
        client.post(f'/api/v1/intake/{created["id"]}/end-session', headers=headers), 5)
    assert erased.status_code == 200, erased.text
    assert cancelled.is_set() and task.cancelled()
    assert app.state.analysis_admitted == 0
    assert not _guest_tasks and not _active
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None})
        assert (await conn.execute(select(func.count()).select_from(AnalysisRun))).scalar_one() == 0


async def test_new_work_refused_while_erase_pending():
    from app.showcase import _erasing_guests, spawn_guest_task

    ran = []

    async def work():
        ran.append(True)

    _erasing_guests.add(424242)
    try:
        with pytest.raises(HTTPException) as exc:
            spawn_guest_task(424242, work())
        assert exc.value.status_code == 409
    finally:
        _erasing_guests.discard(424242)
    await asyncio.sleep(0)
    assert ran == []


async def test_orphaned_running_run_is_failed_and_replaced(showcase, stubbed_stages):
    from app.db.engine import get_engine
    from app.models.analysis import AnalysisRun
    from sqlalchemy.ext.asyncio import AsyncSession

    client, _, _ = showcase
    gate, _, _, _ = stubbed_stages
    gate.set()
    headers = {**await guest(client), "X-LLM-API-Key": "visitor-key"}
    created = (await client.post("/api/v1/intake/", headers=headers, json={})).json()
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn) as db:
            orphan = AnalysisRun(intake_id=created["id"], status="running", trigger_type="manual")
            db.add(orphan)
            await db.flush()
            orphan_id = orphan.id
            await db.commit()

    body = (await client.post(f'/api/v1/analysis/{created["id"]}/analyze', headers=headers)).json()
    assert body["run_id"] != orphan_id
    await _finish(body["run_id"])
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn) as db:
            assert (await db.get(AnalysisRun, orphan_id)).status == "failed"
            assert (await db.get(AnalysisRun, body["run_id"])).status == "converged"
