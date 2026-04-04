"""Tests for screening protocol DB models, TriggerMatcher, Pydantic schemas,
ProtocolService CRUD, admin API endpoints, and lifespan seed loading.

Validates:
- ScreeningProtocol, ProtocolVersion, OrgProtocolActivation, ScreeningEvent DB models
- TriggerMatcher keyword/regex matching with <50ms performance
- ExplorationConfig / ExplorationResult / ExplorationRoundResult schemas
- AnalysisConfig.exploration field integration
- ProtocolService CRUD, activation, visibility rules
- Admin API at /api/v1/admin/screening/ with role guard
- Seed protocol loading during app lifespan
"""

import time
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession as AS

from app.models.screening import (
    OrgProtocolActivation,
    ProtocolVersion,
    ScreeningEvent,
    ScreeningProtocol,
)
from app.services.exploration.schemas import (
    ExplorationConfig,
    ExplorationResult,
    ExplorationRoundResult,
    ExplorationStageResult,
    ScreeningResult,
)
from app.services.analysis.schemas import AnalysisConfig
from app.services.screening.trigger_matcher import TriggerMatcher, TriggeredProtocol


def _mock_activation(protocol_id: int, version_id: int, mode: str = "mandatory"):
    """Create a lightweight mock for OrgProtocolActivation (avoids SQLAlchemy state)."""
    return SimpleNamespace(protocol_id=protocol_id, pinned_version_id=version_id, activation_mode=mode)


def _mock_version(version_id: int, protocol_id: int, trigger_conditions: dict,
                   protocol_name: str = "Test", severity_tier: str = "critical"):
    """Create a lightweight mock for ProtocolVersion (avoids SQLAlchemy state)."""
    return SimpleNamespace(
        id=version_id,
        protocol_id=protocol_id,
        version="1.0.0",
        trigger_conditions_json=trigger_conditions,
        _protocol_name=protocol_name,
        _severity_tier=severity_tier,
    )


# -- DB Model Tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_screening_protocol_has_required_columns(async_session: AsyncSession):
    """ScreeningProtocol model has all required columns."""
    protocol = ScreeningProtocol(
        name="Test Protocol",
        slug="test-protocol",
        description="A test screening protocol",
        severity_tier="critical",
        owner_org_id=None,
        is_shared=False,
        is_seed=True,
    )
    async_session.add(protocol)
    await async_session.flush()

    assert protocol.id is not None
    assert protocol.name == "Test Protocol"
    assert protocol.slug == "test-protocol"
    assert protocol.description == "A test screening protocol"
    assert protocol.severity_tier == "critical"
    assert protocol.owner_org_id is None
    assert protocol.is_shared is False
    assert protocol.is_seed is True
    assert protocol.created_at is not None


@pytest.mark.asyncio
async def test_protocol_version_has_required_columns(async_session: AsyncSession):
    """ProtocolVersion model has all required columns."""
    protocol = ScreeningProtocol(
        name="DV Protocol",
        slug="dv-version-test",
        severity_tier="critical",
        is_seed=True,
    )
    async_session.add(protocol)
    await async_session.flush()

    version = ProtocolVersion(
        protocol_id=protocol.id,
        version="1.0.0",
        trigger_conditions_json={"keywords": ["domestic violence"]},
        questions_json=[{"text": "Are you safe?", "is_mandatory": True}],
        escalation_actions_json={"immediate_resources": True},
        safety_resources_json={"hotline": "1-800-799-7233"},
        is_active=True,
    )
    async_session.add(version)
    await async_session.flush()

    assert version.id is not None
    assert version.protocol_id == protocol.id
    assert version.version == "1.0.0"
    assert version.trigger_conditions_json["keywords"] == ["domestic violence"]
    assert version.questions_json[0]["text"] == "Are you safe?"
    assert version.escalation_actions_json["immediate_resources"] is True
    assert version.safety_resources_json["hotline"] == "1-800-799-7233"
    assert version.is_active is True
    assert version.created_at is not None


@pytest.mark.asyncio
async def test_org_protocol_activation_has_required_columns(async_session: AsyncSession):
    """OrgProtocolActivation model (TenantBase) has all required columns."""
    activation = OrgProtocolActivation(
        protocol_id=1,
        pinned_version_id=1,
        activation_mode="mandatory",
        config_json={"custom_override": True},
    )
    async_session.add(activation)
    await async_session.flush()

    assert activation.id is not None
    assert activation.protocol_id == 1
    assert activation.pinned_version_id == 1
    assert activation.activation_mode == "mandatory"
    assert activation.config_json == {"custom_override": True}
    assert activation.created_at is not None
    assert activation.updated_at is not None


