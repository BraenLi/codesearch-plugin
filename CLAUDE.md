# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=codesearch

# Run a single test
pytest tests/test_builder.py -v

# Format code
black codesearch tests

# Lint code
ruff check codesearch tests
```

## Architecture Overview

This is a Python semantic code search toolkit for AI coding agents. It uses tree-sitter for AST parsing and ChromaDB for vector embeddings.

### Package Structure

- `codesearch/` - Main package
  - `builder/` - Core indexing pipeline
    - `parser.py` - CParser using tree-sitter-c for AST extraction
    - `chunker.py` - CodeChunker with strategies (HYBRID, BY_FUNCTION, BY_CLASS, BY_BLOCK, BY_FILE)
    - `embeddings.py` - EmbeddingGenerator supporting OpenAI, Anthropic, and custom providers
    - `storage.py` - VectorStore wrapper around ChromaDB
    - `indexer.py` - CodeIndexer orchestrating the full pipeline
  - `mcp/` - MCP server implementation
    - `server.py` - MCP server exposing 4 tools: semantic_search, find_symbol, find_references, get_file_context
    - `tools.py` - Tool definitions with Pydantic schemas
  - `hooks/` - Subagent trigger system with confidence scoring
  - `subagent/` - Subagent configuration

### Key Classes

- `CodeIndexer` - Main entry point for building indices and searching
- `CParser` - tree-sitter-based C parser extracting AST nodes
- `CodeChunker` - Chunks code by function, struct, enum, or hybrid strategies
- `VectorStore` - ChromaDB-backed vector storage
- `HookTrigger` - Pattern/intent-based triggers for activating codesearch subagent

### Data Flow

```
Source files -> CParser (tree-sitter) -> ASTNodes -> CodeChunker -> CodeChunk
-> EmbeddingGenerator -> VectorStore (ChromaDB) -> Search Results
```

### MCP Tools

The MCP server exposes 4 tools to AI agents:
1. `semantic_search` - Search code by meaning
2. `find_symbol` - Find symbol definition by name
3. `find_references` - Find all references to a symbol
4. `get_file_context` - Get file/line context

### Configuration

Key configuration in `IndexConfig`:
- `persist_directory` - Index storage path
- `chunk_strategy` - HYBRID (default), BY_FUNCTION, BY_CLASS, BY_BLOCK, BY_FILE
- `embedding_provider` - OPENAI (default), ANTHROPIC, CUSTOM
- `include_patterns` - ["*.c", "*.h"] by default
- `exclude_patterns` - ["**/test/**", "**/tests/**", "**/vendor/**"]
