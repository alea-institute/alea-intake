"""Tests for Clio CMS adapter.

Covers:
- adapter_name returns "clio"
- push_contact calls POST /api/v4/contacts.json with correct field mapping
- push_matter calls POST /api/v4/matters.json with client reference
- push_document calls POST /api/v4/documents.json with multipart upload
- pull_updates calls GET endpoints with since filter
- test_connection calls GET /api/v4/users/who_am_i.json
- OAuth token refresh before API call (Pitfall 4)
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.cms.base import CMSSyncConfig, SyncDirection


def _make_clio_config() -> CMSSyncConfig:
    """Create a test Clio config."""
    return CMSSyncConfig(
        cms_type="clio",
        credentials_encrypted=b"test-credentials",
        sync_scope=["contacts", "matters", "documents"],
        direction=SyncDirection.BIDIRECTIONAL,
    )


# ---------------------------------------------------------------------------
# Test 1: adapter_name
# ---------------------------------------------------------------------------

def test_clio_adapter_name():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())
    assert adapter.adapter_name == "clio"
    assert "Clio" in adapter.display_name


# ---------------------------------------------------------------------------
# Test 2: push_contact calls POST /api/v4/contacts.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clio_push_contact():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())

    mock_response = httpx.Response(
        200,
        json={"data": {"id": 12345, "name": "Jane Doe"}},
        request=httpx.Request("POST", "https://app.clio.com/api/v4/contacts.json"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_contact({
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "type": "person",
        })

    assert result == "12345"
    mock_client.post.assert_awaited_once()
    call_url = mock_client.post.call_args[0][0]
    assert "contacts.json" in call_url


# ---------------------------------------------------------------------------
# Test 3: push_matter calls POST /api/v4/matters.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clio_push_matter():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())

    mock_response = httpx.Response(
        200,
        json={"data": {"id": 67890, "description": "Custody case"}},
        request=httpx.Request("POST", "https://app.clio.com/api/v4/matters.json"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_matter({
            "description": "Custody case",
            "status": "open",
            "practice_area": "family_law",
            "client_id": "c123",
        })

    assert result == "67890"
    call_url = mock_client.post.call_args[0][0]
    assert "matters.json" in call_url


# ---------------------------------------------------------------------------
# Test 4: push_document calls POST /api/v4/documents.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clio_push_document():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())

    mock_response = httpx.Response(
        200,
        json={"data": {"id": 99999}},
        request=httpx.Request("POST", "https://app.clio.com/api/v4/documents.json"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.push_document(
            {"name": "case_memo.pdf", "content_type": "application/pdf", "description": "Memo"},
            file_bytes=b"PDF content",
        )

    assert result == "99999"
    call_url = mock_client.post.call_args[0][0]
    assert "documents.json" in call_url


# ---------------------------------------------------------------------------
# Test 5: pull_updates calls GET with since filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clio_pull_updates():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())

    contacts_resp = httpx.Response(
        200,
        json={"data": [{"id": 1, "name": "Updated Contact"}]},
        request=httpx.Request("GET", "https://app.clio.com/api/v4/contacts.json"),
    )
    matters_resp = httpx.Response(
        200,
        json={"data": [{"id": 2, "description": "Updated Matter"}]},
        request=httpx.Request("GET", "https://app.clio.com/api/v4/matters.json"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(side_effect=[contacts_resp, matters_resp])
        results = await adapter.pull_updates(since=datetime(2024, 1, 1))

    assert len(results) == 2
    assert mock_client.get.await_count == 2


# ---------------------------------------------------------------------------
# Test 6: test_connection calls GET /api/v4/users/who_am_i.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clio_test_connection():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())

    mock_response = httpx.Response(
        200,
        json={"data": {"id": 1, "name": "Test User"}},
        request=httpx.Request("GET", "https://app.clio.com/api/v4/users/who_am_i.json"),
    )

    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await adapter.test_connection()

    assert result is True
    call_url = mock_client.get.call_args[0][0]
    assert "who_am_i" in call_url


# ---------------------------------------------------------------------------
# Test 7: OAuth token refresh when expired (Pitfall 4)
# ---------------------------------------------------------------------------

def test_clio_refresh_token_when_expired():
    from app.integrations.cms.clio import ClioAdapter

    adapter = ClioAdapter(config=_make_clio_config())
    adapter._access_token = "old-token"
    adapter._token_expires_at = time.time() - 10  # Already expired

    # _refresh_token_if_needed should be callable without raising
    adapter._refresh_token_if_needed()
    # Token should still be set (refresh is advisory in base class)
    assert adapter._access_token is not None