@pytest.mark.asyncio
async def test_screening_event_has_required_columns(async_session: AsyncSession):
    """ScreeningEvent model (TenantBase) has all required columns."""
    event = ScreeningEvent(
        session_id=42,
        protocol_id=1,
        protocol_version_id=1,
        severity_tier="critical",
        trigger_details_json={"matched_keywords": ["afraid of partner"]},
        action_taken="immediate_alert",
    )
    async_session.add(event)
    await async_session.flush()

    assert event.id is not None
    assert event.session_id == 42
    assert event.protocol_id == 1
    assert event.protocol_version_id == 1
    assert event.severity_tier == "critical"
    assert event.trigger_details_json["matched_keywords"] == ["afraid of partner"]
    assert event.action_taken == "immediate_alert"
    assert event.created_at is not None


# -- TriggerMatcher Tests ---------------------------------------------------


def test_trigger_matcher_keyword_match():
    """TriggerMatcher.match_fast returns triggered protocols for keyword match."""
    activation = _mock_activation(1, 10)
    version = _mock_version(10, 1, {
        "keywords": ["domestic violence", "afraid of partner", "hitting me"],
        "regex_patterns": [],
        "folio_concept_iris": [],
    }, protocol_name="DV/IPV", severity_tier="critical")

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("My partner has been hitting me and I am scared")

    assert len(results) > 0
    assert results[0].protocol_id == 1
    assert results[0].trigger_type == "keyword"
    assert "hitting me" in results[0].matched_terms


def test_trigger_matcher_regex_match():
    """TriggerMatcher.match_fast returns triggered protocols for regex pattern match."""
    activation = _mock_activation(2, 20)
    version = _mock_version(20, 2, {
        "keywords": [],
        "regex_patterns": [r"child\s+(abuse|neglect)", r"hurt\s+my\s+(kid|child)"],
        "folio_concept_iris": [],
    }, protocol_name="Child Abuse", severity_tier="critical")

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("I think there is child abuse happening in the home")

    assert len(results) > 0
    assert results[0].trigger_type == "regex"


def test_trigger_matcher_no_match():
    """TriggerMatcher.match_fast returns empty list when no triggers match."""
    activation = _mock_activation(1, 10)
    version = _mock_version(10, 1, {
        "keywords": ["domestic violence"],
        "regex_patterns": [],
        "folio_concept_iris": [],
    }, protocol_name="DV/IPV", severity_tier="critical")

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("I need help with a contract dispute")

    assert results == []


def test_trigger_matcher_precompiles_regex():
    """TriggerMatcher pre-compiles regex patterns on initialization."""
    activation = _mock_activation(3, 30, "optional")
    version = _mock_version(30, 3, {
        "keywords": [],
        "regex_patterns": [r"stalk(ing|er|ed)", r"follow(ing|ed)\s+me"],
        "folio_concept_iris": [],
    }, protocol_name="Stalking", severity_tier="elevated")

    matcher = TriggerMatcher([(activation, version)])

    # Verify that compiled patterns exist (implementation detail check)
    assert hasattr(matcher, "_compiled_patterns") or hasattr(matcher, "_protocols")
    # The matcher should work quickly (pre-compiled)
    start = time.perf_counter()
    matcher.match_fast("This person has been stalking me for weeks")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50, f"Match took {elapsed_ms:.1f}ms, expected <50ms"


def test_trigger_matcher_keyword_match_under_50ms():
    """TriggerMatcher.match_fast completes keyword matching in <50ms."""
    protocols = []
    for i in range(16):  # Simulate all 16 protocols
        activation = _mock_activation(i + 1, (i + 1) * 10)
        tier = "critical" if i < 5 else "elevated" if i < 10 else "advisory"
        version = _mock_version((i + 1) * 10, i + 1, {
            "keywords": [f"keyword_{i}_a", f"keyword_{i}_b", f"keyword_{i}_c"],
            "regex_patterns": [rf"pattern_{i}\s+\w+"],
            "folio_concept_iris": [],
        }, protocol_name=f"Protocol {i + 1}", severity_tier=tier)
        protocols.append((activation, version))

    matcher = TriggerMatcher(protocols)

    start = time.perf_counter()
    matcher.match_fast("This is a long narrative about someone keyword_3_b experiencing problems")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50, f"Match against 16 protocols took {elapsed_ms:.1f}ms, expected <50ms"


# -- ExplorationConfig Schema Tests ------------------------------------------


