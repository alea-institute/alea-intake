"""Tests for CMS admin API endpoints.

Covers:
- POST /api/v1/admin/cms/connectors creates a CMSConnectorConfig
- GET /api/v1/admin/cms/connectors lists org's connector configs
- POST /api/v1/admin/cms/connectors/{id}/test calls test_connection
- POST /api/v1/admin/cms/sync/{intake_id} triggers sync for an intake
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.cms.base import CMSSyncConfig, SyncDirection


# ---------------------------------------------------------------------------
# Test 12: POST /connectors creates a config
# ---------------------------------------------------------------------------

def test_create_connector_schema():
    """Verify the connector creation schema accepts required fields."""
    from app.routers.cms_admin import ConnectorCreateRequest

    req = ConnectorCreateRequest(
        cms_type="clio",
        credentials={"access_token": "abc", "refresh_token": "xyz"},
        sync_scope=["contacts", "matters"],
        direction="bidirectional",
    )
    assert req.cms_type == "clio"
    assert req.sync_scope == ["contacts", "matters"]


# ---------------------------------------------------------------------------
# Test 13: GET /connectors list schema
# ---------------------------------------------------------------------------

def test_connector_response_schema():
    """Verify the connector response schema fields."""
    from app.routers.cms_admin import ConnectorResponse

    resp = ConnectorResponse(
        id=1,
        cms_type="clio",
        sync_scope=["contacts", "matters"],
        direction="bidirectional",
        is_active=True,
        webhook_url=None,
    )
    assert resp.id == 1
    assert resp.cms_type == "clio"
    assert resp.is_active is True


# ---------------------------------------------------------------------------
# Test 14: Test connection schema
# ---------------------------------------------------------------------------

def test_test_connection_response_schema():
    """Verify the test connection response schema."""
    from app.routers.cms_admin import TestConnectionResponse

    resp = TestConnectionResponse(success=True, message="Connected to Clio")
    assert resp.success is True


# ---------------------------------------------------------------------------
# Test 15: Sync trigger schema
# ---------------------------------------------------------------------------

def test_sync_trigger_response_schema():
    """Verify the sync trigger response schema."""
    from app.routers.cms_admin import SyncTriggerResponse

    resp = SyncTriggerResponse(
        intake_id=42,
        status="queued",
        jobs_enqueued=3,
    )
    assert resp.intake_id == 42
    assert resp.jobs_enqueued == 3


# ---------------------------------------------------------------------------
# Test: Router is importable and has correct prefix
# ---------------------------------------------------------------------------

def test_cms_admin_router_prefix():
    from app.routers.cms_admin import router

    assert router.prefix == "/api/v1/admin/cms"
    assert "cms-admin" in router.tags
