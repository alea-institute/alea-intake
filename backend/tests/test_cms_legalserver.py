"""Tests for LegalServer CMS adapter.

Covers:
- adapter_name returns "legalserver"
- push_matter pushes to /matters endpoint
- Uses API key auth (not OAuth)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.cms.base import CMSSyncConfig, SyncDirection


def _make_legalserver_config() -> CMSSyncConfig:
    """Create a test LegalServer config."""
    return CMSSyncConfig(
        cms_type="legalserver",
        credentials_encrypted=b"api-key-data",
        sync_scope=["matters"],
        direction=SyncDirection.PUSH,
    )


# ---------------------------------------------------------------------------
# Test 10: adapter_name
# ---------------------------------------------------------------------------

def test_legalserver_adapter_name():
    from app.integrations.cms.legalserver import LegalServerAdapter

    adapter = LegalServerAdapter(config=_make_legalserver_config())
    assert adapter.adapter_name == "legalserver"


# ---------------------------------------------------------------------------
# Test 11: push_matter pushes to /matters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legalserver_push_matter():
    from app.integrations.cms.legalserver import LegalServerAdapter

    adapter = LegalServerAdapter(config=_make_legalserver_config())

    mock_response = httpx.Response(
        200,
        json={"id": "LS-999", "matter_name": "Test Matter"},
        request=httpx.Request("POST", "https://demo.legalserver.org/api/v1/matters"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_matter({
            "description": "Eviction defense",
            "status": "open",
            "practice_area": "housing",
            "client_id": "c456",
        })

    assert result == "LS-999"
    call_url = mock_client.post.call_args[0][0]
    assert "/matters" in call_url


# ---------------------------------------------------------------------------
# Test 12: Uses API key auth (not OAuth)
# ---------------------------------------------------------------------------

def test_legalserver_uses_api_key_auth():
    from app.integrations.cms.legalserver import LegalServerAdapter

    adapter = LegalServerAdapter(config=_make_legalserver_config())

    # LegalServer should use API key header, not OAuth bearer
    headers = adapter._get_auth_headers()
    assert "X-API-Key" in headers or "Authorization" in headers
    # Should not be a Bearer token pattern
    if "Authorization" in headers:
        assert not headers["Authorization"].startswith("Bearer ")


# ---------------------------------------------------------------------------
# Test: test_connection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legalserver_test_connection():
    from app.integrations.cms.legalserver import LegalServerAdapter

    adapter = LegalServerAdapter(config=_make_legalserver_config())

    mock_response = httpx.Response(
        200,
        json={"status": "ok"},
        request=httpx.Request("GET", "https://demo.legalserver.org/api/v1/status"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await adapter.test_connection()

    assert result is True


# ---------------------------------------------------------------------------
# Test: push_contact creates participant on matter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legalserver_push_contact():
    from app.integrations.cms.legalserver import LegalServerAdapter

    adapter = LegalServerAdapter(config=_make_legalserver_config())

    mock_response = httpx.Response(
        200,
        json={"id": "P-100", "name": "Jane Doe"},
        request=httpx.Request("POST", "https://demo.legalserver.org/api/v1/participants"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_contact({
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "type": "person",
        })

    assert result == "P-100"
