"""MyCase CMS adapter -- sync with MyCase API v1.

Implements CMSAdapter for MyCase's REST API.
Uses OAuth2 bearer token or API key authentication.
Supports push/pull for clients (contacts) and cases (matters).

Note: MyCase uses "clients" and "cases" terminology instead of
"contacts" and "matters".

API docs: https://developer.mycase.com/
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.integrations.cms.base import CMSAdapter, CMSSyncConfig

logger = logging.getLogger(__name__)

# MyCase API v1 base URL
MYCASE_BASE_URL = "https://api.mycase.com/v1"


class MyCaseAdapter(CMSAdapter):
    """MyCase CMS adapter using REST API v1.

    Authentication: OAuth2 bearer token or API key header.
    Entity mapping:
        - ALEA contacts -> MyCase Clients
        - ALEA matters -> MyCase Cases
        - ALEA documents -> MyCase Documents
    """

    def __init__(self, config: CMSSyncConfig) -> None:
        super().__init__()
        self._config = config
        self._base_url = MYCASE_BASE_URL
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
        return "mycase"

    @property
    def display_name(self) -> str:
        return "MyCase"

    def _get_auth_headers(self) -> dict[str, str]:
        """Build auth headers -- OAuth2 bearer or API key."""
        token = self._access_token or "placeholder"
        return {"Authorization": f"Bearer {token}"}

    async def push_contact(self, contact_data: dict) -> str:
        """Push a contact to MyCase as a Client.

        MyCase field mapping:
            name -> first_name + last_name
            email -> email
            phone -> phone

        Returns:
            MyCase client ID as string.
        """
        self._refresh_token_if_needed()

        name_parts = contact_data.get("name", "Unknown").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        mycase_payload: dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
            "email": contact_data.get("email", ""),
            "phone": contact_data.get("phone", ""),
        }

        response = await self._client.post(
            f"{self._base_url}/clients",
            json=mycase_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def push_matter(self, matter_data: dict) -> str:
        """Push a matter to MyCase as a Case.

        MyCase field mapping:
            description -> name (MyCase uses 'name' for cases)
            status -> status
            practice_area -> practice_area

        Returns:
            MyCase case ID as string.
        """
        self._refresh_token_if_needed()

        mycase_payload: dict[str, Any] = {
            "name": matter_data.get("description", "ALEA Intake Case"),
            "status": matter_data.get("status", "open"),
            "practice_area": matter_data.get("practice_area", ""),
        }

        if matter_data.get("client_id"):
            mycase_payload["client_id"] = matter_data["client_id"]

        response = await self._client.post(
            f"{self._base_url}/cases",
            json=mycase_payload,
            headers=self._get_auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["id"])

    async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
        """Push a document to MyCase.

        Returns:
            MyCase document ID as string.
        """
        self._refresh_token_if_needed()

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
        """Pull updated clients and cases from MyCase since a timestamp.

        Returns:
            List of updated entity dicts.
        """
        self._refresh_token_if_needed()

        since_str = since.isoformat()
        results: list[dict] = []

        # Pull clients
        clients_resp = await self._client.get(
            f"{self._base_url}/clients",
            params={"updated_since": since_str},
            headers=self._get_auth_headers(),
        )
        clients_resp.raise_for_status()
        for client in clients_resp.json().get("data", clients_resp.json() if isinstance(clients_resp.json(), list) else []):
            results.append({"type": "contact", "cms": "mycase", **client})

        # Pull cases
        cases_resp = await self._client.get(
            f"{self._base_url}/cases",
            params={"updated_since": since_str},
            headers=self._get_auth_headers(),
        )
        cases_resp.raise_for_status()
        for case in cases_resp.json().get("data", cases_resp.json() if isinstance(cases_resp.json(), list) else []):
            results.append({"type": "matter", "cms": "mycase", **case})

        return results

    async def handle_webhook(self, payload: dict) -> None:
        """Process a MyCase webhook payload."""
        entity_type = payload.get("type")
        entity_id = payload.get("id")
        logger.info(
            "MyCase webhook received: type=%s id=%s",
            entity_type,
            entity_id,
        )

    async def test_connection(self) -> bool:
        """Test connection by calling GET /v1/users/current.

        Returns:
            True if MyCase returns 200.
        """
        self._refresh_token_if_needed()

        try:
            response = await self._client.get(
                f"{self._base_url}/users/current",
                headers=self._get_auth_headers(),
            )
            return response.status_code == 200
        except Exception as exc:
            logger.error("MyCase connection test failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
