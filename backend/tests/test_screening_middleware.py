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


# ---------------------------------------------------------------------------
# WebSocket integration tests (Task 2)
# ---------------------------------------------------------------------------


def _make_engine_mock():
    """Create a properly-configured async engine mock for _handle_text_message tests.

    The async with engine.connect() chain requires a proper async context manager.
    """
    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_conn = MagicMock()
    mock_conn.execution_options = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_connect_ctx = MagicMock()
    mock_connect_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_engine.connect.return_value = mock_connect_ctx

    return mock_engine, mock_conn, mock_session


def _make_standard_patches(screening_result, extra_patches=None):
    """Return a dict of patch targets for _handle_text_message tests."""
    patches = {
        "screen": patch("app.routers.intake.screen_message_fast", new_callable=AsyncMock, return_value=screening_result),
        "persist": patch("app.routers.intake.persist_screening_event", new_callable=AsyncMock),
        "queue_elevated": patch("app.routers.intake.queue_elevated_screening", new_callable=AsyncMock),
        "explore_queue": patch("app.routers.intake.add_to_exploration_queue", new_callable=AsyncMock),
        "session_cls": patch("app.routers.intake.AsyncSession"),
        "svc_cls": patch("app.routers.intake.IntakeSessionService"),
        "conv_cls": patch("app.routers.intake.ConversationService"),
        "normalize": patch("app.routers.intake.normalize_text"),
    }
    if extra_patches:
        patches.update(extra_patches)
    return patches


