"""Background execution for ``POST /api/v1/analysis/{id}/analyze``.

Fact backfill plus the orchestrator can take minutes with live models, longer
than proxies keep a request open (2026-11-08: past 300 s). The endpoint now
creates the run, starts this job, and returns; clients poll ``/status``.

The deployment runs one uvicorn worker, so an in-process registry tracks
in-flight runs. A run left ``running`` without a registered task (a restart)
is marked ``failed`` by the next trigger. In showcase mode the job registers
with the per-guest task registry before it first runs, so erase cancels it
and refuses new work while pending, and it holds the bounded analysis slot.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_engine
from app.models.analysis import AnalysisRun

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

FAILED_STATUS = "failed"

# run_id -> task. Strong references keep tasks alive until they finish.
_tasks: dict[int, asyncio.Task] = {}


def is_in_flight(run_id: int) -> bool:
    task = _tasks.get(run_id)
    return task is not None and not task.done()


@asynccontextmanager
async def _session(schema_map: dict[str, Any]):
    async with get_engine().connect() as conn:
        conn = await conn.execution_options(schema_translate_map=schema_map)
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                # CancelledError included: roll back before erase purges rows.
                await session.rollback()
                raise


def _concept_services() -> tuple[Any, Any]:
    """Resolve FOLIO + embedding singletons; degrade if unavailable (e.g. tests)."""
    folio = embedding_service = None
    try:
        from app.services.folio.folio_service import get_folio

        folio = get_folio()
    except Exception as exc:  # pragma: no cover - startup-dependent
        logger.warning("FOLIO unavailable for extraction (%s)", type(exc).__name__)
    try:
        from app.services.embedding.service import EmbeddingService

        embedding_service = EmbeddingService.get_instance()
    except Exception as exc:  # pragma: no cover - startup-dependent
        logger.warning("EmbeddingService unavailable for extraction (%s)", type(exc).__name__)
    return folio, embedding_service


async def _execute(run_id: int, intake_id: int, llm_service: LLMService,
                   schema_map: dict[str, Any]) -> None:
    from app.services.analysis.orchestrator import AnalysisOrchestrator
    from app.services.analysis.stages.deadline_detect import DeadlineDetectStage
    from app.services.extraction import backfill
    from app.services.output.data_assembler import gather_safety_alerts

    folio, embedding_service = _concept_services()
    async with _session(schema_map) as db:
        # Backfill facts from ingested messages before analysis. Without this
        # the orchestrator's _load_facts() returns [] and analysis yields nothing.
        try:
            n_facts = await backfill.backfill_intake_facts(
                db, intake_id, llm_service, folio=folio, embedding_service=embedding_service
            )
            await db.commit()
            logger.info("Pre-analysis fact backfill created %d facts for intake %d",
                        n_facts, intake_id)
        except Exception as exc:
            await db.rollback()
            logger.warning("Pre-analysis fact backfill failed for intake %d (%s)",
                           intake_id, type(exc).__name__)

        run = await db.get(AnalysisRun, run_id)
        if run is None:  # erased or superseded while queued
            return
        orchestrator = AnalysisOrchestrator(
            db_session=db, llm_service=llm_service,
            folio=folio, embedding_service=embedding_service,
        )
        await orchestrator.run(intake_id=intake_id, session_id=0, run=run,
                               commit_progress=True)

        # Detect + hedge deadlines for this run; never fails the analysis. The
        # terminal status commits together with them, so a poller that sees a
        # terminal status also sees the deadlines.
        try:
            deadlines = await DeadlineDetectStage(
                llm_service=llm_service, db_session=db
            ).detect_and_persist(intake_id=intake_id, run_id=run.id)
            logger.info("Deadline detection produced %d deadlines for intake %d",
                        len(deadlines), intake_id)
        except Exception as exc:
            logger.warning("Deadline detection failed for intake %d (%s)",
                           intake_id, type(exc).__name__)

        # Decoupled safety screening (SAFETY CRITICAL, BUG-15): deterministic,
        # degrades gracefully. Log counts and severity tiers only -- protocol
        # names are a sensitive-category disclosure keyed to an intake.
        try:
            safety_alerts = await gather_safety_alerts(db, intake_id)
            if safety_alerts:
                logger.warning(
                    "Safety screening flagged %d protocol(s) for intake %d (severity: %s)",
                    len(safety_alerts), intake_id,
                    ", ".join(sorted({a.severity_tier for a in safety_alerts})),
                )
            else:
                logger.info("Safety screening produced 0 alerts for intake %d", intake_id)
        except Exception as exc:
            logger.warning("Safety screening failed for intake %d (%s)",
                           intake_id, type(exc).__name__)

        await db.commit()


async def _mark_failed(run_id: int, schema_map: dict[str, Any]) -> None:
    try:
        async with _session(schema_map) as db:
            await db.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run_id, AnalysisRun.status == "running")
                .values(status=FAILED_STATUS)
            )
            await db.commit()
    except Exception as exc:
        logger.error("Could not mark analysis run %d failed (%s)", run_id, type(exc).__name__)


async def run_analysis_job(
    run_id: int,
    intake_id: int,
    llm_service: LLMService,
    schema_map: dict[str, Any],
    *,
    user_id: int | None = None,
    app: Any = None,
    release: Callable[[], None] | None = None,
) -> None:
    """Run one analysis to a terminal status: converged, max_iterations, or failed."""
    try:
        async with AsyncExitStack() as stack:
            if user_id is not None:
                from app.db.retention import guest_activity

                # Keep the retention sweeper off a guest whose analysis runs.
                await stack.enter_async_context(guest_activity(user_id))
            if app is not None and release is not None:
                from app.showcase import reserved_analysis_slot

                await stack.enter_async_context(reserved_analysis_slot(app, release))
            await _execute(run_id, intake_id, llm_service, schema_map)
    except asyncio.CancelledError:
        # Erase or shutdown: erase purges the run; a restart leaves it for the
        # next trigger to mark failed.
        raise
    except Exception as exc:
        logger.error("Background analysis failed for intake %d run %d (%s)",
                     intake_id, run_id, type(exc).__name__)
        await _mark_failed(run_id, schema_map)


def start_analysis(
    run_id: int,
    intake_id: int,
    llm_service: LLMService,
    schema_map: dict[str, Any],
    *,
    user_id: int | None = None,
    app: Any = None,
    release: Callable[[], None] | None = None,
) -> asyncio.Task:
    """Start the job; showcase jobs register with the guest's task registry."""
    coro = run_analysis_job(run_id, intake_id, llm_service, schema_map,
                            user_id=user_id, app=app, release=release)
    if user_id is not None:
        from app.showcase import spawn_guest_task

        task = spawn_guest_task(user_id, coro)
    else:
        task = asyncio.get_running_loop().create_task(coro)
    _tasks[run_id] = task

    def _done(done: asyncio.Task) -> None:
        if _tasks.get(run_id) is done:
            del _tasks[run_id]
        if release is not None:
            release()  # idempotent; covers a task cancelled before it ran

    task.add_done_callback(_done)
    return task
