"""Tests for per-message safety screening middleware.

Tests the screen_message_fast function, priority-based dispatch helpers,
ScreeningEvent persistence, and performance benchmarks.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exploration.schemas import ScreeningResult


# ---------------------------------------------------------------------------
# Helpers: build mock protocol fixtures
# ---------------------------------------------------------------------------


def _make_activation(protocol_id: int) -> SimpleNamespace:
    """Create a mock OrgProtocolActivation."""
    return SimpleNamespace(protocol_id=protocol_id)


def _make_version(
    version_id: int,
    trigger_conditions: dict,
    questions: list | None = None,
    escalation_actions: dict | None = None,
    safety_resources: dict | None = None,
    severity_tier: str = "advisory",
    protocol_name: str = "Test Protocol",
) -> SimpleNamespace:
    """Create a mock ProtocolVersion with _severity_tier and _protocol_name attrs."""
    return SimpleNamespace(
        id=version_id,
        trigger_conditions_json=trigger_conditions,
        questions_json=questions or [],
        escalation_actions_json=escalation_actions or {},
        safety_resources_json=safety_resources,
        _severity_tier=severity_tier,
        _protocol_name=protocol_name,
    )


# DV protocol -- critical
DV_ACTIVATION = _make_activation(1)
DV_VERSION = _make_version(
    version_id=100,
    trigger_conditions={
        "keywords": ["domestic violence", "hit me", "abusive partner", "restraining order"],
        "regex_patterns": [r"\b(dv|ipv)\b"],
    },
    questions=[
        {
            "question_id": "dv-q1",
            "text": "Are you safe right now?",
            "text_transparent": "We ask everyone about safety because many people in legal situations also experience violence at home. Are you safe right now?",
            "is_mandatory": True,
            "priority": 1,
        },
        {
            "question_id": "dv-q2",
            "text": "Do you have a safe place to go?",
            "text_transparent": "Having a safety plan is important. Do you have a safe place to go if needed?",
            "is_mandatory": True,
            "priority": 2,
        },
        {
            "question_id": "dv-q3",
            "text": "Have you contacted law enforcement?",
            "text_transparent": "Some people find it helpful to involve authorities. Have you contacted law enforcement?",
            "is_mandatory": False,
            "priority": 3,
        },
    ],
    escalation_actions={
        "immediate_resources": [
            {"name": "National DV Hotline", "phone": "1-800-799-7233", "url": "https://www.thehotline.org"},
        ],
    },
    safety_resources={
        "hotlines": [
            {"name": "National DV Hotline", "phone": "1-800-799-7233"},
        ],
    },
    severity_tier="critical",
    protocol_name="Domestic Violence / IPV",
)

# Stalking protocol -- elevated
STALK_ACTIVATION = _make_activation(2)
STALK_VERSION = _make_version(
    version_id=200,
    trigger_conditions={
        "keywords": ["stalking", "following me", "tracking my phone"],
        "regex_patterns": [],
    },
    questions=[
        {
            "question_id": "stalk-q1",
            "text": "Has someone been following or monitoring you?",
            "text_transparent": "Many people dealing with legal issues also experience unwanted surveillance. Has someone been following or monitoring you?",
            "is_mandatory": False,
            "priority": 1,
        },
    ],
    escalation_actions={},
    safety_resources=None,
    severity_tier="elevated",
    protocol_name="Stalking / Harassment",
)

# Housing instability protocol -- advisory
HOUSING_ACTIVATION = _make_activation(3)
HOUSING_VERSION = _make_version(
    version_id=300,
    trigger_conditions={
        "keywords": ["eviction", "homeless", "housing instability"],
        "regex_patterns": [],
    },
    questions=[],
    escalation_actions={},
    safety_resources=None,
    severity_tier="advisory",
    protocol_name="Housing Instability",
)


ALL_PROTOCOLS = [
    (DV_ACTIVATION, DV_VERSION),
    (STALK_ACTIVATION, STALK_VERSION),
    (HOUSING_ACTIVATION, HOUSING_VERSION),
]


# ---------------------------------------------------------------------------
# screen_message_fast tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_dv_keywords_critical():
    """screen_message_fast returns has_critical=True when DV keywords detected."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has been abusive and hit me last week",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert isinstance(result, ScreeningResult)
    assert result.has_critical is True


@pytest.mark.asyncio
async def test_screen_stalking_elevated():
    """screen_message_fast returns has_elevated=True for stalking keywords."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="Someone has been stalking me and following me everywhere",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert result.has_elevated is True


@pytest.mark.asyncio
async def test_screen_housing_advisory():
    """screen_message_fast returns has_advisory=True for housing instability keywords."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="I'm facing eviction from my apartment and might become homeless",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert result.has_advisory is True


