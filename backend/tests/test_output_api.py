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
# Helper: create a valid JWT for test requests
# ---------------------------------------------------------------------------


def _make_auth_header(role: str = "professional") -> dict[str, str]:
    """Create an Authorization header with a valid test JWT."""
    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": "1", "email": "test@test.com", "org_id": 1, "role": role}
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_output_doc(
    doc_id: int = 1,
    run_id: int = 1,
    intake_id: int = 1,
    profile_type: str = "law_firm",
    markdown_content: str = "# Test output",
) -> SimpleNamespace:
    """Create a mock OutputDocument."""
    return SimpleNamespace(
        id=doc_id,
        run_id=run_id,
        intake_id=intake_id,
        profile_type=profile_type,
        markdown_content=markdown_content,
        rendered_pdf=None,
        rendered_docx=None,
        rendered_json=None,
        metadata_json={"completeness_score": 0.75},
        created_at=datetime(2026, 1, 15, 10, 30, 0),
    )


# ---------------------------------------------------------------------------
# Router registration test
# ---------------------------------------------------------------------------


class TestOutputRouterRegistration:
    """Test that the output router is wired into main.py."""

    def test_output_router_registered(self) -> None:
        """Output router should be included in the FastAPI app."""
        from app.main import app

        routes = [r.path for r in app.routes]
        # Check for at least one output endpoint pattern
        output_routes = [r for r in routes if "/output" in r]
        assert len(output_routes) > 0, "No /output routes found in app"


# ---------------------------------------------------------------------------
# Generation endpoint tests
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    """Tests for POST /api/v1/output/generate."""

    async def test_generate_returns_201(self, async_client: AsyncClient) -> None:
        """POST /generate with valid data returns 201."""
        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            # Setup mocks
            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler

            from app.services.output.schemas import (
                GapReport,
                OutputContext,
                OutputProfile,
                TriageResult,
            )

            mock_ctx = OutputContext(
                intake_id=1,
                run_id=1,
                org_id=1,
                matter_title="Test Matter",
                generated_at=datetime(2026, 1, 15),
                completeness_score=0.75,
                gap_report=GapReport(completeness_score=0.75),
                profile=OutputProfile(profile_type="law_firm", language_level="professional"),
            )
            mock_assembler.assemble.return_value = mock_ctx

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
                headers=_make_auth_header(),
            )
            assert resp.status_code == 201
            data = resp.json()
            assert "documents" in data
            assert len(data["documents"]) >= 1

    async def test_generate_multiple_profiles(self, async_client: AsyncClient) -> None:
        """POST /generate with multiple profile_types creates multiple documents."""
        with (
            patch("app.routers.output.DataAssembler") as mock_assembler_cls,
            patch("app.routers.output.TriageScorer") as mock_triage_cls,
            patch("app.routers.output.ActionItemGenerator") as mock_action_cls,
            patch("app.routers.output.TemplateEngine") as mock_engine_cls,
        ):
            from app.services.output.schemas import (
                GapReport,
                OutputContext,
                OutputProfile,
                TriageResult,
            )

            mock_assembler = AsyncMock()
            mock_assembler_cls.return_value = mock_assembler
            mock_assembler.assemble.return_value = OutputContext(
                intake_id=1,
                run_id=1,
                org_id=1,
                matter_title="Test",
                generated_at=datetime(2026, 1, 15),
                completeness_score=0.5,
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
                headers=_make_auth_header(),
            )
            assert resp.status_code == 201
            data = resp.json()
            assert len(data["documents"]) == 2

    async def test_generate_requires_auth(self, async_client: AsyncClient) -> None:
        """POST /generate without auth token returns 401."""
        resp = await async_client.post(
            "/api/v1/output/generate",
            json={"run_id": 1, "intake_id": 1},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Retrieval endpoint tests
# ---------------------------------------------------------------------------


class TestRetrievalEndpoints:
    """Tests for GET output endpoints."""

    async def test_get_document_detail(self, async_client: AsyncClient) -> None:
        """GET /output/{id} returns document detail."""
        # First generate a document
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
                headers=_make_auth_header(),
            )
            assert gen_resp.status_code == 201
            doc_id = gen_resp.json()["documents"][0]["id"]

        # Now retrieve it
        resp = await async_client.get(
            f"/api/v1/output/{doc_id}",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert "markdown_content" in data

    async def test_list_outputs_by_intake(self, async_client: AsyncClient) -> None:
        """GET /output/intake/{intake_id} lists documents."""
        # Generate first
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
                headers=_make_auth_header(),
            )

        resp = await async_client.get(
            "/api/v1/output/intake/42",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_nonexistent_document_returns_404(self, async_client: AsyncClient) -> None:
        """GET /output/99999 returns 404."""
        resp = await async_client.get(
            "/api/v1/output/99999",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Export endpoint tests
# ---------------------------------------------------------------------------


class TestExportEndpoints:
    """Tests for GET /output/{id}/export/{format}."""

    async def test_export_pdf_content_type(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/pdf returns application/pdf Content-Type."""
        # Generate a document first
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
                headers=_make_auth_header(),
            )
            doc_id = gen_resp.json()["documents"][0]["id"]

        resp = await async_client.get(
            f"/api/v1/output/{doc_id}/export/pdf",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]

    async def test_export_docx_content_type(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/docx returns OOXML Content-Type."""
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
                intake_id=1, run_id=1, org_id=1, matter_title="DOCX Test",
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
            mock_engine.render_full.return_value = "# DOCX test"

            gen_resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm"]},
                headers=_make_auth_header(),
            )
            doc_id = gen_resp.json()["documents"][0]["id"]

        resp = await async_client.get(
            f"/api/v1/output/{doc_id}/export/docx",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 200
        assert "openxmlformats" in resp.headers["content-type"]

    async def test_export_requires_auth(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/pdf without auth returns 401."""
        resp = await async_client.get("/api/v1/output/1/export/pdf")
        assert resp.status_code == 401

    async def test_export_invalid_format_returns_400(self, async_client: AsyncClient) -> None:
        """GET /output/{id}/export/xlsx returns 400 for unsupported format."""
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
            mock_engine.render_full.return_value = "# Test"

            gen_resp = await async_client.post(
                "/api/v1/output/generate",
                json={"run_id": 1, "intake_id": 1, "profile_types": ["law_firm"]},
                headers=_make_auth_header(),
            )
            doc_id = gen_resp.json()["documents"][0]["id"]

        resp = await async_client.get(
            f"/api/v1/output/{doc_id}/export/xlsx",
            headers=_make_auth_header(),
        )
        assert resp.status_code == 400
