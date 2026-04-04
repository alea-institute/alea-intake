"""Tests for FolioMCPClient singleton wrapping folio-mcp via MCP SDK.

All tests mock the mcp SDK (StdioServerParameters, ClientSession, stdio_client)
since folio-mcp subprocess is not available in the test environment.
Tests verify correct tool names and argument shapes are passed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp.folio_mcp_client import FolioMCPClient


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset FolioMCPClient singleton between tests."""
    FolioMCPClient.reset_instance()
    yield
    FolioMCPClient.reset_instance()


def _make_mock_session() -> AsyncMock:
    """Create a mock ClientSession that returns structured content."""
    session = AsyncMock()
    # Default call_tool returns a result with content
    result_mock = MagicMock()
    result_mock.content = [{"text": '{"name": "negligence", "iri": "http://example.org/negligence"}'}]
    session.call_tool = AsyncMock(return_value=result_mock)
    session.initialize = AsyncMock()
    return session


def _make_mock_stdio_client(mock_session: AsyncMock):
    """Create a mock stdio_client context manager that yields (read, write) streams."""
    mock_read = AsyncMock()
    mock_write = AsyncMock()

    # stdio_client returns an async context manager yielding (read, write)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    cm.__aexit__ = AsyncMock(return_value=False)

    return cm, mock_read, mock_write


class TestFolioMCPClientInit:
    """Test 1: FolioMCPClient.__init__ accepts mode param."""

    def test_default_mode_is_api(self):
        client = FolioMCPClient(mode="api")
        assert client._mode == "api"

    def test_local_mode(self):
        client = FolioMCPClient(mode="local")
        assert client._mode == "local"

    def test_session_initially_none(self):
        client = FolioMCPClient()
        assert client._session is None


class TestFolioMCPClientConnect:
    """Test 2 & 3: connect() creates correct StdioServerParameters."""

    @patch("app.services.mcp.folio_mcp_client.ClientSession")
    @patch("app.services.mcp.folio_mcp_client.stdio_client")
    @patch("app.services.mcp.folio_mcp_client.StdioServerParameters")
    async def test_connect_api_mode(self, mock_params_cls, mock_stdio, mock_cs_cls):
        mock_session = _make_mock_session()
        mock_stdio_cm, mock_read, mock_write = _make_mock_stdio_client(mock_session)
        mock_stdio.return_value = mock_stdio_cm

        mock_cs_cm = AsyncMock()
        mock_cs_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cs_cm.__aexit__ = AsyncMock(return_value=False)
        mock_cs_cls.return_value = mock_cs_cm

        client = FolioMCPClient(mode="api")
        await client.connect()

        mock_params_cls.assert_called_once_with(
            command="uvx",
            args=["folio-mcp"],
        )
        mock_session.initialize.assert_awaited_once()

    @patch("app.services.mcp.folio_mcp_client.ClientSession")
    @patch("app.services.mcp.folio_mcp_client.stdio_client")
    @patch("app.services.mcp.folio_mcp_client.StdioServerParameters")
    async def test_connect_local_mode_adds_local_arg(self, mock_params_cls, mock_stdio, mock_cs_cls):
        mock_session = _make_mock_session()
        mock_stdio_cm, mock_read, mock_write = _make_mock_stdio_client(mock_session)
        mock_stdio.return_value = mock_stdio_cm

        mock_cs_cm = AsyncMock()
        mock_cs_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cs_cm.__aexit__ = AsyncMock(return_value=False)
        mock_cs_cls.return_value = mock_cs_cm

        client = FolioMCPClient(mode="local")
        await client.connect()

        mock_params_cls.assert_called_once_with(
            command="uvx",
            args=["folio-mcp", "--local"],
        )


