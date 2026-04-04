"""FolioMCPClient -- singleton MCP client wrapping folio-mcp subprocess.

Connects to folio-mcp as a long-running subprocess via the mcp SDK,
exposing all 12 FOLIO ontology tools for LLM agent tool-use during analysis.

Usage:
    # As singleton (for lifespan management)
    client = FolioMCPClient.get_instance(mode="api")
    await client.connect()
    results = await client.search_concepts("negligence", limit=5)
    await client.close()

    # As async context manager
    async with FolioMCPClient(mode="api") as client:
        results = await client.search_concepts("negligence", limit=5)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class FolioMCPClient:
    """Singleton MCP client for folio-mcp server.

    Wraps all 12 folio-mcp tools via the mcp SDK. Designed to be started
    once at application lifespan and shared across requests.
    """

    _instance: FolioMCPClient | None = None
    _lock = threading.Lock()

    def __init__(self, mode: str = "api") -> None:
        """Initialize the client.

        Args:
            mode: "api" (default, calls public FOLIO API) or "local" (local OWL file).
        """
        self._mode = mode
        self._session: ClientSession | None = None
        self._session_cm: Any = None  # ClientSession context manager
        self._stdio_cm: Any = None  # stdio_client context manager
        self._read: Any = None
        self._write: Any = None

    # -- Singleton pattern (matches EmbeddingService) --

    @classmethod
    def get_instance(cls, mode: str = "api") -> FolioMCPClient:
        """Return the singleton instance, creating it on first call.

        Uses double-checked locking for thread safety.
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            cls._instance = cls(mode=mode)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    # -- Connection lifecycle --

    async def connect(self) -> None:
        """Start folio-mcp as subprocess and connect via stdio.

        Creates StdioServerParameters and uses the mcp SDK to manage
        the subprocess lifecycle.
        """
        args = ["folio-mcp"]
        if self._mode == "local":
            args.append("--local")

        server_params = StdioServerParameters(
            command="uvx",
            args=args,
        )

        # Start the subprocess via stdio_client
        self._stdio_cm = stdio_client(server_params)
        self._read, self._write = await self._stdio_cm.__aenter__()

        # Create and initialize the session
        self._session_cm = ClientSession(self._read, self._write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

        logger.info("FolioMCPClient connected (mode=%s)", self._mode)

    async def close(self) -> None:
        """Close session and subprocess, releasing all resources."""
        if self._session is None and self._session_cm is None and self._stdio_cm is None:
            return

        try:
            if self._session_cm is not None:
                await self._session_cm.__aexit__(None, None, None)
        except Exception:
            logger.warning("Error closing MCP session", exc_info=True)
        finally:
            self._session = None
            self._session_cm = None

        try:
            if self._stdio_cm is not None:
                await self._stdio_cm.__aexit__(None, None, None)
        except Exception:
            logger.warning("Error closing stdio transport", exc_info=True)
        finally:
            self._stdio_cm = None
            self._read = None
            self._write = None

        logger.info("FolioMCPClient closed")

    # -- Async context manager --

    async def __aenter__(self) -> FolioMCPClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # -- Tool wrappers (all 12 folio-mcp tools) --

    def _parse_content(self, result: Any) -> list[dict] | dict:
        """Extract content from an MCP tool call result."""
        return result.content

    async def search_concepts(self, query: str, limit: int = 10) -> list[dict]:
        """Search concepts by fuzzy name match."""
        result = await self._session.call_tool(
            "search_concepts", {"query": query, "limit": limit}
        )
        return self._parse_content(result)

    async def search_definitions(self, query: str, limit: int = 10) -> list[dict]:
        """Search concepts by definition content."""
        result = await self._session.call_tool(
            "search_definitions", {"query": query, "limit": limit}
        )
        return self._parse_content(result)

    async def query_concepts(self, text: str | None = None, limit: int = 10, **kwargs) -> list[dict]:
        """Advanced multi-filter concept query."""
        params: dict[str, Any] = {"text": text, "limit": limit}
        params.update(kwargs)
        result = await self._session.call_tool("query_concepts", params)
        return self._parse_content(result)

    async def query_properties(self, label: str | None = None, domain: str | None = None, range_: str | None = None) -> list[dict]:
        """Search OWL object properties."""
        params: dict[str, Any] = {}
        if label is not None:
            params["label"] = label
        if domain is not None:
            params["domain"] = domain
        if range_ is not None:
            params["range"] = range_
        result = await self._session.call_tool("query_properties", params)
        return self._parse_content(result)

    async def get_concept(self, iri: str) -> dict | list[dict]:
        """Get full concept details by IRI."""
        result = await self._session.call_tool("get_concept", {"iri": iri})
        return self._parse_content(result)

    async def export_concept(self, iri: str, format: str = "markdown") -> dict | list[dict]:
        """Export concept as markdown/JSON-LD/OWL."""
        result = await self._session.call_tool(
            "export_concept", {"iri": iri, "format": format}
        )
        return self._parse_content(result)

    async def list_branches(self) -> list[dict]:
        """List all 24 taxonomy branches."""
        result = await self._session.call_tool("list_branches", {})
        return self._parse_content(result)

    async def get_taxonomy_branch(self, branch_name: str, max_depth: int = 3) -> dict | list[dict]:
        """Extract branch concepts up to max_depth."""
        result = await self._session.call_tool(
            "get_taxonomy_branch", {"branch_name": branch_name, "max_depth": max_depth}
        )
        return self._parse_content(result)

    async def get_children(self, iri: str, max_depth: int = 1) -> list[dict]:
        """Get subordinate concepts."""
        result = await self._session.call_tool(
            "get_children", {"iri": iri, "max_depth": max_depth}
        )
        return self._parse_content(result)

    async def get_parents(self, iri: str, max_depth: int = 1) -> list[dict]:
        """Get parent concepts."""
        result = await self._session.call_tool(
            "get_parents", {"iri": iri, "max_depth": max_depth}
        )
        return self._parse_content(result)

    async def get_properties(self) -> list[dict]:
        """List all OWL object properties."""
        result = await self._session.call_tool("get_properties", {})
        return self._parse_content(result)

    async def find_connections(
        self, subject: str | None = None, property: str | None = None, obj: str | None = None
    ) -> list[dict]:
        """Semantic triple lookup."""
        params: dict[str, Any] = {}
        if subject is not None:
            params["subject"] = subject
        if property is not None:
            params["property"] = property
        if obj is not None:
            params["object"] = obj
        result = await self._session.call_tool("find_connections", params)
        return self._parse_content(result)
