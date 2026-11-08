"""Demo-polish regressions: deployed commit, reference-date year anchoring,
structured deadline headings with de-duplication, and calm lapsed wording.

Live runs on 2026-11-08 showed Sonnet dating a "march 3rd" notice in a spring
2026 story as 2027-03-03, memo headings that were raw visitor quotes, and a
shouted "DEADLINE MAY HAVE PASSED".
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
from app.observability.health import deployed_commit
from app.services.analysis.stages.deadline_detect import DeadlineDetectStage
from app.services.deadline.dates import (
    anchor_event_date,
    has_explicit_year,
    reference_date_from,
    resolve_yearless_date,
)
from app.services.deadline.engine import LAPSED_NOTICE, compute_deadlines
from app.services.deadline.schemas import DeadlineEvent
from app.services.extraction.fact_extraction import date_anchor_instruction
from app.services.intake.session_service import IntakeSessionService
from app.services.output.deadline_display import (
    deadline_heading,
    deadline_label,
    dedupe_deadlines,
)
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


def _mock_llm_service():
    mock = MagicMock()
    mock.get_client_config.return_value = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "data_policy": "cloud_optout",
    }
    return mock


# ---- 1. Deployed commit on /health ----


def test_commit_falls_back_to_source_commit_when_git_sha_empty(monkeypatch):
    """Coolify injects GIT_COMMIT_SHA="" at runtime but sets SOURCE_COMMIT."""
    monkeypatch.setenv("GIT_COMMIT_SHA", "")
    monkeypatch.setenv("SOURCE_COMMIT", "a36eb88" + "0" * 33)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    assert deployed_commit() == "a36eb88" + "0" * 33


def test_commit_prefers_git_sha_and_is_none_when_all_empty(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
    monkeypatch.setenv("SOURCE_COMMIT", "def5678")
    assert deployed_commit() == "abc1234"
    monkeypatch.setenv("GIT_COMMIT_SHA", "  ")
    monkeypatch.setenv("SOURCE_COMMIT", "")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "")
    assert deployed_commit() is None


# ---- 2. Reference-date year anchoring ----


def test_march_3rd_resolves_to_same_year_not_next():
    ref = date(2026, 3, 10)
    assert resolve_yearless_date(3, 3, ref, past_event=True) == date(2026, 3, 3)
    assert resolve_yearless_date(3, 3, ref, past_event=False) == date(2026, 3, 3)
    # The model's 2027 pick for a posted notice rolls back to 2026.
    assert anchor_event_date(
        date(2027, 3, 3), "march 3rd, thats when the 14 day notice showed up",
        "notice_posted", ref,
    ) == date(2026, 3, 3)


def test_anchor_matches_the_live_story_on_demo_day():
    """Story told 2026-11-08: notice "march 3rd", hearing "april 1st" are 2026."""
    ref = date(2026, 11, 8)
    assert anchor_event_date(
        date(2027, 4, 1), "case is set for april 1st at 9am", "hearing", ref
    ) == date(2026, 4, 1)
    assert anchor_event_date(
        date(2027, 1, 18), "our HEAT went out for like 5 days, jan 18 to 23",
        "incident", ref,
    ) == date(2026, 1, 18)
    # An upcoming hearing a few weeks out stays in the future.
    assert anchor_event_date(
        date(2026, 12, 1), "my hearing is dec 1", "hearing", ref
    ) == date(2026, 12, 1)
    # A past date is never pushed forward.
    assert anchor_event_date(
        date(2025, 12, 1), "coughing so much worse since like december", "incident", ref
    ) == date(2025, 12, 1)
    # A year the visitor stated is never touched.
    assert anchor_event_date(
        date(2027, 7, 1), "when we moved in july 2027", "incident", ref
    ) == date(2027, 7, 1)
    assert has_explicit_year("served 3/3/26") and not has_explicit_year("march 3rd")


def test_reference_date_from_timestamps():
    assert reference_date_from(datetime(2026, 3, 10, 23, 0)) == date(2026, 3, 10)
    aware = datetime(2026, 3, 11, 1, 0, tzinfo=timezone.utc)
    assert reference_date_from(aware) == date(2026, 3, 11)
    assert isinstance(reference_date_from(None), date)


@pytest.mark.asyncio
async def test_prompt_carries_reference_date():
    """The fake model sees the reference date and the nearest-date instruction."""
    captured = {}

    class FakeClient:
        async def json_async(self, messages):
            captured["messages"] = messages
            return MagicMock(data={"events": []})

    llm = MagicMock()
    llm.create_client.return_value = FakeClient()
    stage = DeadlineDetectStage(llm_service=llm, db_session=MagicMock())
    await stage._call_llm_extraction("notice march 3rd", today=date(2026, 3, 10))
    system = captured["messages"][0]["content"]
    assert "TODAY'S DATE IS 2026-03-10" in system
    assert "NEAREST past-or-near-future" in system
    assert "2026-03-03, not 2027-03-03" in system
    assert "2026-03-10" in date_anchor_instruction(date(2026, 3, 10))


@pytest.mark.asyncio
async def test_stage_uses_message_date_and_corrects_drifted_year(db_session, intake_scaffold):
    """No explicit today: the visitor's message date anchors year + lapsed check."""
    svc = IntakeSessionService(db_session)
    msg = await svc.store_message(
        session_id=intake_scaffold["session"].id,
        sender_type="consumer",
        modality="text",
        content="march 3rd, thats when the 14 day notice to pay rent showed up taped to the door",
        party_id=intake_scaffold["party"].id,
    )
    msg.created_at = datetime(2026, 3, 10, 15, 0)
    await db_session.flush()

    drifted = {
        "events": [
            {
                "event_type": "notice_to_pay_or_quit",
                "raw_text": "march 3rd, thats when the 14 day notice showed up",
                "trigger": "notice_posted",
                "date": "2027-03-03",
                "window_days": 14,
            }
        ]
    }
    stage = DeadlineDetectStage(llm_service=_mock_llm_service(), db_session=db_session)
    with patch.object(
        DeadlineDetectStage, "_call_llm_extraction", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = drifted
        await stage.detect_and_persist(
            intake_id=intake_scaffold["intake"].id, run_id=intake_scaffold["run"].id
        )
        assert mock_call.await_args.kwargs["today"] == date(2026, 3, 10)

    rows = (
        await db_session.execute(
            select(Deadline).where(Deadline.run_id == intake_scaffold["run"].id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].trigger_date == date(2026, 3, 3)


# ---- 3 + 4. Structured headings, de-duplication, calm lapsed wording ----


def _ref(**kw):
    base = dict(
        event_text="march 3rd, thats when the 14 day notice showed up taped to the door",
        event_type="notice_to_vacate",
        trigger="notice_posted",
        trigger_date="2026-03-03",
        computed_date="2026-03-17",
        citation="The cure/vacate period stated in your written notice or lease.",
        computed=True,
        urgency="high",
        hedge="Estimated — confirm the exact date with the court or a lawyer.",
    )
    base.update(kw)
    return DeadlineRef(**base)


def _render(deadlines):
    context = OutputContext(
        intake_id=1, run_id=1, org_id=1, matter_title="Test Matter",
        generated_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
        gap_report=GapReport(), profile=LEGAL_AID_PROFILE, deadlines=deadlines,
    )
    return TemplateEngine().render_section("deadlines.md.j2", context, LEGAL_AID_PROFILE)


def test_heading_is_label_and_normalized_date_with_quote_in_body():
    md = _render([_ref()])
    assert "## ⚠️ Notice to vacate — March 3, 2026\n" in md
    assert '- **In your words:** "march 3rd, thats when the 14 day notice' in md
    assert "## ⚠️ march 3rd" not in md
    assert "- **Estimated deadline:** 2026-03-17" in md


def test_labels_cover_common_types_and_fallbacks():
    assert deadline_label("notice_to_pay_or_quit", "notice_posted") == "Notice to pay rent or quit"
    assert deadline_label("eviction_hearing", "hearing") == "Eviction hearing"
    assert deadline_label("", "hearing") == "Court hearing"
    assert deadline_label("mold_complaint", "") == "Mold complaint"
    assert deadline_label(None, None) == "Time-sensitive item"
    assert deadline_heading("", "incident", None, None) == "Incident"


def test_duplicate_events_on_same_date_render_once():
    hearing = dict(event_type="eviction_hearing", trigger="hearing",
                   trigger_date="2026-04-01", computed_date="2026-04-01")
    refs = [
        _ref(event_text="the case is set for april 1st at 9am", **hearing),
        _ref(event_text="papers say i have to show up april 1st", **hearing),
        _ref(event_text="i have texts from nov 12 and dec 2", event_type="incident",
             trigger="incident", trigger_date="2025-11-12", computed_date=None, computed=False),
        _ref(event_text="texts from nov 12 and dec 2", event_type="incident",
             trigger="incident", trigger_date="2025-11-12", computed_date=None, computed=False),
        # A different incident on the same day survives.
        _ref(event_text="the heat went out", event_type="incident",
             trigger="incident", trigger_date="2025-11-12", computed_date=None, computed=False),
    ]
    kept = dedupe_deadlines(refs)
    assert [r.event_text for r in kept] == [
        "the case is set for april 1st at 9am",
        "i have texts from nov 12 and dec 2",
        "the heat went out",
    ]
    md = _render(kept)
    assert md.count("Eviction hearing — April 1, 2026") == 1


def test_lapsed_uses_reference_date_and_calm_wording():
    ref_date = date(2026, 11, 8)
    [cd] = compute_deadlines(
        [DeadlineEvent(event_type="eviction_hearing", raw_text="case is set for april 1st at halden county court",
                       trigger="hearing", date=date(2026, 4, 1))],
        today=ref_date,
    )
    assert cd.urgency == "lapsed"
    assert cd.hedge.startswith(LAPSED_NOTICE)
    assert "Compared with 2026-11-08" in cd.hedge
    assert "ALREADY PASSED" not in cd.hedge and "WARNING" not in cd.hedge
    # Before the hearing it is not lapsed.
    [early] = compute_deadlines(
        [DeadlineEvent(event_type="eviction_hearing", trigger="hearing", raw_text="court april 1st",
                       date=date(2026, 4, 1))],
        today=date(2026, 3, 22),
    )
    assert early.urgency != "lapsed"

    md = _render([_ref(event_type="eviction_hearing", trigger="hearing",
                       trigger_date=cd.trigger_date.isoformat(),
                       computed_date=cd.computed_date.isoformat(),
                       urgency="lapsed", hedge=cd.hedge)])
    assert "## ⛔ Eviction hearing — April 1, 2026 (may have passed)\n" in md
    assert "This date may already have passed — check with the court." in md
    assert "MAY HAVE PASSED" not in md


@pytest.mark.asyncio
async def test_results_endpoint_returns_memo_heading_lapsed_and_drops_duplicates(
    db_session, intake_scaffold
):
    """The showcase page reads /results: it gets the memo's heading, the
    engine's reference-date lapsed flag, and the memo's de-duplication."""
    from app.routers.analysis import get_analysis_results

    intake, run = intake_scaffold["intake"], intake_scaffold["run"]
    common = dict(intake_id=intake.id, run_id=run.id, jurisdiction="Minnesota")
    db_session.add_all(
        [
            Deadline(
                event_text="march 3rd, thats when the 14 day notice showed up taped to the door",
                event_type="notice_to_vacate", trigger="notice_posted",
                trigger_date=date(2026, 3, 3), computed_date=date(2026, 3, 17),
                computed=True, urgency="lapsed", hedge="h", **common,
            ),
            Deadline(
                event_text="the 14 day notice showed up taped to the door",
                event_type="notice_to_vacate", trigger="notice_posted",
                trigger_date=date(2026, 3, 3), computed_date=date(2026, 3, 17),
                computed=True, urgency="lapsed", hedge="h", **common,
            ),
            Deadline(
                event_text="court date is april 1",
                event_type="eviction_hearing", trigger="hearing",
                trigger_date=date(2026, 4, 1), computed_date=date(2026, 4, 1),
                computed=True, urgency="high", hedge="h", **common,
            ),
        ]
    )
    await db_session.flush()

    body = await get_analysis_results(intake.id, db=db_session, user=MagicMock())
    deadlines = body["deadlines"]

    assert [d["heading"] for d in deadlines] == [
        "Notice to vacate — March 3, 2026",
        "Eviction hearing — April 1, 2026",
    ]
    assert [d["lapsed"] for d in deadlines] == [True, False]
    # Existing fields stay for other consumers.
    first = deadlines[0]
    assert first["event_text"].startswith("march 3rd")
    assert first["computed_date"] == "2026-03-17"
    assert first["urgency"] == "lapsed"
