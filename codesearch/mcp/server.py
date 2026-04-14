"""
MCP server implementation.

This module implements the MCP server that exposes code search tools
to AI coding agents.
"""

import asyncio
import json
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
)

from codesearch.builder.indexer import CodeIndexer, IndexConfig
from codesearch.mcp.tools import MCPTools


def create_mcp_server(indexer: Optional[CodeIndexer] = None) -> Server:
    """
    Create an MCP server with code search tools.

    Args:
        indexer: Optional pre-configured indexer. If not provided,
                 a default indexer will be created.

    Returns:
        Configured MCP server instance
    """
    server = Server("codesearch")

    # Create or use provided indexer
    _indexer = indexer or CodeIndexer()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        tools_def = MCPTools.all_tools()
        return [
            Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in tools_def
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[TextContent]:
        """
        Call a tool with the given arguments.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result as text content
        """
        try:
            if name == "semantic_search":
                result = await _handle_semantic_search(arguments, _indexer)
            elif name == "find_symbol":
                result = await _handle_find_symbol(arguments, _indexer)
            elif name == "find_references":
                result = await _handle_find_references(arguments, _indexer)
            elif name == "get_file_context":
                result = await _handle_get_file_context(arguments, _indexer)
            else:
                result = {"error": f"Unknown tool: {name}"}

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    return server


async def _handle_semantic_search(
    arguments: dict, indexer: CodeIndexer
) -> dict:
    """Handle semantic search tool."""
    query = arguments.get("query")
    if not query:
        return {"error": "Missing required argument: query"}

    n_results = arguments.get("n_results", 5)

    # Build filters
    filters = {}
    if arguments.get("file_filter"):
        filters["file_path"] = arguments["file_filter"]
    if arguments.get("chunk_type"):
        filters["chunk_type"] = arguments["chunk_type"]

    results = await indexer.search(
        query=query,
        n_results=n_results,
        filters=filters if filters else None,
    )

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


async def _handle_find_symbol(
    arguments: dict, indexer: CodeIndexer
) -> dict:
    """Handle find_symbol tool."""
    name = arguments.get("name")
    if not name:
        return {"error": "Missing required argument: name"}

    symbol_type = arguments.get("symbol_type")

    results = await indexer.find_symbol(
        symbol_name=name,
        symbol_type=symbol_type,
    )

    return {
        "symbol_name": name,
        "symbol_type": symbol_type,
        "results": results,
        "count": len(results),
    }


async def _handle_find_references(
    arguments: dict, indexer: CodeIndexer
) -> dict:
    """Handle find_references tool."""
    symbol_name = arguments.get("symbol_name")
    if not symbol_name:
        return {"error": "Missing required argument: symbol_name"}

    results = await indexer.find_references(symbol_name=symbol_name)

    return {
        "symbol_name": symbol_name,
        "results": results,
        "count": len(results),
    }


async def _handle_get_file_context(
    arguments: dict, indexer: CodeIndexer
) -> dict:
    """Handle get_file_context tool."""
    file_path = arguments.get("file_path")
    if not file_path:
        return {"error": "Missing required argument: file_path"}

    line_number = arguments.get("line_number")

    result = await indexer.get_file_context(
        file_path=file_path,
        line_number=line_number,
    )

    return result


async def run_server(indexer: Optional[CodeIndexer] = None):
    """
    Run the MCP server using stdio transport.

    Args:
        indexer: Optional pre-configured indexer
    """
    server = create_mcp_server(indexer)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Main entry point for the MCP server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
