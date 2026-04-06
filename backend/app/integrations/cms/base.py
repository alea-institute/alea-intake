"""CMS adapter abstract base class and shared data types.

Defines the pluggable contract for CMS sync connectors.
Each adapter implements push/pull/webhook operations against
a specific CMS (Clio, MyCase, LegalServer).

Mirrors the ResearchAdapter pattern from Phase 6.
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SyncDirection(str, Enum):
    """Direction of data synchronization."""

    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class CMSSyncConfig:
    """Configuration for a CMS connector instance.

    Attributes:
        cms_type: CMS identifier (clio, mycase, legalserver).
        credentials_encrypted: Encrypted OAuth2/API-key credentials.
        sync_scope: Entity types to sync (contacts, matters, documents).
        direction: Sync direction for this connector.
        webhook_url: Optional URL for CMS webhook callbacks.
    """

    cms_type: str
    credentials_encrypted: bytes
    sync_scope: list[str]
    direction: SyncDirection
    webhook_url: str | None = None


class CMSAdapter(abc.ABC):
    """Abstract base class for CMS sync connectors.

    Each concrete adapter wraps a specific CMS API (Clio, MyCase,
    LegalServer) and implements a uniform interface for pushing
    contacts/matters/documents, pulling updates, and processing webhooks.

    Adapters are instantiated per-org with their encrypted credentials.
    """

    def __init__(self) -> None:
        self._token_expires_at: float = 0.0
        self._access_token: str | None = None

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Unique identifier for this CMS adapter (e.g., 'clio')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for this adapter."""
        return self.adapter_name.replace("_", " ").title()

    @abc.abstractmethod
    async def push_contact(self, contact_data: dict) -> str:
        """Push a contact to the CMS.

        Args:
            contact_data: Canonical contact dict from field_mapping.

        Returns:
            CMS-side entity ID for the created/updated contact.
        """
        ...

    @abc.abstractmethod
    async def push_matter(self, matter_data: dict) -> str:
        """Push a matter/case to the CMS.

        Args:
            matter_data: Canonical matter dict from field_mapping.

        Returns:
            CMS-side entity ID for the created/updated matter.
        """
        ...

    @abc.abstractmethod
    async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
        """Push a document to the CMS.

        Args:
            doc_data: Canonical document dict from field_mapping.
            file_bytes: Raw file content bytes.

        Returns:
            CMS-side entity ID for the uploaded document.
        """
        ...

    @abc.abstractmethod
    async def pull_updates(self, since: datetime) -> list[dict]:
        """Pull updated entities from the CMS since a given timestamp.

        Args:
            since: Only return entities updated after this datetime.

        Returns:
            List of entity dicts with CMS-specific fields.
        """
        ...

    @abc.abstractmethod
    async def handle_webhook(self, payload: dict) -> None:
        """Process an incoming webhook payload from the CMS.

        Args:
            payload: Raw webhook payload dict.
        """
        ...

    @abc.abstractmethod
    async def test_connection(self) -> bool:
        """Test the CMS API connection using current credentials.

        Returns:
            True if the connection is healthy, False otherwise.
        """
        ...

    def _refresh_token_if_needed(self) -> None:
        """Check token expiry and refresh via authlib if within 60s of expiry.

        Concrete OAuth2 adapters override this to call their refresh endpoint.
        API-key adapters can leave this as a no-op.

        Pitfall 4: OAuth token auto-refresh prevents mid-sync expiration.
        """
        if self._access_token and self._token_expires_at > 0:
            if time.time() >= (self._token_expires_at - 60):
                logger.info(
                    "Token near expiry for %s, refresh needed",
                    self.adapter_name,
                )
                # Concrete adapters implement actual refresh logic
