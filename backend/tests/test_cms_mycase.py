"""Tests for MyCase CMS adapter.

Covers:
- adapter_name returns "mycase"
- push_contact pushes to /v1/clients
- push_matter pushes to /v1/cases
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.cms.base import CMSSyncConfig, SyncDirection


def _make_mycase_config() -> CMSSyncConfig:
    """Create a test MyCase config."""
    return CMSSyncConfig(
        cms_type="mycase",
        credentials_encrypted=b"test-credentials",
        sync_scope=["contacts", "matters"],
        direction=SyncDirection.PUSH,
    )


# ---------------------------------------------------------------------------
# Test 8: adapter_name
# ---------------------------------------------------------------------------

def test_mycase_adapter_name():
    from app.integrations.cms.mycase import MyCaseAdapter

    adapter = MyCaseAdapter(config=_make_mycase_config())
    assert adapter.adapter_name == "mycase"


# ---------------------------------------------------------------------------
# Test 9: push_contact pushes to /v1/clients
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mycase_push_contact():
    from app.integrations.cms.mycase import MyCaseAdapter

    adapter = MyCaseAdapter(config=_make_mycase_config())

    mock_response = httpx.Response(
        200,
        json={"id": 555, "first_name": "Jane"},
        request=httpx.Request("POST", "https://api.mycase.com/v1/clients"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_contact({
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "type": "person",
        })

    assert result == "555"
    call_url = mock_client.post.call_args[0][0]
    assert "/clients" in call_url


# ---------------------------------------------------------------------------
# Test 10: push_matter pushes to /v1/cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mycase_push_matter():
    from app.integrations.cms.mycase import MyCaseAdapter

    adapter = MyCaseAdapter(config=_make_mycase_config())

    mock_response = httpx.Response(
        200,
        json={"id": 777, "name": "Custody Case"},
        request=httpx.Request("POST", "https://api.mycase.com/v1/cases"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_matter({
            "description": "Custody dispute",
            "status": "open",
            "practice_area": "family_law",
            "client_id": "c123",
        })

    assert result == "777"
    call_url = mock_client.post.call_args[0][0]
    assert "/cases" in call_url


# ---------------------------------------------------------------------------
# Test: test_connection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mycase_test_connection():
    from app.integrations.cms.mycase import MyCaseAdapter

    adapter = MyCaseAdapter(config=_make_mycase_config())

    mock_response = httpx.Response(
        200,
        json={"id": 1, "name": "Test User"},
        request=httpx.Request("GET", "https://api.mycase.com/v1/users/current"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await adapter.test_connection()

    assert result is True