class TestFolioMCPClientToolCalls:
    """Tests 4-10: Tool wrapper methods call session.call_tool with correct args."""

    async def _connected_client(self) -> tuple[FolioMCPClient, AsyncMock]:
        """Create a FolioMCPClient with a mocked connected session."""
        client = FolioMCPClient(mode="api")
        mock_session = _make_mock_session()
        client._session = mock_session
        return client, mock_session

    async def test_search_concepts(self):
        client, session = await self._connected_client()
        result = await client.search_concepts("negligence", limit=5)
        session.call_tool.assert_awaited_once_with(
            "search_concepts", {"query": "negligence", "limit": 5}
        )
        assert isinstance(result, list)

    async def test_get_concept(self):
        client, session = await self._connected_client()
        result = await client.get_concept("http://example.org/negligence")
        session.call_tool.assert_awaited_once_with(
            "get_concept", {"iri": "http://example.org/negligence"}
        )

    async def test_get_taxonomy_branch(self):
        client, session = await self._connected_client()
        result = await client.get_taxonomy_branch("Objectives", max_depth=3)
        session.call_tool.assert_awaited_once_with(
            "get_taxonomy_branch", {"branch_name": "Objectives", "max_depth": 3}
        )

    async def test_get_children(self):
        client, session = await self._connected_client()
        result = await client.get_children("http://example.org/concept", max_depth=2)
        session.call_tool.assert_awaited_once_with(
            "get_children", {"iri": "http://example.org/concept", "max_depth": 2}
        )

    async def test_get_parents(self):
        client, session = await self._connected_client()
        result = await client.get_parents("http://example.org/concept", max_depth=2)
        session.call_tool.assert_awaited_once_with(
            "get_parents", {"iri": "http://example.org/concept", "max_depth": 2}
        )

    async def test_list_branches(self):
        client, session = await self._connected_client()
        result = await client.list_branches()
        session.call_tool.assert_awaited_once_with("list_branches", {})

    async def test_find_connections(self):
        client, session = await self._connected_client()
        result = await client.find_connections(
            subject="http://example.org/a",
            property="http://example.org/prop",
            obj="http://example.org/b",
        )
        session.call_tool.assert_awaited_once_with(
            "find_connections",
            {
                "subject": "http://example.org/a",
                "property": "http://example.org/prop",
                "object": "http://example.org/b",
            },
        )

    async def test_search_definitions(self):
        client, session = await self._connected_client()
        result = await client.search_definitions("intentional harm", limit=5)
        session.call_tool.assert_awaited_once_with(
            "search_definitions", {"query": "intentional harm", "limit": 5}
        )

    async def test_query_concepts(self):
        client, session = await self._connected_client()
        result = await client.query_concepts(text="negligence", limit=5)
        session.call_tool.assert_awaited_once_with(
            "query_concepts", {"text": "negligence", "limit": 5}
        )

    async def test_query_properties(self):
        client, session = await self._connected_client()
        result = await client.query_properties(label="relates_to")
        session.call_tool.assert_awaited_once_with(
            "query_properties", {"label": "relates_to"}
        )

    async def test_export_concept(self):
        client, session = await self._connected_client()
        result = await client.export_concept("http://example.org/c", format="markdown")
        session.call_tool.assert_awaited_once_with(
            "export_concept", {"iri": "http://example.org/c", "format": "markdown"}
        )

    async def test_get_properties(self):
        client, session = await self._connected_client()
        result = await client.get_properties()
        session.call_tool.assert_awaited_once_with("get_properties", {})


class TestFolioMCPClientCleanup:
    """Test 11: close() properly cleans up session and subprocess resources."""

    async def test_close_cleans_up(self):
        client = FolioMCPClient(mode="api")
        mock_session = _make_mock_session()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

        client._session = mock_session
        client._session_cm = mock_session_cm
        client._stdio_cm = mock_stdio_cm

        await client.close()

        mock_session_cm.__aexit__.assert_awaited_once()
        mock_stdio_cm.__aexit__.assert_awaited_once()
        assert client._session is None

    async def test_close_when_not_connected_is_noop(self):
        client = FolioMCPClient(mode="api")
        # Should not raise
        await client.close()


class TestFolioMCPClientContextManager:
    """Test 12: FolioMCPClient is usable as async context manager."""

    @patch("app.services.mcp.folio_mcp_client.ClientSession")
    @patch("app.services.mcp.folio_mcp_client.stdio_client")
    @patch("app.services.mcp.folio_mcp_client.StdioServerParameters")
    async def test_async_context_manager(self, mock_params_cls, mock_stdio, mock_cs_cls):
        mock_session = _make_mock_session()
        mock_stdio_cm, mock_read, mock_write = _make_mock_stdio_client(mock_session)
        mock_stdio.return_value = mock_stdio_cm

        mock_cs_cm = AsyncMock()
        mock_cs_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cs_cm.__aexit__ = AsyncMock(return_value=False)
        mock_cs_cls.return_value = mock_cs_cm

        async with FolioMCPClient(mode="api") as client:
            assert client._session is not None
            result = await client.search_concepts("test")

        # After exit, session should be cleaned up
        assert client._session is None


class TestFolioMCPClientSingleton:
    """Test singleton pattern: get_instance / reset_instance."""

    def test_get_instance_returns_same_object(self):
        a = FolioMCPClient.get_instance()
        b = FolioMCPClient.get_instance()
        assert a is b

    def test_reset_instance_clears_singleton(self):
        a = FolioMCPClient.get_instance()
        FolioMCPClient.reset_instance()
        b = FolioMCPClient.get_instance()
        assert a is not b