@pytest.mark.asyncio
async def test_screen_no_triggers():
    """screen_message_fast returns all False when no triggers match."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="I need help with a contract dispute with my employer",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert result.has_critical is False
    assert result.has_elevated is False
    assert result.has_advisory is False
    assert len(result.triggered_protocols) == 0


@pytest.mark.asyncio
async def test_screen_critical_returns_safety_resources():
    """screen_message_fast returns safety_resources from critical protocol."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has domestic violence issues and hit me",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert len(result.safety_resources) > 0
    resource_names = [r.get("name") for r in result.safety_resources]
    assert "National DV Hotline" in resource_names


@pytest.mark.asyncio
async def test_screen_critical_returns_mandatory_questions():
    """screen_message_fast returns mandatory_questions from critical protocol."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has domestic violence issues and hit me",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
    )
    assert len(result.mandatory_questions) > 0
    # Only mandatory questions should be included
    for q in result.mandatory_questions:
        assert q.get("is_mandatory") is True


@pytest.mark.asyncio
async def test_screen_transparency_true_uses_text_transparent():
    """screen_message_fast with question_transparency=True returns text_transparent variant."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has domestic violence issues and hit me",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
        question_transparency=True,
    )
    assert len(result.mandatory_questions) > 0
    for q in result.mandatory_questions:
        assert "We ask everyone" in q.get("text", "") or "safety" in q.get("text", "").lower()


@pytest.mark.asyncio
async def test_screen_transparency_false_uses_plain_text():
    """screen_message_fast with question_transparency=False returns plain text variant."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has domestic violence issues and hit me",
        session_id=1,
        db_session=db_session,
        active_protocols=ALL_PROTOCOLS,
        question_transparency=False,
    )
    assert len(result.mandatory_questions) > 0
    # Plain text questions are shorter and don't have the transparency framing
    first_q = result.mandatory_questions[0]
    assert first_q.get("text") == "Are you safe right now?"


# ---------------------------------------------------------------------------
# persist_screening_event tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_screening_event_creates_record(async_engine):
    """persist_screening_event creates a ScreeningEvent record for a triggered protocol."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.screening import ScreeningEvent
    from app.services.screening.middleware import persist_screening_event

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            triggered = {
                "protocol_id": 1,
                "protocol_name": "DV Protocol",
                "severity_tier": "critical",
                "version_id": 100,
                "trigger_type": "keyword",
                "matched_terms": ["domestic violence"],
            }
            event = await persist_screening_event(
                db_session=db_session,
                session_id=42,
                triggered=triggered,
                action_taken="immediate_alert",
            )
            await db_session.commit()

            assert event is not None
            assert event.session_id == 42
            assert event.protocol_id == 1
            assert event.severity_tier == "critical"
            assert event.action_taken == "immediate_alert"
            assert "domestic violence" in event.trigger_details_json.get("matched_terms", [])


@pytest.mark.asyncio
async def test_persist_event_action_critical(async_engine):
    """persist_screening_event sets action_taken='immediate_alert' for critical."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.screening.middleware import persist_screening_event

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            triggered = {
                "protocol_id": 1,
                "severity_tier": "critical",
                "version_id": 100,
                "trigger_type": "keyword",
                "matched_terms": ["hit me"],
            }
            event = await persist_screening_event(db_session, 1, triggered, "immediate_alert")
            assert event.action_taken == "immediate_alert"


@pytest.mark.asyncio
async def test_persist_event_action_elevated(async_engine):
    """persist_screening_event sets action_taken='queued' for elevated."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.screening.middleware import persist_screening_event

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            triggered = {
                "protocol_id": 2,
                "severity_tier": "elevated",
                "version_id": 200,
                "trigger_type": "keyword",
                "matched_terms": ["stalking"],
            }
            event = await persist_screening_event(db_session, 1, triggered, "queued")
            assert event.action_taken == "queued"