def _setup_session_and_svc_mocks(mock_session, mock_patches):
    """Wire up AsyncSession and IntakeSessionService mocks."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_patches["session_cls"].return_value = ctx

    mock_svc_instance = AsyncMock()
    mock_message = MagicMock()
    mock_message.id = 1
    mock_message.sequence_number = 1
    mock_svc_instance.store_message = AsyncMock(return_value=mock_message)
    mock_patches["svc_cls"].return_value = mock_svc_instance

    mock_conv_instance = AsyncMock()
    mock_conv_instance.generate_response = AsyncMock(return_value="I understand.")
    mock_patches["conv_cls"].return_value = mock_conv_instance

    return mock_svc_instance, mock_conv_instance


@pytest.mark.asyncio
async def test_handle_text_message_calls_screening():
    """_handle_text_message calls screen_message_fast before processing the message."""
    from app.routers.intake import _handle_text_message

    mock_engine, mock_conn, mock_session = _make_engine_mock()
    empty_result = ScreeningResult()
    patches = _make_standard_patches(empty_result)

    entered = {}
    with patches["screen"] as mock_screen, \
         patches["persist"], patches["queue_elevated"], patches["explore_queue"], \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            AsyncMock(), 1, 10, {"content": "test message", "party_id": None}, mock_engine
        )

        mock_screen.assert_called_once()
        call_kwargs = mock_screen.call_args
        assert call_kwargs[1].get("content") == "test message" or (call_kwargs[0] and call_kwargs[0][0] == "test message")


@pytest.mark.asyncio
async def test_critical_trigger_sends_safety_alert():
    """Critical screening trigger sends safety_alert WebSocket message to client."""
    from app.routers.intake import _handle_text_message

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()

    critical_result = ScreeningResult(
        triggered_protocols=[
            {"protocol_id": 1, "severity_tier": "critical", "version_id": 100,
             "trigger_type": "keyword", "matched_terms": ["domestic violence"]},
        ],
        has_critical=True,
        safety_resources=[{"name": "National DV Hotline", "phone": "1-800-799-7233"}],
        mandatory_questions=[{"question_id": "dv-q1", "text": "Are you safe?", "is_mandatory": True}],
    )
    patches = _make_standard_patches(critical_result)

    with patches["screen"], patches["persist"], patches["queue_elevated"], patches["explore_queue"], \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            mock_ws, 1, 10,
            {"content": "my partner has domestic violence issues", "party_id": None},
            mock_engine,
        )

        send_calls = mock_ws.send_json.call_args_list
        safety_alerts = [c for c in send_calls if c[0][0].get("type") == "safety_alert"]
        assert len(safety_alerts) >= 1
        alert = safety_alerts[0][0][0]
        assert alert["severity"] == "critical"
        assert len(alert["resources"]) > 0


@pytest.mark.asyncio
async def test_elevated_trigger_persists_queued_no_ws_alert():
    """Elevated screening trigger persists queued ScreeningEvent, no immediate WebSocket message."""
    from app.routers.intake import _handle_text_message

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()

    elevated_result = ScreeningResult(
        triggered_protocols=[
            {"protocol_id": 2, "severity_tier": "elevated", "version_id": 200,
             "trigger_type": "keyword", "matched_terms": ["stalking"]},
        ],
        has_elevated=True,
    )
    patches = _make_standard_patches(elevated_result)

    with patches["screen"], patches["persist"], \
         patches["queue_elevated"] as mock_queue, \
         patches["explore_queue"], \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            mock_ws, 1, 10, {"content": "someone has been stalking me", "party_id": None},
            mock_engine,
        )

        mock_queue.assert_called_once()
        send_calls = mock_ws.send_json.call_args_list
        safety_alerts = [c for c in send_calls if c[0][0].get("type") == "safety_alert"]
        assert len(safety_alerts) == 0


@pytest.mark.asyncio
async def test_advisory_trigger_folds_to_exploration():
    """Advisory screening trigger persists exploration queue entry, no immediate WebSocket message."""
    from app.routers.intake import _handle_text_message

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()

    advisory_result = ScreeningResult(
        triggered_protocols=[
            {"protocol_id": 3, "severity_tier": "advisory", "version_id": 300,
             "trigger_type": "keyword", "matched_terms": ["eviction"]},
        ],
        has_advisory=True,
    )
    patches = _make_standard_patches(advisory_result)

    with patches["screen"], patches["persist"], patches["queue_elevated"], \
         patches["explore_queue"] as mock_explore, \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            mock_ws, 1, 10, {"content": "I'm facing eviction", "party_id": None},
            mock_engine,
        )

        mock_explore.assert_called_once()


@pytest.mark.asyncio
async def test_message_processing_continues_after_screening():
    """Message processing continues normally after screening -- store, normalize, ack, LLM response."""
    from app.routers.intake import _handle_text_message

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()

    critical_result = ScreeningResult(
        triggered_protocols=[{"protocol_id": 1, "severity_tier": "critical"}],
        has_critical=True,
        safety_resources=[{"name": "DV Hotline"}],
        mandatory_questions=[{"text": "Are you safe?"}],
    )
    patches = _make_standard_patches(critical_result)

    with patches["screen"], patches["persist"], patches["queue_elevated"], patches["explore_queue"], \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            mock_ws, 1, 10, {"content": "domestic violence situation", "party_id": None},
            mock_engine,
        )

        send_calls = mock_ws.send_json.call_args_list
        ack_messages = [c for c in send_calls if c[0][0].get("type") == "message_ack"]
        assert len(ack_messages) == 1
        sys_messages = [c for c in send_calls if c[0][0].get("type") == "system_message"]
        assert len(sys_messages) == 1


@pytest.mark.asyncio
async def test_screening_does_not_block_ack():
    """Screening does NOT block message acknowledgment -- safety_alert sent in addition to message_ack."""
    from app.routers.intake import _handle_text_message

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()

    critical_result = ScreeningResult(
        triggered_protocols=[{"protocol_id": 1, "severity_tier": "critical"}],
        has_critical=True,
        safety_resources=[{"name": "DV Hotline"}],
        mandatory_questions=[],
    )
    patches = _make_standard_patches(critical_result)

    with patches["screen"], patches["persist"], patches["queue_elevated"], patches["explore_queue"], \
         patches["session_cls"] as mock_session_cls, \
         patches["svc_cls"] as mock_svc_cls, \
         patches["conv_cls"] as mock_conv_cls, \
         patches["normalize"]:

        entered_patches = {"session_cls": mock_session_cls, "svc_cls": mock_svc_cls, "conv_cls": mock_conv_cls}
        _setup_session_and_svc_mocks(mock_session, entered_patches)

        await _handle_text_message(
            mock_ws, 1, 10, {"content": "domestic violence", "party_id": None},
            mock_engine,
        )

        send_calls = mock_ws.send_json.call_args_list
        types_sent = [c[0][0].get("type") for c in send_calls]
        assert "safety_alert" in types_sent
        assert "message_ack" in types_sent


@pytest.mark.asyncio
async def test_transcript_approve_also_screens():
    """Screening runs on transcript_approve handler (voice treated same as text)."""
    from app.routers.intake import _handle_transcript_approve

    mock_ws = AsyncMock()
    mock_engine, mock_conn, mock_session = _make_engine_mock()
    empty_result = ScreeningResult()

    mock_transcript = MagicMock()
    mock_transcript.text_encrypted = b"My partner hit me last night"
    mock_transcript.status = "pending_review"

    mock_recording = MagicMock()
    mock_recording.id = 5
    mock_recording.message_id = 10

    mock_message = MagicMock()
    mock_message.id = 10
    mock_message.sequence_number = 1
    mock_message.party_id = None

    mock_result1 = MagicMock()
    mock_result1.scalar_one.return_value = mock_transcript
    mock_result2 = MagicMock()
    mock_result2.scalar_one.return_value = mock_recording
    mock_result3 = MagicMock()
    mock_result3.scalar_one.return_value = mock_message

    mock_session.execute = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])

    with patch("app.routers.intake.screen_message_fast", new_callable=AsyncMock, return_value=empty_result) as mock_screen, \
         patch("app.routers.intake.persist_screening_event", new_callable=AsyncMock), \
         patch("app.routers.intake.queue_elevated_screening", new_callable=AsyncMock), \
         patch("app.routers.intake.add_to_exploration_queue", new_callable=AsyncMock), \
         patch("app.routers.intake.AsyncSession") as mock_session_cls, \
         patch("app.routers.intake.IntakeSessionService") as mock_svc_cls, \
         patch("app.routers.intake.ConversationService") as mock_conv_cls, \
         patch("app.routers.intake.normalize_text"), \
         patch("app.routers.intake.process_message", new_callable=AsyncMock):

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = ctx

        mock_svc_instance = AsyncMock()
        sys_msg = MagicMock()
        sys_msg.id = 11
        mock_svc_instance.store_message = AsyncMock(return_value=sys_msg)
        mock_svc_cls.return_value = mock_svc_instance

        mock_conv_instance = AsyncMock()
        mock_conv_instance.generate_response = AsyncMock(return_value="I understand.")
        mock_conv_cls.return_value = mock_conv_instance

        await _handle_transcript_approve(
            mock_ws, 1, 10, {"recording_id": 5}, mock_engine
        )

        mock_screen.assert_called_once()


@pytest.mark.asyncio
async def test_no_protocols_active_screening_skipped_gracefully():
    """When no protocols are active for org, screening is skipped gracefully."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    result = await screen_message_fast(
        content="My partner has domestic violence issues",
        session_id=1,
        db_session=db_session,
        active_protocols=[],  # No active protocols
    )
    assert result.has_critical is False
    assert result.has_elevated is False
    assert result.has_advisory is False
    assert len(result.triggered_protocols) == 0


@pytest.mark.asyncio
async def test_dv_keyword_triggers_safety_alert_with_hotline():
    """DV keyword in text_message triggers safety_alert with National DV Hotline per D-11/EXPLORE-09."""
    from app.services.screening.middleware import screen_message_fast

    db_session = AsyncMock()
    # Use only the DV protocol
    result = await screen_message_fast(
        content="I am a victim of domestic violence and need help",
        session_id=1,
        db_session=db_session,
        active_protocols=[(DV_ACTIVATION, DV_VERSION)],
    )
    assert result.has_critical is True
    assert any("National DV Hotline" in r.get("name", "") for r in result.safety_resources)
    assert any("1-800-799-7233" in r.get("phone", "") for r in result.safety_resources)
