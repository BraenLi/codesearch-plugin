"""
MCP tool definitions for code search.

This module defines the tools available via the MCP protocol.
"""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    """Request for semantic search."""

    query: str = Field(..., description="The search query")
    n_results: int = Field(default=5, description="Number of results to return")
    file_filter: Optional[str] = Field(
        default=None, description="Filter by file path pattern"
    )
    chunk_type: Optional[str] = Field(
        default=None, description="Filter by chunk type (function, struct, etc.)"
    )


class FindSymbolRequest(BaseModel):
    """Request to find a symbol."""

    name: str = Field(..., description="Name of the symbol to find")
    symbol_type: Optional[str] = Field(
        default=None, description="Type of symbol (function, struct, etc.)"
    )


class FindReferencesRequest(BaseModel):
    """Request to find references to a symbol."""

    symbol_name: str = Field(..., description="Name of the symbol")


class GetFileContextRequest(BaseModel):
    """Request to get file context."""

    file_path: str = Field(..., description="Path to the file")
    line_number: Optional[int] = Field(
        default=None, description="Specific line number for context"
    )


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str
    input_schema: dict


class MCPTools:
    """MCP tool definitions."""

    SEMANTIC_SEARCH = ToolDefinition(
        name="semantic_search",
        description="Search for code semantically by meaning rather than keywords. "
        "Finds code chunks that match the intent of the query.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query describing what code to find",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
                "file_filter": {
                    "type": "string",
                    "description": "Optional file path pattern to filter results",
                },
                "chunk_type": {
                    "type": "string",
                    "description": "Optional chunk type filter (function, struct, enum, etc.)",
                },
            },
            "required": ["query"],
        },
    )

    FIND_SYMBOL = ToolDefinition(
        name="find_symbol",
        description="Find a symbol (function, struct, enum, etc.) by name. "
        "Returns the definition of the symbol.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the symbol to find",
                },
                "symbol_type": {
                    "type": "string",
                    "description": "Optional type filter (function, struct, union, enum, typedef)",
                },
            },
            "required": ["name"],
        },
    )

    FIND_REFERENCES = ToolDefinition(
        name="find_references",
        description="Find references to a symbol across the codebase. "
        "Returns code chunks that mention the symbol.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the symbol to find references for",
                },
            },
            "required": ["symbol_name"],
        },
    )

    GET_FILE_CONTEXT = ToolDefinition(
        name="get_file_context",
        description="Get context for a specific file or line. "
        "Returns the code structure and surrounding context.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file",
                },
                "line_number": {
                    "type": "integer",
                    "description": "Optional line number to get specific context",
                },
            },
            "required": ["file_path"],
        },
    )

    @classmethod
    def all_tools(cls) -> list[ToolDefinition]:
        """Get all tool definitions."""
        return [
            cls.SEMANTIC_SEARCH,
            cls.FIND_SYMBOL,
            cls.FIND_REFERENCES,
            cls.GET_FILE_CONTEXT,
        ]

    @classmethod
    def get_tool_schema(cls, tool_name: str) -> Optional[dict]:
        """Get the schema for a specific tool."""
        tools = cls.all_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool.input_schema
        return None
