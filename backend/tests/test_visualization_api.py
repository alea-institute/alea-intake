"""Tests for GET /api/v1/analysis/{intake_id}/visualization endpoint.

Verifies the visualization API returns facts with source_spans, claims with
elements, mappings, gaps, and messages -- the full payload needed by the
frontend visualization views.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

import app.models  # noqa: F401 -- register all models

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper: register a user and get auth headers
# ---------------------------------------------------------------------------


_register_counter = 0


async def _register_and_get_headers(client: AsyncClient) -> dict[str, str]:
    """Register a test user, grant AI consent, and return auth + tenant headers."""
    global _register_counter
    _register_counter += 1
    email = f"viztest{_register_counter}@example.com"

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Viz Test User",
        },
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    data = resp.json()
    headers = {
        "Authorization": f"Bearer {data['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }

    # Grant AI processing consent so ConsentMiddleware doesn't block analysis endpoints
    await client.post(
        "/api/v1/consent/grant",
        json={
            "consent_version": "1.0",
            "consent_items": {"ai_processing": True, "data_sharing": False},
        },
        headers=headers,
    )

    return headers


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_visualization_data(client: AsyncClient, headers: dict[str, str]) -> int:
    """Seed a full analysis run with facts, spans, claims, elements, mappings, gaps, messages.

    Returns the intake_id.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import app.db.engine as engine_module

    engine = engine_module._engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(
            schema_translate_map={"tenant": None, "shared": None}
        )
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            from app.models.intake import Intake, IntakeSession, Message
            from app.models.fact import ExtractedFact, FactSourceSpan
            from app.models.analysis import (
                AnalysisRun,
                AnalysisClaim,
                ClaimElement,
                FactClaimMapping,
                AnalysisGap,
            )

            # Create intake
            intake = Intake(org_id=1, status="active")
            session.add(intake)
            await session.flush()

            # Create session for the intake
            intake_session = IntakeSession(intake_id=intake.id, status="active")
            session.add(intake_session)
            await session.flush()

            # Create messages (consumer/professional only, not 'system')
            msg1 = Message(
                session_id=intake_session.id,
                party_id=None,
                sender_type="consumer",
                modality="text",
                normalized_text=b"My landlord refuses to fix the broken heater in my apartment.",
                sequence_number=1,
            )
            msg2 = Message(
                session_id=intake_session.id,
                party_id=None,
                sender_type="professional",
                modality="text",
                normalized_text=b"How long has the heater been broken?",
                sequence_number=2,
            )
            # System message -- should be excluded from visualization
            msg_sys = Message(
                session_id=intake_session.id,
                party_id=None,
                sender_type="system",
                modality="text",
                normalized_text=b"Session started.",
                sequence_number=0,
            )
            session.add_all([msg1, msg2, msg_sys])
            await session.flush()

            # Create analysis run
            run = AnalysisRun(
                intake_id=intake.id,
                status="completed",
                trigger_type="manual",
                current_iteration_number=2,
                max_iterations=10,
            )
            session.add(run)
            await session.flush()

            # Create facts
            fact1 = ExtractedFact(
                intake_id=intake.id,
                message_id=msg1.id,
                assertion_text="Landlord refuses to fix broken heater",
                fact_type="assertion",
                confidence=0.92,
                is_active=True,
            )
            fact2 = ExtractedFact(
                intake_id=intake.id,
                message_id=msg1.id,
                assertion_text="Apartment has a broken heater",
                fact_type="condition",
                confidence=0.88,
                is_active=True,
            )
            # Inactive fact -- should be excluded
            fact_inactive = ExtractedFact(
                intake_id=intake.id,
                message_id=msg1.id,
                assertion_text="Old fact superseded",
                fact_type="assertion",
                confidence=0.5,
                is_active=False,
            )
            session.add_all([fact1, fact2, fact_inactive])
            await session.flush()

            # Create source spans
            span1 = FactSourceSpan(
                fact_id=fact1.id,
                message_id=msg1.id,
                start_char=0,
                end_char=40,
                page_number=1,
                paragraph_index=0,
            )
            span2 = FactSourceSpan(
                fact_id=fact1.id,
                message_id=msg1.id,
                start_char=41,
                end_char=60,
                timestamp_start_sec=5.0,
                timestamp_end_sec=12.0,
            )
            session.add_all([span1, span2])
            await session.flush()

            # Create claims
            claim1 = AnalysisClaim(
                run_id=run.id,
                claim_name="Breach of Warranty of Habitability",
                claim_type="identified",
                jurisdiction="California",
                confidence=0.85,
                rationale="Landlord failed to maintain habitable conditions",
                is_potential=False,
                iteration_discovered=1,
            )
            claim2 = AnalysisClaim(
                run_id=run.id,
                claim_name="Wrongful Eviction",
                claim_type="potential",
                jurisdiction="California",
                confidence=0.6,
                rationale="Possible retaliatory eviction",
                is_potential=True,
                iteration_discovered=2,
            )
            session.add_all([claim1, claim2])
            await session.flush()

            # Create elements
            elem1 = ClaimElement(
                claim_id=claim1.id,
                element_name="Defective Condition",
                element_description="The rental unit has a condition that makes it uninhabitable",
                is_satisfied=True,
                satisfaction_confidence=0.90,
                jurisdiction="California",
            )
            elem2 = ClaimElement(
                claim_id=claim1.id,
                element_name="Notice to Landlord",
                element_description="Tenant gave notice of the defective condition",
                is_satisfied=False,
                satisfaction_confidence=0.3,
                jurisdiction="California",
            )
            session.add_all([elem1, elem2])
            await session.flush()

            # Create mappings
            mapping1 = FactClaimMapping(
                fact_id=fact1.id,
                claim_id=claim1.id,
                element_id=elem1.id,
                confidence=0.88,
                mapping_rationale="Broken heater constitutes defective condition",
                iteration_number=1,
            )
            session.add(mapping1)
            await session.flush()

            # Create gaps
            gap1 = AnalysisGap(
                run_id=run.id,
                gap_type="unsupported_element",
                claim_id=claim1.id,
                element_id=elem2.id,
                description="No evidence that tenant notified landlord",
                priority=1,
                status="open",
                iteration_found=1,
            )
            session.add(gap1)
            await session.flush()

            await session.commit()
            return intake.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVisualizationEndpoint:
    """Tests for GET /api/v1/analysis/{intake_id}/visualization."""

    async def test_returns_200_with_full_payload(self, async_client: AsyncClient) -> None:
        """Test 1: Returns 200 with facts, claims, mappings, gaps, messages arrays."""
        headers = await _register_and_get_headers(async_client)
        intake_id = await _seed_visualization_data(async_client, headers)

        resp = await async_client.get(
            f"/api/v1/analysis/{intake_id}/visualization",
            headers=headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "completed"
        assert isinstance(data["facts"], list)
        assert isinstance(data["claims"], list)
        assert isinstance(data["mappings"], list)
        assert isinstance(data["gaps"], list)
        assert isinstance(data["messages"], list)

        # 2 active facts (inactive excluded)
        assert len(data["facts"]) == 2
        # 2 claims
        assert len(data["claims"]) == 2
        # 1 mapping
        assert len(data["mappings"]) == 1
        # 1 gap
        assert len(data["gaps"]) == 1
        # 2 messages (system excluded)
        assert len(data["messages"]) == 2

    async def test_facts_include_source_spans(self, async_client: AsyncClient) -> None:
        """Test 2: Each fact includes source_spans with start_char, end_char, etc."""
        headers = await _register_and_get_headers(async_client)
        intake_id = await _seed_visualization_data(async_client, headers)

        resp = await async_client.get(
            f"/api/v1/analysis/{intake_id}/visualization",
            headers=headers,
        )
        data = resp.json()

        # Find the fact that has source spans (fact1)
        facts_with_spans = [f for f in data["facts"] if len(f["source_spans"]) > 0]
        assert len(facts_with_spans) >= 1

        fact = facts_with_spans[0]
        assert len(fact["source_spans"]) == 2

        span = fact["source_spans"][0]
        assert "start_char" in span
        assert "end_char" in span
        assert "message_id" in span
        assert "page_number" in span
        assert "paragraph_index" in span
        assert "timestamp_start_sec" in span
        assert "timestamp_end_sec" in span

    async def test_claims_include_elements(self, async_client: AsyncClient) -> None:
        """Test 3: Each claim includes elements with expected fields."""
        headers = await _register_and_get_headers(async_client)
        intake_id = await _seed_visualization_data(async_client, headers)

        resp = await async_client.get(
            f"/api/v1/analysis/{intake_id}/visualization",
            headers=headers,
        )
        data = resp.json()

        # Find the claim with elements (Breach of Warranty)
        claims_with_elems = [c for c in data["claims"] if len(c["elements"]) > 0]
        assert len(claims_with_elems) >= 1

        claim = claims_with_elems[0]
        assert len(claim["elements"]) == 2

        elem = claim["elements"][0]
        assert "id" in elem
        assert "element_name" in elem
        assert "element_description" in elem
        assert "is_satisfied" in elem
        assert "satisfaction_confidence" in elem

    async def test_mappings_have_required_fields(self, async_client: AsyncClient) -> None:
        """Test 4: Mappings include fact_id, claim_id, element_id, confidence, mapping_rationale."""
        headers = await _register_and_get_headers(async_client)
        intake_id = await _seed_visualization_data(async_client, headers)

        resp = await async_client.get(
            f"/api/v1/analysis/{intake_id}/visualization",
            headers=headers,
        )
        data = resp.json()

        assert len(data["mappings"]) >= 1
        mapping = data["mappings"][0]
        assert "fact_id" in mapping
        assert "claim_id" in mapping
        assert "element_id" in mapping
        assert "confidence" in mapping
        assert "mapping_rationale" in mapping

    async def test_returns_404_when_no_analysis_run(self, async_client: AsyncClient) -> None:
        """Test 5: Returns 404 when no analysis run exists for the intake."""
        headers = await _register_and_get_headers(async_client)

        resp = await async_client.get(
            "/api/v1/analysis/99999/visualization",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_messages_include_content_and_sender_type(self, async_client: AsyncClient) -> None:
        """Test 6: Messages include id, content (decoded), sender_type."""
        headers = await _register_and_get_headers(async_client)
        intake_id = await _seed_visualization_data(async_client, headers)

        resp = await async_client.get(
            f"/api/v1/analysis/{intake_id}/visualization",
            headers=headers,
        )
        data = resp.json()

        assert len(data["messages"]) == 2
        msg = data["messages"][0]
        assert "id" in msg
        assert "content" in msg
        assert "sender_type" in msg
        # Verify sender types are only consumer/professional (no system)
        sender_types = {m["sender_type"] for m in data["messages"]}
        assert "system" not in sender_types
        assert sender_types <= {"consumer", "professional"}