@pytest.mark.asyncio
async def test_persist_event_action_advisory(async_engine):
    """persist_screening_event sets action_taken='folded_to_exploration' for advisory."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.screening.middleware import persist_screening_event

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            triggered = {
                "protocol_id": 3,
                "severity_tier": "advisory",
                "version_id": 300,
                "trigger_type": "keyword",
                "matched_terms": ["eviction"],
            }
            event = await persist_screening_event(db_session, 1, triggered, "folded_to_exploration")
            assert event.action_taken == "folded_to_exploration"


# ---------------------------------------------------------------------------
# build_safety_alert_message tests
# ---------------------------------------------------------------------------


def test_build_safety_alert_message():
    """build_safety_alert_message builds correct WebSocket safety_alert message format."""
    from app.services.screening.middleware import build_safety_alert_message

    screening_result = ScreeningResult(
        triggered_protocols=[{"protocol_id": 1, "severity_tier": "critical"}],
        has_critical=True,
        safety_resources=[
            {"name": "National DV Hotline", "phone": "1-800-799-7233"},
        ],
        mandatory_questions=[
            {"question_id": "dv-q1", "text": "Are you safe right now?", "is_mandatory": True},
        ],
    )

    msg = build_safety_alert_message(screening_result)
    assert msg["type"] == "safety_alert"
    assert msg["severity"] == "critical"
    assert len(msg["resources"]) == 1
    assert msg["resources"][0]["name"] == "National DV Hotline"
    assert len(msg["questions"]) == 1
    assert "safe" in msg["message"].lower()


# ---------------------------------------------------------------------------
# queue_elevated_screening tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_elevated_screening(async_engine):
    """queue_elevated_screening persists queued ScreeningEvent for elevated triggers."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.screening import ScreeningEvent
    from app.services.screening.middleware import queue_elevated_screening

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            elevated_triggers = [
                {
                    "protocol_id": 2,
                    "severity_tier": "elevated",
                    "version_id": 200,
                    "trigger_type": "keyword",
                    "matched_terms": ["stalking"],
                },
            ]
            await queue_elevated_screening(db_session, 42, elevated_triggers)
            await db_session.commit()

            result = await db_session.execute(
                select(ScreeningEvent).where(
                    ScreeningEvent.session_id == 42,
                    ScreeningEvent.action_taken == "queued",
                )
            )
            events = result.scalars().all()
            assert len(events) == 1
            assert events[0].severity_tier == "elevated"


# ---------------------------------------------------------------------------
# add_to_exploration_queue tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_to_exploration_queue(async_engine):
    """add_to_exploration_queue stores exploration queue entry for advisory triggers."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.screening import ScreeningEvent
    from app.services.screening.middleware import add_to_exploration_queue

    async with async_engine.connect() as conn:
        conn = await conn.execution_options(schema_translate_map={"tenant": None, "shared": None})
        async with AsyncSession(bind=conn, expire_on_commit=False) as db_session:
            advisory_triggers = [
                {
                    "protocol_id": 3,
                    "severity_tier": "advisory",
                    "version_id": 300,
                    "trigger_type": "keyword",
                    "matched_terms": ["eviction"],
                },
            ]
            await add_to_exploration_queue(db_session, 99, advisory_triggers)
            await db_session.commit()

            result = await db_session.execute(
                select(ScreeningEvent).where(
                    ScreeningEvent.session_id == 99,
                    ScreeningEvent.action_taken == "folded_to_exploration",
                )
            )
            events = result.scalars().all()
            assert len(events) == 1
            assert events[0].severity_tier == "advisory"


# ---------------------------------------------------------------------------
# Performance benchmark
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_message_fast_performance():
    """screen_message_fast completes in <50ms with 10 active protocols (benchmark)."""
    from app.services.screening.middleware import screen_message_fast

    # Build 10 protocols with various triggers
    protocols = []
    for i in range(10):
        act = _make_activation(i + 10)
        ver = _make_version(
            version_id=1000 + i,
            trigger_conditions={
                "keywords": [f"keyword_{i}_a", f"keyword_{i}_b", f"keyword_{i}_c"],
                "regex_patterns": [rf"\bpattern_{i}\b"],
            },
            severity_tier=["critical", "elevated", "advisory"][i % 3],
            protocol_name=f"Benchmark Protocol {i}",
        )
        protocols.append((act, ver))

    db_session = AsyncMock()
    content = "This is a normal message about my employment dispute and contract issues"

    # Warm up
    await screen_message_fast(
        content=content,
        session_id=1,
        db_session=db_session,
        active_protocols=protocols,
    )

    # Benchmark: run 100 times
    start = time.perf_counter()
    for _ in range(100):
        await screen_message_fast(
            content=content,
            session_id=1,
            db_session=db_session,
            active_protocols=protocols,
        )
    elapsed = time.perf_counter() - start
    median_ms = (elapsed / 100) * 1000

    assert median_ms < 50, f"Median screening time {median_ms:.2f}ms exceeds 50ms target"