def test_exploration_config_defaults():
    """ExplorationConfig has correct default values."""
    config = ExplorationConfig()
    assert config.min_rounds == 1
    assert config.max_rounds == 3
    assert config.stability_threshold == 0
    assert config.exploration_confidence_threshold == 0.4
    assert config.question_transparency is True


def test_analysis_config_has_exploration_field():
    """AnalysisConfig now has exploration field of type ExplorationConfig."""
    config = AnalysisConfig()
    assert hasattr(config, "exploration")
    assert isinstance(config.exploration, ExplorationConfig)
    assert config.exploration.min_rounds == 1
    assert config.exploration.max_rounds == 3


def test_exploration_result_schema():
    """ExplorationResult schema has required fields."""
    result = ExplorationResult(
        description="Possible domestic violence issue",
        folio_iri="https://folio.openlegalstandard.org/objective042",
        source_layer="protocol_match",
        confidence=0.85,
        is_new_issue=True,
        protocol_id=1,
        claim_name="DV Protection Order",
        rationale="Keyword match on 'afraid of partner'",
    )
    assert result.description == "Possible domestic violence issue"
    assert result.folio_iri is not None
    assert result.source_layer == "protocol_match"
    assert result.confidence == 0.85
    assert result.is_new_issue is True
    assert result.protocol_id == 1


def test_exploration_round_result_schema():
    """ExplorationRoundResult schema has required fields."""
    round_result = ExplorationRoundResult(
        round_number=1,
        results=[
            ExplorationResult(
                description="DV issue",
                source_layer="protocol_match",
                confidence=0.9,
                is_new_issue=True,
            ),
        ],
        new_issues_count=1,
        is_stable=False,
    )
    assert round_result.round_number == 1
    assert len(round_result.results) == 1
    assert round_result.new_issues_count == 1
    assert round_result.is_stable is False


def test_exploration_stage_result_schema():
    """ExplorationStageResult schema has required fields."""
    stage_result = ExplorationStageResult(
        rounds=[],
        total_new_issues=0,
        new_claims=[],
        triggered_protocols=[],
    )
    assert stage_result.total_new_issues == 0
    assert stage_result.new_claims == []
    assert stage_result.triggered_protocols == []


def test_screening_result_schema():
    """ScreeningResult schema has required fields."""
    result = ScreeningResult(
        triggered_protocols=[{"protocol_id": 1, "name": "DV/IPV", "severity": "critical"}],
        has_critical=True,
        has_elevated=False,
        has_advisory=False,
        safety_resources=[{"name": "National DV Hotline", "phone": "1-800-799-7233"}],
        mandatory_questions=[{"text": "Are you safe right now?"}],
        needs_deep_scan=True,
    )
    assert result.has_critical is True
    assert len(result.triggered_protocols) == 1
    assert result.needs_deep_scan is True


# ============================================================================
# Task 2: ProtocolService CRUD, Admin API, and Lifespan
# ============================================================================


# -- Helpers (same pattern as test_folio_admin.py) ---------------------------


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "StrongPass123!"
) -> dict:
    """Register a user and return tokens."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    return resp.json()


async def _make_admin(client: AsyncClient, email: str) -> dict:
    """Register user, promote to admin, re-login."""
    from app.models.user import User

    await _register_and_login(client, email)

    import app.db.engine as engine_module

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AS(bind=conn, expire_on_commit=False) as session:
            await session.execute(
                update(User).where(User.email == email).values(role="admin")
            )
            await session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    return resp.json()


def _auth_headers(tokens: dict) -> dict:
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }


# -- ProtocolService Unit Tests -----------------------------------------------


@pytest.mark.asyncio
async def test_protocol_service_create_protocol(async_session: AsyncSession):
    """ProtocolService.create_protocol creates a ScreeningProtocol + initial ProtocolVersion."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)
    protocol, version = await svc.create_protocol(
        name="Custom DV Protocol",
        slug="custom-dv",
        severity_tier="critical",
        description="Org-specific DV screening",
        owner_org_id=1,
        is_shared=False,
        trigger_conditions={"keywords": ["partner violence"]},
        questions=[{"text": "Are you safe?", "is_mandatory": True, "text_transparent": "..."}],
        escalation_actions={"mandated_reporting_flag": True},
        safety_resources=None,
    )

    assert protocol.id is not None
    assert protocol.slug == "custom-dv"
    assert protocol.owner_org_id == 1
    assert protocol.is_shared is False
    assert version.protocol_id == protocol.id
    assert version.version == "1.0.0"


