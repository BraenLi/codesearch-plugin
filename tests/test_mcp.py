"""Tests for the MCP server module."""

import json
import pytest

from codesearch.mcp.tools import MCPTools, ToolDefinition
from codesearch.mcp.server import (
    create_mcp_server,
    _handle_semantic_search,
    _handle_find_symbol,
    _handle_find_references,
    _handle_get_file_context,
)


class TestMCPTools:
    """Tests for MCP tool definitions."""

    def test_all_tools(self):
        """Test that all tools are defined."""
        tools = MCPTools.all_tools()

        assert len(tools) == 4

        tool_names = {tool.name for tool in tools}
        assert "semantic_search" in tool_names
        assert "find_symbol" in tool_names
        assert "find_references" in tool_names
        assert "get_file_context" in tool_names

    def test_tool_schema(self):
        """Test tool schema retrieval."""
        schema = MCPTools.get_tool_schema("semantic_search")

        assert schema is not None
        assert "query" in schema["required"]
        assert "properties" in schema

    def test_semantic_search_schema(self):
        """Test semantic_search tool schema."""
        schema = MCPTools.get_tool_schema("semantic_search")

        assert schema["properties"]["query"]["type"] == "string"
        assert schema["properties"]["n_results"]["type"] == "integer"

    def test_find_symbol_schema(self):
        """Test find_symbol tool schema."""
        schema = MCPTools.get_tool_schema("find_symbol")

        assert schema["properties"]["name"]["type"] == "string"
        assert "name" in schema["required"]

    def test_find_references_schema(self):
        """Test find_references tool schema."""
        schema = MCPTools.get_tool_schema("find_references")

        assert schema["properties"]["symbol_name"]["type"] == "string"
        assert "symbol_name" in schema["required"]

    def test_get_file_context_schema(self):
        """Test get_file_context tool schema."""
        schema = MCPTools.get_tool_schema("get_file_context")

        assert schema["properties"]["file_path"]["type"] == "string"
        assert "file_path" in schema["required"]


class TestMCPServer:
    """Tests for MCP server creation."""

    def test_create_server(self):
        """Test creating an MCP server."""
        server = create_mcp_server()

        assert server is not None
        assert server.name == "codesearch"

    def test_server_list_tools(self):
        """Test listing server tools."""
        server = create_mcp_server()

        # The list_tools decorator should be registered
        assert hasattr(server, "list_tools")


class TestToolHandlers:
    """Tests for tool handlers."""

    @pytest.fixture
    def mock_indexer(self, mocker):
        """Create a mock indexer."""
        indexer = mocker.MagicMock()
        indexer.search = mocker.AsyncMock(return_value=[])
        indexer.find_symbol = mocker.AsyncMock(return_value=[])
        indexer.find_references = mocker.AsyncMock(return_value=[])
        indexer.get_file_context = mocker.AsyncMock(return_value={})
        return indexer

    @pytest.mark.asyncio
    async def test_semantic_search_handler(self, mock_indexer):
        """Test semantic search handler."""
        arguments = {
            "query": "memory allocation",
            "n_results": 5,
        }

        result = await _handle_semantic_search(arguments, mock_indexer)

        assert "query" in result
        assert "results" in result
        mock_indexer.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search_missing_query(self, mock_indexer):
        """Test semantic search with missing query."""
        arguments = {}

        result = await _handle_semantic_search(arguments, mock_indexer)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_find_symbol_handler(self, mock_indexer):
        """Test find_symbol handler."""
        arguments = {
            "name": "malloc_wrapper",
            "symbol_type": "function",
        }

        result = await _handle_find_symbol(arguments, mock_indexer)

        assert "symbol_name" in result
        assert "results" in result
        mock_indexer.find_symbol.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_symbol_missing_name(self, mock_indexer):
        """Test find_symbol with missing name."""
        arguments = {}

        result = await _handle_find_symbol(arguments, mock_indexer)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_find_references_handler(self, mock_indexer):
        """Test find_references handler."""
        arguments = {
            "symbol_name": "malloc_wrapper",
        }

        result = await _handle_find_references(arguments, mock_indexer)

        assert "symbol_name" in result
        assert "results" in result
        mock_indexer.find_references.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_context_handler(self, mock_indexer):
        """Test get_file_context handler."""
        arguments = {
            "file_path": "src/memory.c",
            "line_number": 15,
        }

        result = await _handle_get_file_context(arguments, mock_indexer)

        assert isinstance(result, dict)
        mock_indexer.get_file_context.assert_called_once()


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating a tool definition."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.input_schema == {"type": "object"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
