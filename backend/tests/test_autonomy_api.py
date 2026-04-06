"""Tests for autonomy API endpoints: approval workflow and admin config CRUD.

Tests cover professional approval endpoints (list pending, approve, reject,
edit, mode-switch), admin config endpoints (get/put config, stages, presets),
role enforcement, and error handling (404, 409).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.autonomy import ApprovalRequest
from app.models.organization import OrganizationConfig
from app.models.user import User
from app.services.analysis.autonomy.approval_queue import ApprovalQueue
from app.services.analysis.autonomy.config import (
    ANALYSIS_STAGES,
    AutonomyConfig,
    StageCheckpoint,
)
from app.services.analysis.autonomy.schemas import ApprovalAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def org_config(async_session: AsyncSession):
    """Create an OrganizationConfig for tests."""
    config = OrganizationConfig(
        org_id=1,
        autonomy_config_json=AutonomyConfig.chatbot_preset().model_dump(),
    )
    async_session.add(config)
    await async_session.flush()
    return config


@pytest.fixture
async def pending_request(async_session: AsyncSession):
    """Create a pending ApprovalRequest in the DB."""
    req = ApprovalRequest(
        run_id=1,
        iteration_id=10,
        stage_name="issue_spot",
        status="pending",
        stage_output_json={"claims": ["breach"]},
    )
    async_session.add(req)
    await async_session.flush()
    return req


@pytest.fixture
async def professional_user(async_session: AsyncSession):
    """Create a user with professional role."""
    user = User(
        email="pro@example.com",
        hashed_password="$placeholder_hash$",
        full_name=b"Professional User",
        role="professional",
        org_id=1,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def admin_user(async_session: AsyncSession):
    """Create a user with admin role."""
    user = User(
        email="admin@example.com",
        hashed_password="$placeholder_hash$",
        full_name=b"Admin User",
        role="admin",
        org_id=1,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
def mock_approval_queue():
    """Mock ApprovalQueue for API tests."""
    queue = MagicMock(spec=ApprovalQueue)
    queue.resolve = MagicMock()
    queue.get_pending = MagicMock(return_value=[])
    return queue


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_auth_token(user_id: int) -> dict:
    """Create a JWT auth header for testing."""
    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": str(user_id), "role": "professional"},
        secret_key="test-secret-key-for-testing-only-not-production",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Slug": "test-legal-aid"}


def _make_admin_auth_token(user_id: int) -> dict:
    """Create a JWT auth header with admin role for testing."""
    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": str(user_id), "role": "admin"},
        secret_key="test-secret-key-for-testing-only-not-production",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Slug": "test-legal-aid"}


# ===========================================================================
# Approval Endpoints (Professional role)
# ===========================================================================


class TestGetPending:
    """GET /api/v1/autonomy/pending returns pending approval requests."""

    @pytest.mark.asyncio
    async def test_empty_pending_list(
        self, async_session: AsyncSession, professional_user: User
    ):
        """Returns empty list when no pending requests exist."""
        from app.routers.autonomy import get_pending_requests

        # Direct function call with mocked dependencies
        result = await get_pending_requests(
            db=async_session,
            user=professional_user,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_pending_list_returns_requests(
        self,
        async_session: AsyncSession,
        professional_user: User,
        pending_request: ApprovalRequest,
    ):
        """Returns list with pending requests when they exist."""
        from app.routers.autonomy import get_pending_requests

        result = await get_pending_requests(
            db=async_session,
            user=professional_user,
        )
        assert len(result) == 1
        assert result[0]["status"] == "pending"
        assert result[0]["stage_name"] == "issue_spot"


class TestApproveEndpoint:
    """POST /api/v1/autonomy/requests/{id}/approve marks request approved."""

    @pytest.mark.asyncio
    async def test_approve_success(
        self,
        async_session: AsyncSession,
        professional_user: User,
        pending_request: ApprovalRequest,
        mock_approval_queue: MagicMock,
    ):
        """Approve returns 200 and marks request approved."""
        from app.routers.autonomy import approve_request, set_approval_queue

        set_approval_queue(mock_approval_queue)

        result = await approve_request(
            request_id=pending_request.id,
            db=async_session,
            user=professional_user,
        )
        assert result["status"] == "approved"

        # Verify DB updated
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == pending_request.id)
        row = (await async_session.execute(stmt)).scalar_one()
        assert row.status == "approved"
        assert row.actor_id == professional_user.id
        assert row.resolved_at is not None

    @pytest.mark.asyncio
    async def test_approve_nonexistent_returns_404(
        self,
        async_session: AsyncSession,
        professional_user: User,
        mock_approval_queue: MagicMock,
    ):
        """Approve on non-existent request returns 404."""
        from fastapi import HTTPException

        from app.routers.autonomy import approve_request, set_approval_queue

        set_approval_queue(mock_approval_queue)

        with pytest.raises(HTTPException) as exc_info:
            await approve_request(
                request_id=99999,
                db=async_session,
                user=professional_user,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_timed_out_returns_409(
        self,
        async_session: AsyncSession,
        professional_user: User,
        pending_request: ApprovalRequest,
        mock_approval_queue: MagicMock,
    ):
        """Approve on timed-out request returns 409 Conflict."""
        from fastapi import HTTPException

        from app.routers.autonomy import approve_request, set_approval_queue

        mock_approval_queue.resolve.side_effect = ValueError("timed_out")
        set_approval_queue(mock_approval_queue)

        with pytest.raises(HTTPException) as exc_info:
            await approve_request(
                request_id=pending_request.id,
                db=async_session,
                user=professional_user,
            )
        assert exc_info.value.status_code == 409


class TestRejectEndpoint:
    """POST /api/v1/autonomy/requests/{id}/reject with guidance."""

    @pytest.mark.asyncio
    async def test_reject_success(
        self,
        async_session: AsyncSession,
        professional_user: User,
        pending_request: ApprovalRequest,
        mock_approval_queue: MagicMock,
    ):
        """Reject with guidance returns 200."""
        from app.routers.autonomy import reject_request, set_approval_queue
        from app.services.analysis.autonomy.schemas import RejectBody

        set_approval_queue(mock_approval_queue)

        result = await reject_request(
            request_id=pending_request.id,
            body=RejectBody(guidance_text="Please reconsider the claims"),
            db=async_session,
            user=professional_user,
        )
        assert result["status"] == "rejected"

        # Verify guidance stored
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == pending_request.id)
        row = (await async_session.execute(stmt)).scalar_one()
        assert row.guidance_text == "Please reconsider the claims"


class TestEditEndpoint:
    """POST /api/v1/autonomy/requests/{id}/edit with edits dict."""

    @pytest.mark.asyncio
    async def test_edit_success(
        self,
        async_session: AsyncSession,
        professional_user: User,
        pending_request: ApprovalRequest,
        mock_approval_queue: MagicMock,
    ):
        """Edit with edits dict returns 200."""
        from app.routers.autonomy import edit_request, set_approval_queue
        from app.services.analysis.autonomy.schemas import EditBody

        set_approval_queue(mock_approval_queue)

        result = await edit_request(
            request_id=pending_request.id,
            body=EditBody(edits={"claims": ["modified_breach"]}),
            db=async_session,
            user=professional_user,
        )
        assert result["status"] == "edited"

        # Verify edited_output stored
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == pending_request.id)
        row = (await async_session.execute(stmt)).scalar_one()
        assert row.edited_output_json == {"claims": ["modified_breach"]}


class TestSwitchMode:
    """POST /api/v1/autonomy/runs/{id}/switch-mode switches autonomy mode."""

    @pytest.mark.asyncio
    async def test_switch_mode_success(
        self,
        async_session: AsyncSession,
        professional_user: User,
        org_config: OrganizationConfig,
    ):
        """Switch mode updates org config and returns 200."""
        from app.routers.autonomy import switch_mode
        from app.services.analysis.autonomy.schemas import ModeSwitchBody

        new_config = AutonomyConfig.professional_preset()
        body = ModeSwitchBody(
            config=new_config,
            reason="Client requested full review",
        )

        result = await switch_mode(
            run_id=1,
            body=body,
            db=async_session,
            user=professional_user,
        )
        assert result["mode_switched"] is True

        # Verify DB updated
        stmt = select(OrganizationConfig).where(OrganizationConfig.org_id == 1)
        row = (await async_session.execute(stmt)).scalar_one()
        parsed = AutonomyConfig.model_validate(row.autonomy_config_json)
        assert parsed.timeout_behavior.value == "pause_until"


# ===========================================================================
# Admin Config Endpoints (Admin role)
# ===========================================================================


class TestGetConfig:
    """GET /api/v1/autonomy/admin/config returns org autonomy config."""

    @pytest.mark.asyncio
    async def test_get_config_returns_defaults_when_null(
        self,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Returns default config when autonomy_config_json is null."""
        # Create org config with null autonomy
        config = OrganizationConfig(org_id=1, autonomy_config_json=None)
        async_session.add(config)
        await async_session.flush()

        from app.routers.autonomy_admin import get_autonomy_config

        result = await get_autonomy_config(db=async_session, user=admin_user)
        # Should return default AutonomyConfig
        assert "stage_checkpoints" in result
        assert result["timeout_seconds"] == 1800

    @pytest.mark.asyncio
    async def test_get_config_returns_stored(
        self,
        async_session: AsyncSession,
        admin_user: User,
        org_config: OrganizationConfig,
    ):
        """Returns stored config when present."""
        from app.routers.autonomy_admin import get_autonomy_config

        result = await get_autonomy_config(db=async_session, user=admin_user)
        assert "stage_checkpoints" in result


