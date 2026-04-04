"""Tests for seed protocol definitions and idempotent DB loader.

Validates:
- SEED_PROTOCOLS contains exactly 16 protocols with correct severity distribution
- DV/IPV protocol has correct slug, severity, keywords, safety resources
- All critical-tier protocols have "Are you safe right now?" opener
- seed_protocols_to_db inserts idempotently (no duplicates on second call)
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ProtocolVersion, ScreeningProtocol
from app.services.screening.seed_protocols import SEED_PROTOCOLS, seed_protocols_to_db


# -- SEED_PROTOCOLS Structure Tests ------------------------------------------


def test_seed_protocols_count():
    """SEED_PROTOCOLS contains exactly 16 protocols."""
    assert len(SEED_PROTOCOLS) == 16


def test_seed_protocols_severity_distribution():
    """SEED_PROTOCOLS has correct severity distribution: 5 Critical, 5 Elevated, 6 Advisory."""
    critical = [p for p in SEED_PROTOCOLS if p["severity_tier"] == "critical"]
    elevated = [p for p in SEED_PROTOCOLS if p["severity_tier"] == "elevated"]
    advisory = [p for p in SEED_PROTOCOLS if p["severity_tier"] == "advisory"]

    assert len(critical) == 5, f"Expected 5 critical, got {len(critical)}"
    assert len(elevated) == 5, f"Expected 5 elevated, got {len(elevated)}"
    assert len(advisory) == 6, f"Expected 6 advisory, got {len(advisory)}"


def test_dv_ipv_protocol_content():
    """DV/IPV seed protocol has correct slug, severity, keywords, and safety resources."""
    dv = next((p for p in SEED_PROTOCOLS if p["slug"] == "dv-ipv"), None)
    assert dv is not None, "DV/IPV protocol not found in SEED_PROTOCOLS"
    assert dv["severity_tier"] == "critical"

    # Check trigger keywords
    keywords = dv["trigger_conditions"]["keywords"]
    assert "domestic violence" in keywords
    assert "afraid of partner" in keywords

    # Check safety resources include National DV Hotline
    resources = dv.get("safety_resources", {})
    resource_text = str(resources).lower()
    assert "1-800-799-7233" in resource_text or "national" in resource_text


def test_critical_protocols_have_safety_opener():
    """Each critical-tier seed protocol includes 'Are you safe right now?' as first mandatory question."""
    critical = [p for p in SEED_PROTOCOLS if p["severity_tier"] == "critical"]
    for protocol in critical:
        questions = protocol["questions"]
        assert len(questions) > 0, f"Protocol {protocol['slug']} has no questions"

        first_q = questions[0]
        assert first_q["is_mandatory"] is True, (
            f"Protocol {protocol['slug']}: first question not mandatory"
        )
        assert "are you safe" in first_q["text"].lower(), (
            f"Protocol {protocol['slug']}: first question is not 'Are you safe right now?', "
            f"got: {first_q['text']}"
        )


def test_all_protocols_have_required_fields():
    """Every seed protocol has all required fields."""
    required_fields = {"name", "slug", "severity_tier", "trigger_conditions", "questions", "escalation_actions"}
    for protocol in SEED_PROTOCOLS:
        missing = required_fields - set(protocol.keys())
        assert not missing, f"Protocol {protocol.get('slug', '?')} missing fields: {missing}"


def test_critical_protocols_have_mandated_reporting():
    """All critical protocols include mandated_reporting_flag=True in escalation_actions."""
    critical = [p for p in SEED_PROTOCOLS if p["severity_tier"] == "critical"]
    for protocol in critical:
        actions = protocol["escalation_actions"]
        assert actions.get("mandated_reporting_flag") is True, (
            f"Protocol {protocol['slug']}: missing mandated_reporting_flag"
        )


def test_questions_have_trauma_informed_framing():
    """Seed protocol questions have text_transparent field for transparency mode."""
    for protocol in SEED_PROTOCOLS:
        for q in protocol["questions"]:
            assert "text_transparent" in q or "text" in q, (
                f"Protocol {protocol['slug']}: question missing text or text_transparent"
            )


# -- Idempotent DB Loading Tests ---------------------------------------------


@pytest.mark.asyncio
async def test_seed_protocols_to_db_creates_all(async_session: AsyncSession):
    """seed_protocols_to_db creates all 16 protocols on first call."""
    count = await seed_protocols_to_db(async_session)
    assert count == 16

    # Verify all exist in DB
    result = await async_session.execute(select(ScreeningProtocol))
    protocols = result.scalars().all()
    assert len(protocols) == 16


@pytest.mark.asyncio
async def test_seed_protocols_to_db_idempotent(async_session: AsyncSession):
    """seed_protocols_to_db is idempotent -- second call produces no duplicates."""
    first_count = await seed_protocols_to_db(async_session)
    assert first_count == 16

    second_count = await seed_protocols_to_db(async_session)
    assert second_count == 0

    # Still only 16 in DB
    result = await async_session.execute(select(ScreeningProtocol))
    protocols = result.scalars().all()
    assert len(protocols) == 16


@pytest.mark.asyncio
async def test_seed_protocols_create_versions(async_session: AsyncSession):
    """seed_protocols_to_db creates a v1.0.0 ProtocolVersion for each protocol."""
    await seed_protocols_to_db(async_session)

    result = await async_session.execute(select(ProtocolVersion))
    versions = result.scalars().all()
    assert len(versions) == 16

    for v in versions:
        assert v.version == "1.0.0"
        assert v.is_active is True
