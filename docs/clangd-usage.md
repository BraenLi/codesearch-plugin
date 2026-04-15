# Clangd Usage Guide

## Overview

The codesearch-plugin now supports clangd as an alternative (and recommended)
parser backend for C/C++ code. Clangd provides more accurate parsing with full
semantic understanding including:

- Symbol resolution across translation units
- Preprocessor expansion
- Type information
- Reference finding

## Installation

Install clangd:

```bash
# Ubuntu/Debian
apt install clangd

# macOS
# Apple clangd is pre-installed, or install LLVM:
brew install llvm

# Windows
# Install LLVM from https://releases.llvm.org/
```

Verify installation:

```bash
clangd --version
```

## Usage

### Using ClangdParser Directly

```python
import asyncio
from codesearch.builder.clangd_parser import ClangdParser

async def main():
    parser = ClangdParser()
    await parser.start()

    # Parse a file
    nodes = await parser.parse_file("src/example.c")

    for node in nodes:
        print(f"{node.node_type.value}: {node.name}")

    # Find references
    refs = await parser.find_references("function_name")

    await parser.stop()

asyncio.run(main())
```

### Using with CodeIndexer

```python
import asyncio
from codesearch import CodeIndexer
from codesearch.builder import IndexConfig

async def main():
    config = IndexConfig(
        persist_directory="./.codesearch_index",
        use_clangd=True,  # Enable clangd
        clangd_path="clangd",  # Optional: custom path
        embedding_api_key="your-openai-api-key",
    )

    indexer = CodeIndexer(config=config)
    stats = await indexer.build_index("/path/to/codebase")

    print(f"Indexed {stats.files_processed} files with clangd")

asyncio.run(main())
```

## Configuration

### IndexConfig Options for Clangd

| Option | Default | Description |
|--------|---------|-------------|
| `use_clangd` | `False` | Enable clangd parser |
| `clangd_path` | `None` | Path to clangd executable |

### Example: Custom clangd Path

```python
config = IndexConfig(
    use_clangd=True,
    clangd_path="/usr/local/opt/llvm/bin/clangd",  # Homebrew LLVM
)
```

## Benefits of Clangd

1. **Accurate Symbol Resolution**: Resolves symbols across translation units
2. **Preprocessor Support**: Handles `#include`, `#define`, and macros correctly
3. **Type Information**: Provides full type information for symbols
4. **Reference Finding**: Accurately finds all references to a symbol
5. **Error Recovery**: Continues parsing even with syntax errors
6. **C++ Support**: Full support for C++ templates and modern features

## Comparison: tree-sitter vs clangd

| Feature | tree-sitter | clangd |
|---------|-------------|--------|
| Speed | Fast | Moderate |
| Accuracy | Good | Excellent |
| Semantic Understanding | Limited | Full |
| Cross-file References | No | Yes |
| Preprocessor | No | Yes |
| C++ Support | Limited | Full |
| Setup Required | pip install | System package |

## Fallback to tree-sitter

If clangd is not available or fails, the parser automatically falls back to tree-sitter.

To explicitly use tree-sitter, set `use_clangd=False` in IndexConfig:

```python
config = IndexConfig(
    use_clangd=False,  # Force tree-sitter
)
```

## Troubleshooting

### clangd not found

```
RuntimeError: clangd not found. Please install clangd
```

**Solution**: Install clangd using your package manager (see Installation section).

### clangd initialization timeout

This may happen with large codebases. The indexer will retry with a shorter timeout.

**Solution**: Ensure the codebase path is correct and accessible.

### Missing compilation database

For best results with C++ projects, create a `compile_commands.json`:

```bash
# For CMake projects
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON .
```

## API Reference

### ClangdParser

```python
from codesearch.builder.clangd_parser import ClangdParser

parser = ClangdParser(clangd_path="clangd")

# Start the clangd server
await parser.start()

# Parse a file
nodes = await parser.parse_file("file.c")

# Find symbol references
refs = await parser.find_references("symbol_name")

# Find symbol definition
defn = await parser.find_definition("symbol_name")

# Stop the clangd server
await parser.stop()
```