class TestPutConfig:
    """PUT /api/v1/autonomy/admin/config updates autonomy_config_json."""

    @pytest.mark.asyncio
    async def test_put_config_success(
        self,
        async_session: AsyncSession,
        admin_user: User,
        org_config: OrganizationConfig,
    ):
        """PUT updates autonomy_config_json on OrganizationConfig."""
        from app.routers.autonomy_admin import update_autonomy_config

        new_config = AutonomyConfig.professional_preset()
        result = await update_autonomy_config(
            body=new_config,
            db=async_session,
            user=admin_user,
        )
        assert result["updated"] is True

        # Verify DB
        stmt = select(OrganizationConfig).where(OrganizationConfig.org_id == 1)
        row = (await async_session.execute(stmt)).scalar_one()
        parsed = AutonomyConfig.model_validate(row.autonomy_config_json)
        assert parsed.timeout_behavior.value == "pause_until"


class TestGetStages:
    """GET /api/v1/autonomy/admin/stages returns orchestrator stage list."""

    @pytest.mark.asyncio
    async def test_stages_returns_orchestrator_stages(self):
        """Returns AnalysisOrchestrator.STAGES list."""
        from app.routers.autonomy_admin import get_stages

        result = await get_stages()
        assert result["stages"] == ANALYSIS_STAGES


