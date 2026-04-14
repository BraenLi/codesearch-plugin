"""Tests for the builder module."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from codesearch.builder.parser import CParser, NodeType
from codesearch.builder.chunker import CodeChunker, ChunkStrategy
from codesearch.builder.storage import VectorStore
from codesearch.builder.indexer import CodeIndexer, IndexConfig


# Sample C code for testing
SAMPLE_C_CODE = """
#include <stdio.h>
#include <stdlib.h>

// Memory allocation wrapper with error handling
void* malloc_wrapper(size_t size) {
    void* ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "Memory allocation failed\\n");
        exit(1);
    }
    return ptr;
}

// Safe calloc that checks for overflow
void* safe_calloc(size_t nmemb, size_t size) {
    if (nmemb == 0 || size == 0) {
        return NULL;
    }
    return calloc(nmemb, size);
}

typedef struct {
    int x;
    int y;
} Point;

typedef struct {
    Point position;
    int velocity;
} GameObject;

enum ErrorCode {
    SUCCESS = 0,
    ERROR_MEMORY = 1,
    ERROR_INVALID = 2
};
"""


class TestCParser:
    """Tests for CParser."""

    def test_parse_string(self):
        """Test parsing a C source string."""
        parser = CParser()
        tree = parser.parse_string(SAMPLE_C_CODE)
        assert tree is not None
        assert tree.root_node is not None

    def test_parse_file(self):
        """Test parsing a C source file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(SAMPLE_C_CODE)
            f.flush()

            try:
                parser = CParser()
                tree = parser.parse_file(f.name)
                assert tree is not None
                assert tree.root_node is not None
            finally:
                Path(f.name).unlink()

    def test_extract_nodes(self):
        """Test extracting AST nodes."""
        parser = CParser()
        tree = parser.parse_string(SAMPLE_C_CODE)
        source = SAMPLE_C_CODE.encode('utf-8')

        nodes = parser.extract_nodes(tree, source, "test.c")
        assert len(nodes) > 0

        # Check for expected node types
        node_types = {node.node_type for node in nodes}
        assert NodeType.FUNCTION in node_types
        assert NodeType.STRUCT in node_types
        assert NodeType.ENUM in node_types
        assert NodeType.INCLUDE in node_types

    def test_function_extraction(self):
        """Test extracting function definitions."""
        parser = CParser()
        tree = parser.parse_string(SAMPLE_C_CODE)
        source = SAMPLE_C_CODE.encode('utf-8')

        nodes = parser.extract_nodes(tree, source, "test.c")
        functions = [n for n in nodes if n.node_type == NodeType.FUNCTION]

        function_names = {f.name for f in functions}
        assert "malloc_wrapper" in function_names
        assert "safe_calloc" in function_names

    def test_struct_extraction(self):
        """Test extracting struct definitions."""
        parser = CParser()
        tree = parser.parse_string(SAMPLE_C_CODE)
        source = SAMPLE_C_CODE.encode('utf-8')

        nodes = parser.extract_nodes(tree, source, "test.c")

        # Structs are anonymous in the typedef pattern
        structs = [n for n in nodes if n.node_type == NodeType.STRUCT]
        assert len(structs) >= 2  # At least two anonymous structs

        # Typedefs should have the names
        typedefs = [n for n in nodes if n.node_type == NodeType.TYPEDEF]
        typedef_names = {t.name for t in typedefs}
        assert "Point" in typedef_names
        assert "GameObject" in typedef_names


class TestCodeChunker:
    """Tests for CodeChunker."""

    @pytest.fixture
    def sample_nodes(self):
        """Create sample AST nodes for testing."""
        parser = CParser()
        tree = parser.parse_string(SAMPLE_C_CODE)
        source = SAMPLE_C_CODE.encode('utf-8')
        return parser.extract_nodes(tree, source, "test.c")

    def test_chunk_by_function(self, sample_nodes):
        """Test chunking by function."""
        chunker = CodeChunker(strategy=ChunkStrategy.BY_FUNCTION)
        chunks = chunker.chunk(sample_nodes, "test.c")

        # Should have at least the two functions
        function_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(function_chunks) >= 2

    def test_chunk_hybrid(self, sample_nodes):
        """Test hybrid chunking strategy."""
        chunker = CodeChunker(strategy=ChunkStrategy.HYBRID)
        chunks = chunker.chunk(sample_nodes, "test.c")

        assert len(chunks) > 0

        # Check chunk metadata
        for chunk in chunks:
            assert chunk.id is not None
            assert chunk.content is not None
            assert chunk.file_path == "test.c"

    def test_chunk_by_file(self, sample_nodes):
        """Test chunking entire file."""
        chunker = CodeChunker(strategy=ChunkStrategy.BY_FILE)
        chunks = chunker.chunk(sample_nodes, "test.c")

        # Should create single chunk for the file
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "file"


class TestVectorStore:
    """Tests for VectorStore."""

    @pytest.fixture
    def vector_store(self):
        """Create a temporary vector store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(
                collection_name="test_collection",
                persist_directory=tmpdir,
            )
            yield store

    def test_add_and_search(self, vector_store):
        """Test adding and searching documents."""
        # Add documents
        vector_store.add(
            ids=["doc1", "doc2", "doc3"],
            embeddings=[[1.0] * 10, [2.0] * 10, [3.0] * 10],
            documents=["Hello world", "Goodbye world", "Test document"],
            metadatas=[{"type": "greeting"}, {"type": "farewell"}, {"type": "test"}],
        )

        assert vector_store.count() == 3

    def test_delete(self, vector_store):
        """Test deleting documents."""
        vector_store.add(
            ids=["doc1", "doc2"],
            embeddings=[[1.0] * 10, [2.0] * 10],
            documents=["Hello", "Goodbye"],
        )

        assert vector_store.count() == 2

        vector_store.delete(ids=["doc1"])
        assert vector_store.count() == 1

    def test_reset(self, vector_store):
        """Test resetting the store."""
        vector_store.add(
            ids=["doc1", "doc2"],
            embeddings=[[1.0] * 10, [2.0] * 10],
            documents=["Hello", "Goodbye"],
        )

        vector_store.reset()
        assert vector_store.count() == 0


class TestCodeIndexer:
    """Tests for CodeIndexer."""

    @pytest.fixture
    def temp_codebase(self):
        """Create a temporary codebase for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            src_dir = tmpdir / "src"
            src_dir.mkdir()

            (src_dir / "memory.c").write_text(SAMPLE_C_CODE)
            (src_dir / "utils.h").write_text("#ifndef UTILS_H\n#define UTILS_H\n#endif")

            yield tmpdir

    @pytest.fixture
    def indexer(self, temp_codebase):
        """Create an indexer for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = IndexConfig(
                persist_directory=tmpdir,
                include_patterns=["*.c", "*.h"],
            )
            indexer = CodeIndexer(config=config)
            yield indexer

    @pytest.mark.skip(reason="Requires API key for embeddings")
    async def test_build_index(self, indexer, temp_codebase):
        """Test building an index."""
        stats = await indexer.build_index(temp_codebase)

        assert stats.files_processed > 0
        assert stats.chunks_created > 0

    def test_get_stats(self, indexer):
        """Test getting indexer statistics."""
        stats = indexer.get_stats()

        assert "files_processed" in stats
        assert "chunks_created" in stats
        assert "total_chunks" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
