# codesearch-plugin

Semantic code search toolkit for AI coding agents (Claude Code, OpenCode, etc.) that enhances their global understanding of large code repositories.

## Features

- **AST-level indexing** using tree-sitter or clangd LSP for accurate code structure understanding
- **Vector database** (ChromaDB) for semantic search capabilities
- **MCP server** for seamless integration with AI coding agents
- **Hook system** for intelligent subagent triggering
- **Language support** starting with C, extensible to other languages
- **Clangd support** for more precise parsing with full semantic understanding

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Coding Agents                        │
│            (Claude Code, OpenCode, etc.)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                             │
│  - Tool: semantic_search(query, filters)                    │
│  - Tool: find_symbol(name)                                  │
│  - Tool: find_references(symbol)                            │
│  - Tool: get_file_context(path)                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Index API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        Index Layer                          │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   AST Index      │  │  Vector Index    │                 │
│  │   (tree-sitter)  │  │  (chromadb)      │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/codesearch-plugin.git
cd codesearch-plugin

# Install dependencies
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- tree-sitter-c (C language parser, optional if using clangd)
- clangd (recommended for better accuracy) - 安装方式:
  - Ubuntu/Debian: `apt install clangd`
  - macOS: 系统自带或使用 `brew install llvm`
  - Windows: 安装 LLVM
- ChromaDB (vector database)
- OpenAI API key (for embeddings)

## Quick Start

### 1. Build an Index

```python
import asyncio
from codesearch import CodeIndexer
from codesearch.builder.indexer import IndexConfig

async def main():
    # Configure the indexer
    config = IndexConfig(
        persist_directory="./.codesearch_index",
        embedding_api_key="your-openai-api-key",  # or set OPENAI_API_KEY env var
    )

    # Create indexer and build index
    indexer = CodeIndexer(config=config)
    stats = await indexer.build_index("/path/to/your/c/codebase")

    print(f"Indexed {stats.files_processed} files")
    print(f"Created {stats.chunks_created} chunks")

asyncio.run(main())
```

### Using Clangd (Recommended)

For more accurate parsing with full semantic understanding:

```python
import asyncio
from codesearch import CodeIndexer
from codesearch.builder.indexer import IndexConfig

async def main():
    config = IndexConfig(
        persist_directory="./.codesearch_index",
        use_clangd=True,  # Enable clangd for better accuracy
        embedding_api_key="your-openai-api-key",
    )

    indexer = CodeIndexer(config=config)
    stats = await indexer.build_index("/path/to/your/c/codebase")

    print(f"Indexed {stats.files_processed} files with clangd")

asyncio.run(main())
```

### 2. Search Code

```python
# Semantic search
results = await indexer.search(
    query="find all memory allocation functions",
    n_results=5,
)

for result in results:
    print(f"File: {result['metadata']['file_path']}")
    print(f"Function: {result['metadata']['name']}")
    print(f"Code: {result['content'][:200]}...")
```

### 3. Run the MCP Server

```bash
# Start the MCP server
export OPENAI_API_KEY="your-api-key"
codesearch-mcp
```

Or with a custom index path:

```bash
python -m codesearch.mcp.server
```

## MCP Tools

The MCP server exposes the following tools:

### semantic_search

Search for code by meaning rather than keywords.

```json
{
  "name": "semantic_search",
  "arguments": {
    "query": "find all functions that allocate memory",
    "n_results": 5,
    "file_filter": "src/memory.c",
    "chunk_type": "function"
  }
}
```

### find_symbol

Find a symbol (function, struct, enum, etc.) by name.

```json
{
  "name": "find_symbol",
  "arguments": {
    "name": "malloc_wrapper",
    "symbol_type": "function"
  }
}
```

### find_references

Find references to a symbol across the codebase.

```json
{
  "name": "find_references",
  "arguments": {
    "symbol_name": "malloc_wrapper"
  }
}
```

### get_file_context

Get context for a specific file or line.

```json
{
  "name": "get_file_context",
  "arguments": {
    "file_path": "src/memory.c",
    "line_number": 15
  }
}
```

## Integration with AI Agents

### Claude Code

Add to your Claude Code configuration:

```json
{
  "mcpServers": {
    "codesearch": {
      "command": "codesearch-mcp",
      "env": {
        "OPENAI_API_KEY": "your-api-key",
        "CODESEARCH_INDEX_PATH": "./.codesearch_index"
      }
    }
  }
}
```

### OpenCode

Configure in your OpenCode settings:

```yaml
mcp:
  codesearch:
    command: codesearch-mcp
    env:
      OPENAI_API_KEY: your-api-key
```

