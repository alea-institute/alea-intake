"""Marketplace index for community-contributed skills.

Fetches a JSON index of available skills from a Git-based registry
(GitHub repo with index.json listing skill Markdown files).
Supports offline mode: returns empty list when index is unreachable.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_INDEX_URL = (
    "https://raw.githubusercontent.com/alea/skills-registry/main/index.json"
)


class MarketplaceIndex:
    """Client for the community skills marketplace index.

    Skills are Markdown files hosted in a GitHub repository.
    The index.json file lists available skills with metadata.

    Usage:
        marketplace = MarketplaceIndex()
        skills = await marketplace.fetch_index()
        content = await marketplace.fetch_skill(skills[0]["url"])
    """

    def __init__(self, index_url: str = _DEFAULT_INDEX_URL) -> None:
        self._index_url = index_url

    async def fetch_index(self) -> list[dict[str, Any]]:
        """Fetch the community skills index from the configured URL.

        Returns:
            List of skill metadata dicts with keys: name, description, type, author, url.
            Returns empty list on network error (offline mode).
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._index_url)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    return data
                logger.warning("Marketplace index is not a list: %s", type(data))
                return []
        except Exception as exc:
            logger.warning(
                "Failed to fetch marketplace index (offline mode): %s", exc
            )
            return []

    async def fetch_skill(self, url: str) -> str:
        """Fetch a skill's Markdown content from the given URL.

        Args:
            url: Direct URL to the skill Markdown file.

        Returns:
            Markdown content string, or empty string on error.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as exc:
            logger.warning("Failed to fetch skill from %s: %s", url, exc)
            return ""
