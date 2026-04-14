"""
Test script for codesearch-plugin without API key.

This script demonstrates the parser, chunker, and storage components
without requiring an embedding API key.
"""

import asyncio
import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codesearch.builder.parser import CParser, NodeType
from codesearch.builder.chunker import CodeChunker, ChunkStrategy
from codesearch.builder.storage import VectorStore


def test_parser():
    """Test the C parser."""
    print("=" * 60)
    print("Testing C Parser")
    print("=" * 60)

    # Read sample C code
    sample_file = "examples/sample_c_code/demo.c"
    if not os.path.exists(sample_file):
        print(f"Sample file not found: {sample_file}")
        return None

    with open(sample_file, "r") as f:
        source_code = f.read()

    parser = CParser()
    tree = parser.parse_string(source_code)
    source = source_code.encode("utf-8")

    nodes = parser.extract_nodes(tree, source, sample_file)

    print(f"\nParsed {sample_file}:")
    print(f"  Found {len(nodes)} AST nodes")

    # Count by type
    type_counts = {}
    for node in nodes:
        type_name = node.node_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    print("\n  Nodes by type:")
    for type_name, count in sorted(type_counts.items()):
        print(f"    - {type_name}: {count}")

    # Show some examples
    print("\n  Sample nodes:")
    for node in nodes[:5]:
        print(f"    - [{node.node_type.value}] {node.name}")
        print(f"      Lines {node.start_line}-{node.end_line}")

    return nodes


def test_chunker(nodes):
    """Test the code chunker."""
    print("\n" + "=" * 60)
    print("Testing Code Chunker")
    print("=" * 60)

    if not nodes:
        print("  No nodes to chunk")
        return []

    chunker = CodeChunker(strategy=ChunkStrategy.HYBRID)
    chunks = chunker.chunk(nodes, "demo.c")

    print(f"\n  Created {len(chunks)} chunks")

    print("\n  Chunks by type:")
    type_counts = {}
    for chunk in chunks:
        type_counts[chunk.chunk_type] = type_counts.get(chunk.chunk_type, 0) + 1

    for type_name, count in sorted(type_counts.items()):
        print(f"    - {type_name}: {count}")

    print("\n  Sample chunks:")
    for chunk in chunks[:3]:
        print(f"    - [{chunk.chunk_type}] {chunk.name}")
        print(f"      Lines {chunk.start_line}-{chunk.end_line}")
        print(f"      Content preview: {chunk.content[:80]}...")

    return chunks


def test_vector_store(chunks):
    """Test the vector store with mock embeddings."""
    print("\n" + "=" * 60)
    print("Testing Vector Store")
    print("=" * 60)

    if not chunks:
        print("  No chunks to store")
        return

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(
            collection_name="test_collection",
            persist_directory=tmpdir,
        )

        # Create mock embeddings (random vectors for testing)
        import random
        ids = [chunk.id for chunk in chunks]
        embeddings = [[random.random() for _ in range(1536)] for _ in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.embedding_metadata() for chunk in chunks]

        print(f"\n  Adding {len(chunks)} documents to vector store...")
        store.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        print(f"  Vector store count: {store.count()}")

        # Test search with mock query embedding
        print("\n  Testing search...")
        query_embedding = [random.random() for _ in range(1536)]
        results = store.search(query_embedding, n_results=3)

        print(f"  Search returned {len(results)} results")
        for i, result in enumerate(results, 1):
            print(f"    {i}. {result.metadata.get('name', 'Unknown')} (score: {result.score:.4f})")

        print("\n  Vector store test completed successfully!")


def test_hooks():
    """Test the hook trigger system."""
    print("\n" + "=" * 60)
    print("Testing Hook Triggers")
    print("=" * 60)

    from codesearch.hooks.triggers import HookTrigger

    trigger = HookTrigger(threshold=0.5)

    test_queries = [
        "find all memory allocation functions",
        "search for struct definitions",
        "where is malloc_wrapper defined?",
        "show me references to Point",
        "explain how this code works",
        "what is the weather today",  # Should NOT trigger
    ]

    print("\n  Testing trigger responses:")
    for query in test_queries:
        result = trigger.should_trigger(query)
        status = "TRIGGERED" if result.triggered else "not triggered"
        print(f"    '{query[:50]}...'")
        print(f"      -> {status} (confidence: {result.confidence:.2f})")


def main():
    """Main test function."""
    print("\ncodesearch-plugin - Component Test")
    print("=" * 60)

    # Test parser
    nodes = test_parser()

    # Test chunker
    chunks = test_chunker(nodes)

    # Test vector store
    test_vector_store(chunks)

    # Test hooks
    test_hooks()

    print("\n" + "=" * 60)
    print("All component tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