## Configuration

### IndexConfig Options

| Option | Default | Description |
|--------|---------|-------------|
| `persist_directory` | `./.codesearch_index` | Directory to store the index |
| `chunk_strategy` | `ChunkStrategy.HYBRID` | How to chunk code |
| `embedding_provider` | `EmbeddingProvider.OPENAI` | Embedding API provider |
| `embedding_model` | `text-embedding-3-small` | Model for embeddings |
| `embedding_api_key` | `OPENAI_API_KEY` env | API key for embeddings |
| `collection_name` | `code_chunks` | ChromaDB collection name |
| `include_patterns` | `["*.c", "*.h"]` | File patterns to include |
| `exclude_patterns` | `["**/vendor/**"]` | File patterns to exclude |
| `use_clangd` | `False` | Use clangd LSP parser instead of tree-sitter (recommended) |
| `clangd_path` | `None` | Path to clangd executable (default: find in PATH) |

### Chunk Strategies

- `ChunkStrategy.HYBRID` - Combine functions, structs, and typedefs (recommended)
- `ChunkStrategy.BY_FUNCTION` - Chunk by function definitions only
- `ChunkStrategy.BY_CLASS` - Chunk by struct/union/enum definitions
- `ChunkStrategy.BY_BLOCK` - Chunk by all top-level blocks
- `ChunkStrategy.BY_FILE` - Entire file as one chunk

### Embedding Providers

- `EmbeddingProvider.OPENAI` - OpenAI embeddings (recommended)
- `EmbeddingProvider.ANTHROPIC` - Anthropic API
- `EmbeddingProvider.CUSTOM` - Custom embedding endpoint

## Hook System

The hook system automatically triggers the codesearch subagent based on user queries:

```python
from codesearch.hooks.triggers import HookTrigger

trigger = HookTrigger(threshold=0.5)

# Check if a query should trigger codesearch
result = trigger.should_trigger("find all memory allocation functions")

if result.triggered:
    print(f"Triggered with confidence: {result.confidence}")
    print(f"Matched pattern: {result.matched_pattern}")
```

### Default Triggers

The hook system includes pre-configured triggers for:

- Search requests ("search for", "find", "locate")
- Reference requests ("references", "usages", "callers")
- Understanding requests ("explain", "how does", "what does")
- Navigation requests ("go to", "jump to", "open")

### Custom Triggers

```python
def my_custom_trigger(text: str) -> TriggerMatch:
    if "memory" in text.lower() and "leak" in text.lower():
        return TriggerMatch(
            triggered=True,
            confidence=0.9,
            trigger_type=TriggerType.CUSTOM,
        )
    return TriggerMatch(triggered=False, confidence=0.0, trigger_type=TriggerType.CUSTOM)

trigger.add_custom_trigger(my_custom_trigger)
```

## API Reference

### CodeIndexer

```python
from codesearch import CodeIndexer

indexer = CodeIndexer()

# Build index
stats = await indexer.build_index("/path/to/codebase")

# Search
results = await indexer.search("query", n_results=5)

# Find symbol
symbols = await indexer.find_symbol("function_name")

# Find references
refs = await indexer.find_references("symbol_name")

# Get file context
context = await indexer.get_file_context("file.c", line_number=10)

# Get stats
stats = indexer.get_stats()

# Reset index
indexer.reset()
```

### VectorStore

```python
from codesearch.builder.storage import VectorStore

store = VectorStore(
    collection_name="my_collection",
    persist_directory="./index",
)

# Add documents
store.add(
    ids=["doc1", "doc2"],
    embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
    documents=["code content 1", "code content 2"],
    metadatas=[{"name": "func1"}, {"name": "func2"}],
)

# Search
results = store.search(query_embedding=[...], n_results=5)

# Count
count = store.count()

# Reset
store.reset()
```

## Development

### Running Tests

```bash
pytest tests/ -v --cov=codesearch
```

### Code Style

```bash
# Format code
black codesearch tests

# Lint code
ruff check codesearch tests
```

## Examples

See the `examples/` directory for usage examples:

- `basic_usage.py` - Basic indexing and search example
- `mcp_client.py` - MCP client usage example

## Troubleshooting

### Index not building

- Ensure `OPENAI_API_KEY` is set
- Check that the codebase path is correct
- Verify file patterns match your code files

### MCP server not connecting

- Ensure the server is running: `codesearch-mcp`
- Check that the index exists at the configured path
- Verify MCP client configuration

### Search returns no results

- Ensure the index was built successfully
- Check that the query is descriptive enough
- Try adjusting the `n_results` parameter

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request