@pytest.mark.asyncio
async def test_protocol_service_create_with_shared(async_session: AsyncSession):
    """ProtocolService.create_protocol with is_shared=True makes it visible in community pool."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)
    protocol, _ = await svc.create_protocol(
        name="Shared Protocol",
        slug="shared-test",
        severity_tier="advisory",
        description="Community shared",
        owner_org_id=1,
        is_shared=True,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "Test?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    assert protocol.is_shared is True


@pytest.mark.asyncio
async def test_protocol_service_list_protocols_visibility(async_session: AsyncSession):
    """ProtocolService.list_protocols returns seed + shared + own, excludes other org's private."""
    from app.services.screening.protocol_service import ProtocolService
    from app.services.screening.seed_protocols import seed_protocols_to_db

    # Seed the 16 system protocols
    await seed_protocols_to_db(async_session)

    svc = ProtocolService(async_session)

    # Create org 1's private protocol
    await svc.create_protocol(
        name="Org1 Private", slug="org1-private", severity_tier="advisory",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    # Create org 2's private protocol
    await svc.create_protocol(
        name="Org2 Private", slug="org2-private", severity_tier="advisory",
        owner_org_id=2, is_shared=False,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    # Create org 2's shared protocol
    await svc.create_protocol(
        name="Org2 Shared", slug="org2-shared", severity_tier="advisory",
        owner_org_id=2, is_shared=True,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    # Org 1 should see: 16 seeds + own private + org2's shared = 18
    visible = await svc.list_protocols(org_id=1)
    slugs = {p["slug"] for p in visible}

    assert "org1-private" in slugs, "Own private protocol should be visible"
    assert "org2-private" not in slugs, "Other org's private protocol should NOT be visible"
    assert "org2-shared" in slugs, "Other org's shared protocol should be visible"
    assert "dv-ipv" in slugs, "Seed protocol should be visible"


@pytest.mark.asyncio
async def test_protocol_service_create_version(async_session: AsyncSession):
    """ProtocolService.create_version creates a new ProtocolVersion with incremented semver."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)
    protocol, v1 = await svc.create_protocol(
        name="Versioned Protocol", slug="versioned-test", severity_tier="elevated",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["v1"]},
        questions=[{"text": "V1?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    v2 = await svc.create_version(
        protocol_id=protocol.id,
        trigger_conditions={"keywords": ["v2"]},
        questions=[{"text": "V2?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
        version="1.1.0",
    )

    assert v2.version == "1.1.0"
    assert v2.protocol_id == protocol.id


@pytest.mark.asyncio
async def test_protocol_service_activate_protocol(async_session: AsyncSession):
    """ProtocolService.activate_protocol creates OrgProtocolActivation with pinned_version_id."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)
    protocol, version = await svc.create_protocol(
        name="Activate Test", slug="activate-test", severity_tier="critical",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "?", "is_mandatory": True, "text_transparent": "..."}],
        escalation_actions={"mandated_reporting_flag": True},
    )

    activation = await svc.activate_protocol(
        protocol_id=protocol.id,
        pinned_version_id=version.id,
        activation_mode="mandatory",
    )

    assert activation.protocol_id == protocol.id
    assert activation.pinned_version_id == version.id
    assert activation.activation_mode == "mandatory"


@pytest.mark.asyncio
async def test_protocol_service_deactivate(async_session: AsyncSession):
    """ProtocolService.deactivate sets activation_mode to 'disabled'."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)
    protocol, version = await svc.create_protocol(
        name="Deactivate Test", slug="deactivate-test", severity_tier="elevated",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["test"]},
        questions=[{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    await svc.activate_protocol(
        protocol_id=protocol.id,
        pinned_version_id=version.id,
        activation_mode="mandatory",
    )

    await svc.deactivate(protocol_id=protocol.id)

    # Check it's disabled
    active = await svc.get_active_protocols()
    active_ids = [a[0].protocol_id for a in active]
    assert protocol.id not in active_ids


@pytest.mark.asyncio
async def test_protocol_service_get_active_protocols(async_session: AsyncSession):
    """ProtocolService.get_active_protocols returns only non-disabled protocols."""
    from app.services.screening.protocol_service import ProtocolService

    svc = ProtocolService(async_session)

    p1, v1 = await svc.create_protocol(
        name="Active1", slug="active1", severity_tier="critical",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["test1"]},
        questions=[{"text": "?", "is_mandatory": True, "text_transparent": "..."}],
        escalation_actions={"mandated_reporting_flag": True},
    )
    p2, v2 = await svc.create_protocol(
        name="Active2", slug="active2", severity_tier="elevated",
        owner_org_id=1, is_shared=False,
        trigger_conditions={"keywords": ["test2"]},
        questions=[{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
        escalation_actions={},
    )

    await svc.activate_protocol(p1.id, v1.id, "mandatory")
    await svc.activate_protocol(p2.id, v2.id, "disabled")

    active = await svc.get_active_protocols()
    active_ids = [a[0].protocol_id for a in active]
    assert p1.id in active_ids
    assert p2.id not in active_ids


@pytest.mark.asyncio
async def test_protocol_service_activate_defaults_for_org(async_session: AsyncSession):
    """ProtocolService.activate_defaults_for_org activates critical as mandatory."""
    from app.services.screening.protocol_service import ProtocolService
    from app.services.screening.seed_protocols import seed_protocols_to_db

    await seed_protocols_to_db(async_session)

    svc = ProtocolService(async_session)
    count = await svc.activate_defaults_for_org()

    # 5 critical (mandatory) + 5 elevated (optional) = 10
    assert count == 10

    active = await svc.get_active_protocols()
    mandatory = [a for a, v in active if a.activation_mode == "mandatory"]
    optional = [a for a, v in active if a.activation_mode == "optional"]
    assert len(mandatory) == 5
    assert len(optional) == 5


# -- Admin API Endpoint Tests -------------------------------------------------


@pytest.mark.asyncio
async def test_admin_create_protocol(async_client: AsyncClient):
    """POST /api/v1/admin/screening/protocols creates protocol (admin only)."""
    admin_tokens = await _make_admin(async_client, "screenadmin1@test.com")

    resp = await async_client.post(
        "/api/v1/admin/screening/protocols",
        json={
            "name": "API Test Protocol",
            "slug": "api-test-protocol",
            "severity_tier": "advisory",
            "description": "Created via API",
            "trigger_conditions": {"keywords": ["api-test"]},
            "questions": [{"text": "Test?", "is_mandatory": False, "text_transparent": "..."}],
            "escalation_actions": {},
            "is_shared": False,
        },
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code in (200, 201), f"Got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["slug"] == "api-test-protocol"


@pytest.mark.asyncio
async def test_admin_list_protocols(async_client: AsyncClient):
    """GET /api/v1/admin/screening/protocols lists protocols visible to org."""
    admin_tokens = await _make_admin(async_client, "screenadmin2@test.com")

    resp = await async_client.get(
        "/api/v1/admin/screening/protocols",
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_admin_activate_protocol(async_client: AsyncClient):
    """POST /api/v1/admin/screening/protocols/{id}/activate activates with mode."""
    admin_tokens = await _make_admin(async_client, "screenadmin3@test.com")

    # First create a protocol
    create_resp = await async_client.post(
        "/api/v1/admin/screening/protocols",
        json={
            "name": "Activate API Test",
            "slug": "activate-api-test",
            "severity_tier": "elevated",
            "trigger_conditions": {"keywords": ["activate-test"]},
            "questions": [{"text": "?", "is_mandatory": False, "text_transparent": "..."}],
            "escalation_actions": {},
            "is_shared": False,
        },
        headers=_auth_headers(admin_tokens),
    )
    assert create_resp.status_code in (200, 201)
    protocol_data = create_resp.json()
    protocol_id = protocol_data["id"]
    version_id = protocol_data["version_id"]

    # Activate it
    resp = await async_client.post(
        f"/api/v1/admin/screening/protocols/{protocol_id}/activate",
        json={
            "pinned_version_id": version_id,
            "activation_mode": "mandatory",
        },
        headers=_auth_headers(admin_tokens),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["activation_mode"] == "mandatory"


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin(async_client: AsyncClient):
    """Non-admin users get 403 on screening admin endpoints."""
    consumer_tokens = await _register_and_login(async_client, "consumer-screen@test.com")
    headers = _auth_headers(consumer_tokens)

    endpoints = [
        ("GET", "/api/v1/admin/screening/protocols"),
        ("POST", "/api/v1/admin/screening/protocols"),
    ]

    for method, path in endpoints:
        if method == "GET":
            resp = await async_client.get(path, headers=headers)
        else:
            resp = await async_client.post(path, headers=headers, json={})
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}, expected 403"


# -- Router Wiring Test -------------------------------------------------------


def test_screening_admin_router_is_registered():
    """The screening_admin_router is wired into the FastAPI app via include_router."""
    from app.main import app as fastapi_app

    route_paths = [route.path for route in fastapi_app.routes]
    assert "/api/v1/admin/screening/protocols" in route_paths, (
        "screening_admin_router not registered -- /api/v1/admin/screening/protocols missing"
    )
