"""
codesearch-plugin: Semantic code search toolkit for AI coding agents.

This package provides AST-level indexing and vector search capabilities
for semantic code understanding across large codebases.
"""

__version__ = "0.1.0"
__author__ = "codesearch-plugin"

from codesearch.builder.indexer import CodeIndexer
from codesearch.mcp.server import create_mcp_server

__all__ = ["CodeIndexer", "create_mcp_server"]
