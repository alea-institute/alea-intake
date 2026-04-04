"""Tests for screening protocol DB models, TriggerMatcher, and Pydantic schemas.

Validates:
- ScreeningProtocol, ProtocolVersion, OrgProtocolActivation, ScreeningEvent DB models
- TriggerMatcher keyword/regex matching with <50ms performance
- ExplorationConfig / ExplorationResult / ExplorationRoundResult schemas
- AnalysisConfig.exploration field integration
"""

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    # Simulate protocol data as tuple (activation, version)
    activation = OrgProtocolActivation.__new__(OrgProtocolActivation)
    activation.protocol_id = 1
    activation.pinned_version_id = 10
    activation.activation_mode = "mandatory"

    version = ProtocolVersion.__new__(ProtocolVersion)
    version.id = 10
    version.protocol_id = 1
    version.version = "1.0.0"
    version.trigger_conditions_json = {
        "keywords": ["domestic violence", "afraid of partner", "hitting me"],
        "regex_patterns": [],
        "folio_concept_iris": [],
    }

    # Set protocol metadata on version for TriggerMatcher
    version._protocol_name = "DV/IPV"
    version._severity_tier = "critical"

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("My partner has been hitting me and I am scared")

    assert len(results) > 0
    assert results[0].protocol_id == 1
    assert results[0].trigger_type == "keyword"
    assert "hitting me" in results[0].matched_terms


def test_trigger_matcher_regex_match():
    """TriggerMatcher.match_fast returns triggered protocols for regex pattern match."""
    activation = OrgProtocolActivation.__new__(OrgProtocolActivation)
    activation.protocol_id = 2
    activation.pinned_version_id = 20
    activation.activation_mode = "mandatory"

    version = ProtocolVersion.__new__(ProtocolVersion)
    version.id = 20
    version.protocol_id = 2
    version.version = "1.0.0"
    version.trigger_conditions_json = {
        "keywords": [],
        "regex_patterns": [r"child\s+(abuse|neglect)", r"hurt\s+my\s+(kid|child)"],
        "folio_concept_iris": [],
    }
    version._protocol_name = "Child Abuse"
    version._severity_tier = "critical"

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("I think there is child abuse happening in the home")

    assert len(results) > 0
    assert results[0].trigger_type == "regex"


def test_trigger_matcher_no_match():
    """TriggerMatcher.match_fast returns empty list when no triggers match."""
    activation = OrgProtocolActivation.__new__(OrgProtocolActivation)
    activation.protocol_id = 1
    activation.pinned_version_id = 10
    activation.activation_mode = "mandatory"

    version = ProtocolVersion.__new__(ProtocolVersion)
    version.id = 10
    version.protocol_id = 1
    version.version = "1.0.0"
    version.trigger_conditions_json = {
        "keywords": ["domestic violence"],
        "regex_patterns": [],
        "folio_concept_iris": [],
    }
    version._protocol_name = "DV/IPV"
    version._severity_tier = "critical"

    matcher = TriggerMatcher([(activation, version)])
    results = matcher.match_fast("I need help with a contract dispute")

    assert results == []


def test_trigger_matcher_precompiles_regex():
    """TriggerMatcher pre-compiles regex patterns on initialization."""
    activation = OrgProtocolActivation.__new__(OrgProtocolActivation)
    activation.protocol_id = 3
    activation.pinned_version_id = 30
    activation.activation_mode = "optional"

    version = ProtocolVersion.__new__(ProtocolVersion)
    version.id = 30
    version.protocol_id = 3
    version.version = "1.0.0"
    version.trigger_conditions_json = {
        "keywords": [],
        "regex_patterns": [r"stalk(ing|er|ed)", r"follow(ing|ed)\s+me"],
        "folio_concept_iris": [],
    }
    version._protocol_name = "Stalking"
    version._severity_tier = "elevated"

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
        activation = OrgProtocolActivation.__new__(OrgProtocolActivation)
        activation.protocol_id = i + 1
        activation.pinned_version_id = (i + 1) * 10
        activation.activation_mode = "mandatory"

        version = ProtocolVersion.__new__(ProtocolVersion)
        version.id = (i + 1) * 10
        version.protocol_id = i + 1
        version.version = "1.0.0"
        version.trigger_conditions_json = {
            "keywords": [f"keyword_{i}_a", f"keyword_{i}_b", f"keyword_{i}_c"],
            "regex_patterns": [rf"pattern_{i}\s+\w+"],
            "folio_concept_iris": [],
        }
        version._protocol_name = f"Protocol {i + 1}"
        version._severity_tier = "critical" if i < 5 else "elevated" if i < 10 else "advisory"
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