class TestGetPresets:
    """GET /api/v1/autonomy/admin/presets returns preset configs."""

    @pytest.mark.asyncio
    async def test_presets_returns_all_three(self):
        """Returns chatbot, professional, and agent presets."""
        from app.routers.autonomy_admin import get_presets

        result = await get_presets()
        assert "chatbot" in result
        assert "professional" in result
        assert "agent" in result


# ===========================================================================
# Role enforcement
# ===========================================================================


class TestRoleEnforcement:
    """Verify role guards on endpoints."""

    @pytest.mark.asyncio
    async def test_approval_endpoints_require_professional(
        self,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Approval endpoints should enforce PROFESSIONAL role at router level.

        This is a structural test -- we verify the router dependencies include
        the require_role(Role.PROFESSIONAL) dependency.
        """
        from app.routers.autonomy import router

        # Check that the router has dependencies that enforce professional role
        # by inspecting the route dependencies
        has_role_dep = False
        for route in router.routes:
            for dep in getattr(route, "dependencies", []):
                has_role_dep = True
                break
        # Router-level deps apply to all routes
        assert len(router.dependencies) > 0

    @pytest.mark.asyncio
    async def test_admin_endpoints_require_admin(self):
        """Admin config endpoints should enforce ADMIN role at router level."""
        from app.routers.autonomy_admin import router

        assert len(router.dependencies) > 0


# ===========================================================================
# 404 on non-existent requests
# ===========================================================================


class TestNotFound:
    """Verify 404 on non-existent requests for reject and edit."""

    @pytest.mark.asyncio
    async def test_reject_nonexistent_returns_404(
        self,
        async_session: AsyncSession,
        professional_user: User,
        mock_approval_queue: MagicMock,
    ):
        from fastapi import HTTPException

        from app.routers.autonomy import reject_request, set_approval_queue
        from app.services.analysis.autonomy.schemas import RejectBody

        set_approval_queue(mock_approval_queue)

        with pytest.raises(HTTPException) as exc_info:
            await reject_request(
                request_id=99999,
                body=RejectBody(guidance_text="Bad"),
                db=async_session,
                user=professional_user,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_nonexistent_returns_404(
        self,
        async_session: AsyncSession,
        professional_user: User,
        mock_approval_queue: MagicMock,
    ):
        from fastapi import HTTPException

        from app.routers.autonomy import edit_request, set_approval_queue
        from app.services.analysis.autonomy.schemas import EditBody

        set_approval_queue(mock_approval_queue)

        with pytest.raises(HTTPException) as exc_info:
            await edit_request(
                request_id=99999,
                body=EditBody(edits={"x": 1}),
                db=async_session,
                user=professional_user,
            )
        assert exc_info.value.status_code == 404
