"""Tests for deadline detection persistence + surfacing (v1 "detect + hedge").

- DeadlineDetectStage: mock the LLM event extraction, assert Deadline rows are
  persisted for the run, and that DataAssembler surfaces them on OutputContext.
- Memo render: a DeadlineRef list produces the top hedged section (no DB/LLM).
"""

import os
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.db.base import SharedBase, TenantBase, convention
from app.models.analysis import AnalysisRun, Deadline
from app.models.intake import Intake, IntakeParty, IntakeSession
from app.services.analysis.stages.deadline_detect import DeadlineDetectStage
from app.services.intake.session_service import IntakeSessionService
from app.services.output.data_assembler import DataAssembler
from app.services.output.schemas import (
    LEGAL_AID_PROFILE,
    DeadlineRef,
    GapReport,
    OutputContext,
)
from app.services.output.template_engine import TemplateEngine


# ---- Fixtures (mirror test_backfill.py) ----


@pytest.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    import app.models  # noqa: F401

    _tenant_meta = MetaData(naming_convention=convention)
    _shared_meta = MetaData(naming_convention=convention)
    for table in TenantBase.metadata.tables.values():
        table.to_metadata(_tenant_meta, schema=None)
    for table in SharedBase.metadata.tables.values():
        table.to_metadata(_shared_meta, schema=None)

    async with engine.begin() as conn:
        await conn.run_sync(_shared_meta.create_all)
        await conn.run_sync(_tenant_meta.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(_tenant_meta.drop_all)
        await conn.run_sync(_shared_meta.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    async with test_engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()


@pytest.fixture
async def intake_scaffold(db_session):
    intake = Intake(org_id=1, created_by_user_id=1, session_mode="multi_session", status="active")
    db_session.add(intake)
    await db_session.flush()

    party = IntakeParty(intake_id=intake.id, user_id=1, role_in_intake="primary")
    db_session.add(party)
    await db_session.flush()

    intake_session = IntakeSession(intake_id=intake.id, status="active")
    db_session.add(intake_session)
    await db_session.flush()

    run = AnalysisRun(intake_id=intake.id, status="running", trigger_type="manual")
    db_session.add(run)
    await db_session.flush()

    return {"intake": intake, "party": party, "session": intake_session, "run": run}


def _mock_llm_service():
    mock = MagicMock()
    mock.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }
    return mock


def _events_json():
    """Two persona events: MN custody service (+30) and lapsed asylum entry (+1yr)."""
    return {
        "events": [
            {
                "event_type": "custody_response",
                "raw_text": "I was served with custody papers on June 15, 2026.",
                "trigger": "served",
                "date": "2026-06-15",
                "jurisdiction_hint": "MN",
            },
            {
                "event_type": "asylum_entry",
                "raw_text": "I entered the U.S. on August 14, 2019.",
                "trigger": "entry",
                "date": "2019-08-14",
                "jurisdiction_hint": "US",
            },
        ]
    }


# ---- Detection + persistence ----


@pytest.mark.asyncio
async def test_detect_persists_deadlines(db_session, intake_scaffold):
    """Mocked LLM events -> Deadline rows persisted with correct computed dates."""
    svc = IntakeSessionService(db_session)
    await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="consumer",
        modality="text",
        content="I was served custody papers on June 15, 2026 in Minnesota.",
        party_id=intake_scaffold["party"].id,
    )

    intake_id = intake_scaffold["intake"].id
    run_id = intake_scaffold["run"].id

    stage = DeadlineDetectStage(llm_service=_mock_llm_service(), db_session=db_session)
    with patch.object(
        DeadlineDetectStage, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = _events_json()
        created = await stage.detect_and_persist(
            intake_id=intake_id, run_id=run_id, jurisdiction="MN", today=date(2026, 7, 5)
        )

    assert len(created) == 2

    rows = (
        await db_session.execute(select(Deadline).where(Deadline.run_id == run_id))
    ).scalars().all()
    by_rule = {r.rule_id: r for r in rows}

    assert by_rule["mn_family_response_30d"].computed_date == date(2026, 7, 15)
    assert by_rule["mn_family_response_30d"].computed is True

    asylum = by_rule["asylum_one_year"]
    assert asylum.computed_date == date(2020, 8, 14)
    assert asylum.urgency == "lapsed"
    assert "ALREADY PASSED" in asylum.hedge


@pytest.mark.asyncio
async def test_detect_degrades_on_llm_failure(db_session, intake_scaffold):
    """An LLM failure yields zero deadlines and never raises."""
    svc = IntakeSessionService(db_session)
    await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="consumer",
        modality="text",
        content="Some narrative with a date 2026-06-15.",
        party_id=intake_scaffold["party"].id,
    )

    stage = DeadlineDetectStage(llm_service=_mock_llm_service(), db_session=db_session)
    with patch.object(
        DeadlineDetectStage, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.side_effect = RuntimeError("LLM down")
        created = await stage.detect_and_persist(
            intake_id=intake_scaffold["intake"].id,
            run_id=intake_scaffold["run"].id,
            today=date(2026, 7, 5),
        )

    assert created == []


@pytest.mark.asyncio
async def test_assembler_surfaces_deadlines(db_session, intake_scaffold):
    """DataAssembler pulls Deadline rows into OutputContext.deadlines, sorted."""
    intake_id = intake_scaffold["intake"].id
    run_id = intake_scaffold["run"].id

    db_session.add_all([
        Deadline(
            intake_id=intake_id, run_id=run_id, event_text="Custody response",
            trigger="served", trigger_date=date(2026, 6, 15),
            computed_date=date(2026, 7, 15), rule_id="mn_family_response_30d",
            citation="Minn. Gen. R. Prac. 303.03", computed=True, urgency="high",
            hedge="Estimated — confirm the exact date with the court or a lawyer.",
            jurisdiction="MN",
        ),
        Deadline(
            intake_id=intake_id, run_id=run_id, event_text="Asylum filing",
            trigger="entry", trigger_date=date(2019, 8, 14),
            computed_date=date(2020, 8, 14), rule_id="asylum_one_year",
            citation="INA § 208", computed=True, urgency="lapsed",
            hedge="WARNING already passed. Estimated — confirm the exact date.",
            jurisdiction="US",
        ),
    ])
    await db_session.flush()

    context = await DataAssembler(db_session).assemble(run_id, intake_id, LEGAL_AID_PROFILE)

    assert len(context.deadlines) == 2
    # lapsed sorts first
    assert context.deadlines[0].urgency == "lapsed"
    assert context.deadlines[0].computed_date == "2020-08-14"


# ---- Memo render ----


def test_memo_renders_top_hedged_deadline_section():
    """render_full puts the hedged Deadlines section first (before CIRAC)."""
    context = OutputContext(
        intake_id=1,
        run_id=1,
        org_id=1,
        matter_title="Test Matter",
        generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        gap_report=GapReport(),
        profile=LEGAL_AID_PROFILE,
        deadlines=[
            DeadlineRef(
                event_text="Custody response due",
                trigger="served",
                trigger_date="2026-06-15",
                computed_date="2026-07-15",
                citation="Minn. Gen. R. Prac. 303.03",
                computed=True,
                urgency="high",
                hedge="Estimated — confirm the exact date with the court or a lawyer.",
                jurisdiction="MN",
            ),
        ],
    )
    md = TemplateEngine().render_full(context, LEGAL_AID_PROFILE)

    assert "Deadlines & Time-Sensitive Items" in md
    # Section appears before the CIRAC memo content.
    assert md.index("Deadlines & Time-Sensitive Items") < md.index("Test Matter")
    assert "2026-07-15" in md
    assert "confirm the exact date" in md
    assert "Minn. Gen. R. Prac. 303.03" in md
