"""
Basic usage example for codesearch-plugin.

This example demonstrates how to:
1. Build an index for a C codebase
2. Perform semantic search
3. Find symbols
4. Find references
"""

import asyncio
import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codesearch import CodeIndexer
from codesearch.builder.indexer import IndexConfig
from codesearch.builder.chunker import ChunkStrategy
from codesearch.builder.embeddings import EmbeddingProvider


async def main():
    """Main example function."""
    # Get configuration from environment or use defaults
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    codebase_path = sys.argv[1] if len(sys.argv) > 1 else "./examples/sample_c_code"
    index_path = os.getenv("CODESEARCH_INDEX_PATH", "./.codesearch_index")

    print("=" * 60)
    print("codesearch-plugin - Basic Usage Example")
    print("=" * 60)

    # Configure the indexer
    config = IndexConfig(
        persist_directory=index_path,
        chunk_strategy=ChunkStrategy.HYBRID,
        embedding_provider=EmbeddingProvider.OPENAI,
        embedding_api_key=api_key,
        include_patterns=["*.c", "*.h"],
        exclude_patterns=["**/test/**", "**/tests/**", "**/vendor/**"],
    )

    # Create indexer
    indexer = CodeIndexer(config=config)

    print(f"\n1. Building index for: {codebase_path}")
    print(f"   Index path: {index_path}")
    print()

    # Build index
    stats = await indexer.build_index(codebase_path)

    print(f"   Files processed: {stats.files_processed}")
    print(f"   Chunks created: {stats.chunks_created}")
    print(f"   Chunks indexed: {stats.chunks_indexed}")

    if stats.errors:
        print(f"   Errors: {len(stats.errors)}")
        for error in stats.errors:
            print(f"     - {error}")

    print()

    # Example: Semantic search
    print("2. Semantic Search Example:")
    print("   Query: 'memory allocation functions'")
    print()

    search_results = await indexer.search(
        query="memory allocation functions",
        n_results=3,
    )

    for i, result in enumerate(search_results, 1):
        metadata = result.get("metadata", {})
        print(f"   {i}. {metadata.get('name', 'Unknown')}")
        print(f"      File: {metadata.get('file_path', 'Unknown')}")
        print(f"      Type: {metadata.get('chunk_type', 'Unknown')}")
        print()

    # Example: Find symbol
    print("3. Find Symbol Example:")
    print("   Looking for: 'malloc_wrapper'")
    print()

    symbol_results = await indexer.find_symbol(
        symbol_name="malloc_wrapper",
        symbol_type="function",
    )

    for i, result in enumerate(symbol_results, 1):
        metadata = result.get("metadata", {})
        print(f"   {i}. {metadata.get('name', 'Unknown')}")
        print(f"      File: {metadata.get('file_path', 'Unknown')}")
        print()

    # Example: Find references
    print("4. Find References Example:")
    print("   Looking for references to: 'malloc'")
    print()

    ref_results = await indexer.find_references(
        symbol_name="malloc",
    )

    for i, result in enumerate(ref_results[:3], 1):  # Show first 3
        print(f"   {i}. Found in chunk: {result.get('id', 'Unknown')}")
        print(f"      Score: {result.get('score', 0):.4f}")
        print()

    # Get final stats
    final_stats = indexer.get_stats()
    print("5. Final Statistics:")
    print(f"   Total chunks in index: {final_stats['total_chunks']}")
    print(f"   Indexed files: {final_stats['indexed_files']}")
    print()

    print("=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
