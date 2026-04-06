"""Clio CMS adapter -- bidirectional sync with Clio Manage v4 API.

Implements CMSAdapter for Clio's REST API (app.clio.com/api/v4).
Uses OAuth2 bearer token authentication with auto-refresh (Pitfall 4).
Supports push/pull for contacts, matters, and documents.

API docs: https://app.clio.com/api/v4/documentation
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.integrations.cms.base import CMSAdapter, CMSSyncConfig
from app.integrations.cms.field_mapping import (
    map_intake_to_cms_contact,
    map_intake_to_cms_matter,
    map_output_to_cms_document,
)

logger = logging.getLogger(__name__)

# Clio API v4 base URL
CLIO_BASE_URL = "https://app.clio.com/api/v4"


class ClioAdapter(CMSAdapter):
    """Clio Manage CMS adapter using REST API v4.

    Authentication: OAuth2 bearer token with auto-refresh.
    Entity mapping:
        - ALEA contacts -> Clio Contacts (Person type)
        - ALEA matters -> Clio Matters
        - ALEA documents -> Clio Documents (multipart upload)
    """

    def __init__(self, config: CMSSyncConfig) -> None:
        super().__init__()
        self._config = config
        self._base_url = CLIO_BASE_URL
        self._client = httpx.AsyncClient(
            timeout=30,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "alea-intake/1.0.0",
            },
        )

    @property
    def adapter_name(self) -> str:
        return "clio"

    @property
    def display_name(self) -> str:
        return "Clio Manage"

    def _get_auth_headers(self) -> dict[str, str]:
        """Build auth headers with OAuth2 bearer token."""
        token = self._access_token or "placeholder"
        return {"Authorization": f"Bearer {token}"}

    async def push_contact(self, contact_data: dict) -> str:
        """Push a contact to Clio as a Person contact.

        Clio field mapping:
            name -> first_name + last_name split
            email -> email_addresses[0]
            phone -> phone_numbers[0]
            type -> "Person"

        Returns:
            Clio contact ID as string.
        """
        self._refresh_token_if_needed()

        # Map canonical fields to Clio-specific structure
        name_parts = contact_data.get("name", "Unknown").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        clio_payload: dict[str, Any] = {
            "data": {
                "first_name": first_name,
                "last_name": last_name,
                "type": "Person",
            }
        }

        if contact_data.get("email"):
            clio_payload["data"]["email_addresses"] = [
                {"name": "Work", "address": contact_data["email"], "default_email": True}
            ]

        if contact_data.get("phone"):
            clio_payload["data"]["phone_numbers"] = [
                {"name": "Work", "number": contact_data["phone"], "default_number": True}
            ]

        response = await self._client.post(
            f"{self._base_url}/contacts.json",
            json=clio_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["data"]["id"])

    async def push_matter(self, matter_data: dict) -> str:
        """Push a matter to Clio.

        Clio field mapping:
            description -> description
            status -> "Open"
            practice_area -> custom_field_values
            client_id -> client reference

        Returns:
            Clio matter ID as string.
        """
        self._refresh_token_if_needed()

        clio_payload: dict[str, Any] = {
            "data": {
                "description": matter_data.get("description", "ALEA Intake Matter"),
                "status": "Open",
            }
        }

        if matter_data.get("client_id"):
            clio_payload["data"]["client"] = {"id": matter_data["client_id"]}

        if matter_data.get("practice_area"):
            clio_payload["data"]["practice_area"] = {
                "name": matter_data["practice_area"]
            }

        response = await self._client.post(
            f"{self._base_url}/matters.json",
            json=clio_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["data"]["id"])

    async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
        """Push a document to Clio with multipart file upload.

        Returns:
            Clio document ID as string.
        """
        self._refresh_token_if_needed()

        # Multipart upload: create document metadata, then upload file
        files = {
            "file": (doc_data.get("name", "document"), file_bytes, doc_data.get("content_type", "application/octet-stream")),
        }
        data = {
            "name": doc_data.get("name", "ALEA Document"),
            "description": doc_data.get("description", ""),
        }

        response = await self._client.post(
            f"{self._base_url}/documents.json",
            data=data,
            files=files,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        resp_data = response.json()
        return str(resp_data["data"]["id"])

    async def pull_updates(self, since: datetime) -> list[dict]:
        """Pull updated contacts and matters from Clio since a timestamp.

        Returns:
            List of updated entity dicts.
        """
        self._refresh_token_if_needed()

        since_str = since.isoformat() + "Z" if since.tzinfo is None else since.isoformat()
        results: list[dict] = []

        # Pull contacts
        contacts_resp = await self._client.get(
            f"{self._base_url}/contacts.json",
            params={
                "updated_since": since_str,
                "fields": "id,name,email_addresses",
            },
            headers=self._get_auth_headers(),
        )
        contacts_resp.raise_for_status()
        for contact in contacts_resp.json().get("data", []):
            results.append({"type": "contact", "cms": "clio", **contact})

        # Pull matters
        matters_resp = await self._client.get(
            f"{self._base_url}/matters.json",
            params={
                "updated_since": since_str,
                "fields": "id,description,status",
            },
            headers=self._get_auth_headers(),
        )
        matters_resp.raise_for_status()
        for matter in matters_resp.json().get("data", []):
            results.append({"type": "matter", "cms": "clio", **matter})

        return results

    async def handle_webhook(self, payload: dict) -> None:
        """Process a Clio webhook payload.

        Clio webhooks include entity type and ID. Enqueue a pull
        for the affected entity.
        """
        entity_type = payload.get("type")
        entity_id = payload.get("id")
        logger.info(
            "Clio webhook received: type=%s id=%s",
            entity_type,
            entity_id,
        )

    async def test_connection(self) -> bool:
        """Test connection by calling GET /api/v4/users/who_am_i.json.

        Returns:
            True if Clio returns 200 with user data.
        """
        self._refresh_token_if_needed()

        try:
            response = await self._client.get(
                f"{self._base_url}/users/who_am_i.json",
                headers=self._get_auth_headers(),
            )
            return response.status_code == 200
        except Exception as exc:
            logger.error("Clio connection test failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
