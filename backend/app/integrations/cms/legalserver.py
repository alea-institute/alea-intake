"""LegalServer CMS adapter -- sync with LegalServer Premium APIs.

Implements CMSAdapter for LegalServer's REST API.
Uses API key authentication (not OAuth -- LegalServer uses API keys
for Premium API access).

Each LegalServer instance has a unique subdomain, so base_url is
configurable per organization.

Note: LegalServer doesn't have a standalone "contacts" entity.
Contacts are matter participants. push_contact creates/updates a
participant on a matter.

API docs: https://apidocs.legalserver.org/
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.integrations.cms.base import CMSAdapter, CMSSyncConfig

logger = logging.getLogger(__name__)

# Default LegalServer API base URL (overridden per org)
DEFAULT_BASE_URL = "https://demo.legalserver.org/api/v1"


class LegalServerAdapter(CMSAdapter):
    """LegalServer CMS adapter using Premium REST APIs.

    Authentication: API key in X-API-Key header.
    Entity mapping:
        - ALEA contacts -> LegalServer Matter Participants
        - ALEA matters -> LegalServer Matters
        - ALEA documents -> LegalServer Documents
    """

    def __init__(
        self,
        config: CMSSyncConfig,
        base_url: str | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._base_url = base_url or DEFAULT_BASE_URL
        self._api_key = config.credentials_encrypted.decode("utf-8", errors="replace")
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
        return "legalserver"

    @property
    def display_name(self) -> str:
        return "LegalServer"

    def _get_auth_headers(self) -> dict[str, str]:
        """Build auth headers with API key."""
        return {"X-API-Key": self._api_key}

    async def push_contact(self, contact_data: dict) -> str:
        """Push a contact to LegalServer as a matter participant.

        LegalServer doesn't have standalone contacts. Contacts are
        participants on matters. This creates a participant record.

        Returns:
            LegalServer participant ID as string.
        """
        ls_payload: dict[str, Any] = {
            "name": contact_data.get("name", "Unknown"),
            "email": contact_data.get("email", ""),
            "phone": contact_data.get("phone", ""),
            "participant_type": contact_data.get("type", "person"),
        }

        response = await self._client.post(
            f"{self._base_url}/participants",
            json=ls_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def push_matter(self, matter_data: dict) -> str:
        """Push a matter to LegalServer.

        LegalServer field mapping:
            description -> matter_name
            status -> status
            practice_area -> legal_problem_code

        Returns:
            LegalServer matter ID as string.
        """
        ls_payload: dict[str, Any] = {
            "matter_name": matter_data.get("description", "ALEA Intake Matter"),
            "status": matter_data.get("status", "open"),
            "legal_problem_code": matter_data.get("practice_area", ""),
        }

        if matter_data.get("client_id"):
            ls_payload["client_id"] = matter_data["client_id"]

        response = await self._client.post(
            f"{self._base_url}/matters",
            json=ls_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
        """Push a document to LegalServer.

        Returns:
            LegalServer document ID as string.
        """
        files = {
            "file": (doc_data.get("name", "document"), file_bytes, doc_data.get("content_type", "application/octet-stream")),
        }
        data = {
            "name": doc_data.get("name", "ALEA Document"),
            "description": doc_data.get("description", ""),
        }

        response = await self._client.post(
            f"{self._base_url}/documents",
            data=data,
            files=files,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        resp_data = response.json()
        return str(resp_data["id"])

    async def pull_updates(self, since: datetime) -> list[dict]:
        """Pull updated matters from LegalServer since a timestamp.

        Returns:
            List of updated entity dicts.
        """
        since_str = since.isoformat()
        results: list[dict] = []

        matters_resp = await self._client.get(
            f"{self._base_url}/matters",
            params={"updated_since": since_str},
            headers=self._get_auth_headers(),
        )
        matters_resp.raise_for_status()
        resp_json = matters_resp.json()
        matters_list = resp_json.get("data", resp_json if isinstance(resp_json, list) else [])
        for matter in matters_list:
            results.append({"type": "matter", "cms": "legalserver", **matter})

        return results

    async def handle_webhook(self, payload: dict) -> None:
        """Process a LegalServer webhook payload."""
        entity_type = payload.get("type")
        entity_id = payload.get("id")
        logger.info(
            "LegalServer webhook received: type=%s id=%s",
            entity_type,
            entity_id,
        )

    async def test_connection(self) -> bool:
        """Test connection by calling GET /api/v1/status.

        Returns:
            True if LegalServer returns 200.
        """
        try:
            response = await self._client.get(
                f"{self._base_url}/status",
                headers=self._get_auth_headers(),
            )
            return response.status_code == 200
        except Exception as exc:
            logger.error("LegalServer connection test failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
