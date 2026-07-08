"""Tests for the output API router: generation, retrieval, and export endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# Ensure OutputDocument model is registered with TenantBase metadata
import app.models.output  # noqa: F401
import app.models  # noqa: F401


# ---------------------------------------------------------------------------
# Helper: register a user and get auth headers
# ---------------------------------------------------------------------------


async def _register_and_get_headers(client: AsyncClient) -> dict[str, str]:
    """Register a user and return auth + tenant headers."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "outputtest@example.com",
            "password": "TestPass123!",
            "full_name": "Output Test User",
        },
        headers={"X-Tenant-Slug": "test-legal-aid"},
    )
    data = resp.json()
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "X-Tenant-Slug": "test-legal-aid",
    }


# ---------------------------------------------------------------------------
# Router registration test
# ---------------------------------------------------------------------------


class TestOutputRouterRegistration:
    """Test that the output router is wired into main.py."""

    async def test_output_router_registered(self, async_client: AsyncClient) -> None:
        """Output router should be included in the FastAPI app."""
        resp = await async_client.get("/api/v1/output/1")
        # 400/401/404 -- any means the route exists and is handled
        assert resp.status_code in (400, 401, 404), f"Expected 400/401/404, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Generation endpoint tests
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    """Tests for POST /api/v1/output/generate."""

    async def test_generate_returns_201(self, async_client: AsyncClient) -> None:
        """POST /generate with valid data returns 201."""
        headers = await _register_and_get_headers(async_client)

        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import GapReport, OutputContext, OutputProfile, TriageResult

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=1, run_id=1, org_id=1, matter_title="Test Matter",
                generated_at=datetime(2026, 1, 15), completeness_score=0.75,
                gap_report=GapReport(completeness_score=0.75),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )

            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()

            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []

            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Generated Output"

            resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm"]},
                headers=headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert "documents" in data
            assert len(data["documents"]) >= 1

    async def test_generate_multiple_profiles(self, async_client: AsyncClient) -> None:
        """POST /generate with multiple profile_types creates multiple documents."""
        headers = await _register_and_get_headers(async_client)

        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import GapReport, OutputContext, OutputProfile, TriageResult

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=1, run_id=1, org_id=1, matter_title="Test",
                generated_at=datetime(2026, 1, 15), completeness_score=0.5,
                gap_report=GapReport(),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )

            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()

            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []

            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Output"

            resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm", "legal_aid"]},
                headers=headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert len(data["documents"]) == 2

    async def test_generate_requires_auth(self, async_client: AsyncClient) -> None:
        """POST /generate without auth token returns 401 (or 400 from tenant middleware)."""
        # With tenant header but no auth -> 401
        resp = await async_client.post(
            "/api/v1/output/generate",
            json={"run_id": 1, "intake_id": 1},
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Retrieval endpoint tests
# ---------------------------------------------------------------------------


class TestRetrievalEndpoints:
    """Tests for GET output endpoints."""

    async def test_get_document_detail(self, async_client: AsyncClient) -> None:
        """GET /output/{id} returns document detail."""
        headers = await _register_and_get_headers(async_client)

        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import GapReport, OutputContext, OutputProfile, TriageResult

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=1, run_id=1, org_id=1, matter_title="Test",
                generated_at=datetime(2026, 1, 15), completeness_score=0.5,
                gap_report=GapReport(),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )
            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()
            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Generated"

            gen_resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm"]},
                headers=headers,
            )
            assert gen_resp.status_code == 201
            doc_id = gen_resp.json()["documents"][0]["id"]

        resp = await async_client.get(f"/api/v1/output/{doc_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert "markdown_content" in data

    async def test_list_outputs_by_intake(self, async_client: AsyncClient) -> None:
        """GET /output/intake/{intake_id} lists documents."""
        headers = await _register_and_get_headers(async_client)

        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import GapReport, OutputContext, OutputProfile, TriageResult

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=42, run_id=1, org_id=1, matter_title="Test",
                generated_at=datetime(2026, 1, 15), completeness_score=0.5,
                gap_report=GapReport(),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )
            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()
            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Output"

            await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 42, "profile_types": ["law_firm"]},
                headers=headers,
            )

        resp = await async_client.get("/api/v1/output/intake/42", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_nonexistent_document_returns_404(self, async_client: AsyncClient) -> None:
        """GET /output/99999 returns 404."""
        headers = await _register_and_get_headers(async_client)
        resp = await async_client.get("/api/v1/output/99999", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Export endpoint tests
# ---------------------------------------------------------------------------


class TestExportEndpoints:
    """Tests for GET /output/{id}/export/{format}."""

    async def _generate_doc(self, async_client: AsyncClient, headers: dict) -> int:
        """Generate a document and return its ID."""
        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import GapReport, OutputContext, OutputProfile, TriageResult

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=1, run_id=1, org_id=1, matter_title="Export Test",
                generated_at=datetime(2026, 1, 15), completeness_score=0.5,
                gap_report=GapReport(),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )
            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()
            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Export test"

            gen_resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm"]},
                headers=headers,
            )
            assert gen_resp.status_code == 201
            return gen_resp.json()["documents"][0]["id"]

    async def test_export_pdf_content_type(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/pdf returns application/pdf Content-Type."""
        headers = await _register_and_get_headers(async_client)
        doc_id = await self._generate_doc(async_client, headers)

        resp = await async_client.get(f"/api/v1/output/{doc_id}/export/pdf", headers=headers)
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]

    async def test_export_docx_content_type(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/docx returns OOXML Content-Type."""
        headers = await _register_and_get_headers(async_client)
        doc_id = await self._generate_doc(async_client, headers)

        resp = await async_client.get(f"/api/v1/output/{doc_id}/export/docx", headers=headers)
        assert resp.status_code == 200
        assert "openxmlformats" in resp.headers["content-type"]

    async def test_export_requires_auth(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/pdf without auth returns 401 (or 400 from tenant middleware)."""
        resp = await async_client.get(
            "/api/v1/output/1/export/pdf",
            headers={"X-Tenant-Slug": "test-legal-aid"},
        )
        assert resp.status_code == 401

    async def test_export_invalid_format_returns_400(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/xlsx returns 400 for unsupported format."""
        headers = await _register_and_get_headers(async_client)
        doc_id = await self._generate_doc(async_client, headers)

        resp = await async_client.get(f"/api/v1/output/{doc_id}/export/xlsx", headers=headers)
        assert resp.status_code == 400

    async def _generate_rich_doc(self, async_client: AsyncClient, headers: dict) -> int:
        """Generate a document whose assembled context carries real structured
        content (claims, deadlines, executive summary) so the JSON export seam
        can be exercised end-to-end.
        """
        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import (
                CIRACSection,
                DeadlineRef,
                GapReport,
                OutputContext,
                OutputProfile,
                TriageResult,
            )

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=7, run_id=7, org_id=1, matter_title="Rich Export Matter",
                generated_at=datetime(2026, 1, 15), completeness_score=0.9,
                claims_by_jurisdiction={
                    "California": [
                        CIRACSection(
                            claim_id=1, claim_name="Breach of Warranty of Habitability",
                            claim_type="primary", confidence=0.88, jurisdiction="California",
                            issue_statement="Whether the landlord breached the warranty.",
                            conclusion="The facts support a habitability claim.",
                        )
                    ]
                },
                deadlines=[
                    DeadlineRef(
                        event_text="Answer due", computed_date="2026-03-17", urgency="urgent"
                    )
                ],
                executive_summary="Tenant has a strong habitability claim under California law.",
                gap_report=GapReport(completeness_score=0.9),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )
            mock_triage = MagicMock()
            mock_triage_cls.return_value = mock_triage
            mock_triage.score.return_value = TriageResult()
            mock_action = MagicMock()
            mock_action_cls.return_value = mock_action
            mock_action.generate.return_value = []
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.render_full.return_value = "# Rich export markdown"

            gen_resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 7, "intake_id": 7, "profile_types": ["law_firm"]},
                headers=headers,
            )
            assert gen_resp.status_code == 201
            return gen_resp.json()["documents"][0]["id"]

    async def test_export_json_is_not_empty_shell(self, async_client: AsyncClient) -> None:
        """BUG-18 regression: the JSON export must carry the structured content
        assembled at generation, not an empty shell rebuilt at export time.

        This exercises the generate->export seam that unit tests missed: the
        adapter unit test hands a rich context in directly and passes, while the
        real pipeline persisted only markdown and rebuilt an EMPTY context on
        export. Assert claims / deadlines / executive_summary survive.
        """
        headers = await _register_and_get_headers(async_client)
        doc_id = await self._generate_rich_doc(async_client, headers)

        resp = await async_client.get(f"/api/v1/output/{doc_id}/export/json", headers=headers)
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        data = json.loads(resp.content.decode("utf-8"))

        # The core regression assertions: these were {} / [] / "" before the fix.
        assert data["claims_by_jurisdiction"], "JSON export lost claims_by_jurisdiction"
        assert "California" in data["claims_by_jurisdiction"]
        assert data["claims_by_jurisdiction"]["California"][0]["claim_name"] == (
            "Breach of Warranty of Habitability"
        )
        assert data["deadlines"], "JSON export lost deadlines"
        assert data["deadlines"][0]["computed_date"] == "2026-03-17"
        assert data["executive_summary"], "JSON export lost executive_summary"
        assert data["matter_title"] == "Rich Export Matter"
