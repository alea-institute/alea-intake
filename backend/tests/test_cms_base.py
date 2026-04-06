"""Tests for CMS adapter ABC, sync queue, field mapping, and models.

Covers:
- SyncDirection enum values
- CMSSyncConfig dataclass fields
- CMSAdapter ABC contract enforcement
- CMSSyncQueue enqueue/process operations
- CMSSyncQueue error handling (graceful failures)
- field_mapping canonical dict outputs
- CMSSyncRecord and CMSConnectorConfig model fields
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: SyncDirection enum
# ---------------------------------------------------------------------------

def test_sync_direction_enum():
    from app.integrations.cms.base import SyncDirection

    assert SyncDirection.PUSH.value == "push"
    assert SyncDirection.PULL.value == "pull"
    assert SyncDirection.BIDIRECTIONAL.value == "bidirectional"
    # Ensure exactly 3 members
    assert len(SyncDirection) == 3


# ---------------------------------------------------------------------------
# Test 2: CMSSyncConfig dataclass
# ---------------------------------------------------------------------------

def test_cms_sync_config_fields():
    from app.integrations.cms.base import CMSSyncConfig, SyncDirection

    config = CMSSyncConfig(
        cms_type="clio",
        credentials_encrypted=b"secret",
        sync_scope=["contacts", "matters"],
        direction=SyncDirection.BIDIRECTIONAL,
        webhook_url="https://example.com/webhook",
    )

    assert config.cms_type == "clio"
    assert config.credentials_encrypted == b"secret"
    assert config.sync_scope == ["contacts", "matters"]
    assert config.direction == SyncDirection.BIDIRECTIONAL
    assert config.webhook_url == "https://example.com/webhook"


def test_cms_sync_config_default_webhook():
    from app.integrations.cms.base import CMSSyncConfig, SyncDirection

    config = CMSSyncConfig(
        cms_type="mycase",
        credentials_encrypted=b"key",
        sync_scope=["contacts"],
        direction=SyncDirection.PUSH,
    )
    assert config.webhook_url is None


# ---------------------------------------------------------------------------
# Test 3: CMSAdapter ABC requires push/pull/webhook/test_connection
# ---------------------------------------------------------------------------

def test_cms_adapter_abc_cannot_instantiate():
    from app.integrations.cms.base import CMSAdapter

    with pytest.raises(TypeError):
        CMSAdapter()  # type: ignore[abstract]


def test_cms_adapter_abc_concrete_implementation():
    from app.integrations.cms.base import CMSAdapter

    class ConcreteAdapter(CMSAdapter):
        @property
        def adapter_name(self) -> str:
            return "test_adapter"

        async def push_contact(self, contact_data: dict) -> str:
            return "c1"

        async def push_matter(self, matter_data: dict) -> str:
            return "m1"

        async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
            return "d1"

        async def pull_updates(self, since: datetime) -> list[dict]:
            return []

        async def handle_webhook(self, payload: dict) -> None:
            pass

        async def test_connection(self) -> bool:
            return True

    adapter = ConcreteAdapter()
    assert adapter.adapter_name == "test_adapter"
    assert adapter.display_name == "Test Adapter"


# ---------------------------------------------------------------------------
# Test 4: CMSSyncQueue enqueue and process_next
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_queue_enqueue_and_process():
    from app.integrations.cms.base import CMSAdapter
    from app.integrations.cms.sync_queue import CMSSyncQueue, SyncJob

    mock_adapter = AsyncMock(spec=CMSAdapter)
    mock_adapter.push_contact = AsyncMock(return_value="c123")

    queue = CMSSyncQueue()
    job = SyncJob(
        adapter=mock_adapter,
        method="push_contact",
        args={"contact_data": {"name": "Test"}},
    )

    await queue.enqueue(job)
    result = await queue.process_next()

    assert result is not None
    mock_adapter.push_contact.assert_awaited_once_with(contact_data={"name": "Test"})


# ---------------------------------------------------------------------------
# Test 5: CMSSyncQueue handles errors gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_queue_handles_errors_gracefully():
    from app.integrations.cms.base import CMSAdapter
    from app.integrations.cms.sync_queue import CMSSyncQueue, SyncJob

    mock_adapter = AsyncMock(spec=CMSAdapter)
    mock_adapter.push_contact = AsyncMock(side_effect=ConnectionError("API down"))

    queue = CMSSyncQueue()
    job = SyncJob(
        adapter=mock_adapter,
        method="push_contact",
        args={"contact_data": {"name": "Test"}},
    )

    await queue.enqueue(job)
    # Should not raise -- errors are handled internally
    result = await queue.process_next()
    assert result is not None
    assert result.retry_count >= 0


# ---------------------------------------------------------------------------
# Test 6: map_intake_to_cms_contact
# ---------------------------------------------------------------------------

def test_map_intake_to_cms_contact():
    from app.integrations.cms.field_mapping import map_intake_to_cms_contact

    intake = {"id": 1, "description": "Test intake"}
    party = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "party_type": "petitioner",
    }

    result = map_intake_to_cms_contact(intake, party)

    assert "name" in result
    assert "email" in result
    assert "phone" in result
    assert "type" in result
    assert result["email"] == "jane@example.com"
    assert result["phone"] == "555-1234"


# ---------------------------------------------------------------------------
# Test 7: map_intake_to_cms_matter
# ---------------------------------------------------------------------------

def test_map_intake_to_cms_matter():
    from app.integrations.cms.field_mapping import map_intake_to_cms_matter

    intake = {"id": 1, "description": "Custody dispute"}
    analysis_run = {
        "id": 10,
        "practice_area": "family_law",
        "status": "complete",
        "client_id": "c123",
    }

    result = map_intake_to_cms_matter(intake, analysis_run)

    assert "description" in result
    assert "status" in result
    assert "practice_area" in result
    assert "client_id" in result


# ---------------------------------------------------------------------------
# Test 8: map_output_to_cms_document
# ---------------------------------------------------------------------------

def test_map_output_to_cms_document():
    from app.integrations.cms.field_mapping import map_output_to_cms_document

    output_doc = {
        "id": 5,
        "profile_type": "case_memo",
        "markdown_content": "# Case Memo\nDetails...",
    }

    result = map_output_to_cms_document(output_doc, "pdf")

    assert "name" in result
    assert "content_type" in result
    assert "description" in result


# ---------------------------------------------------------------------------
# Test 9: CMSSyncRecord model fields
# ---------------------------------------------------------------------------

def test_cms_sync_record_model_fields():
    from app.models.cms import CMSSyncRecord

    # Check table name
    assert CMSSyncRecord.__tablename__ == "cms_sync_records"

    # Check columns exist
    columns = {c.name for c in CMSSyncRecord.__table__.columns}
    expected = {
        "id", "alea_entity_type", "alea_entity_id", "cms_entity_id",
        "cms_type", "sync_status", "sync_direction", "error_message",
        "last_synced_at", "created_at", "updated_at",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"


# ---------------------------------------------------------------------------
# Test 10: CMSConnectorConfig model fields
# ---------------------------------------------------------------------------

def test_cms_connector_config_model_fields():
    from app.models.cms import CMSConnectorConfig

    # Check table name
    assert CMSConnectorConfig.__tablename__ == "cms_connector_configs"

    # Check columns exist
    columns = {c.name for c in CMSConnectorConfig.__table__.columns}
    expected = {
        "id", "org_id", "cms_type", "credentials_encrypted",
        "sync_scope_json", "is_active", "created_at", "updated_at",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
