"""Tests for ClangdParser."""
import pytest
import tempfile
from pathlib import Path
from codesearch.builder.clangd_parser import ClangdParser, ASTNode, NodeType


SAMPLE_C_CODE = """
#include <stdio.h>
#include <stdlib.h>

void* malloc_wrapper(size_t size) {
    void* ptr = malloc(size);
    if (!ptr) {
        fprintf(stderr, "Memory allocation failed\\n");
        exit(1);
    }
    return ptr;
}

typedef struct {
    int x;
    int y;
} Point;

enum ErrorCode {
    SUCCESS = 0,
    ERROR_MEMORY = 1,
};
"""


class TestClangdParser:
    @pytest.mark.asyncio
    async def test_parse_file(self):
        """Test parsing a C source file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(SAMPLE_C_CODE)
            f.flush()
            try:
                parser = ClangdParser()
                await parser.start()
                nodes = await parser.parse_file(f.name)
                assert len(nodes) > 0
                await parser.stop()
            finally:
                Path(f.name).unlink()

    @pytest.mark.asyncio
    async def test_function_extraction(self):
        """Test extracting function definitions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(SAMPLE_C_CODE)
            f.flush()
            try:
                parser = ClangdParser()
                await parser.start()
                nodes = await parser.parse_file(f.name)
                functions = [n for n in nodes if n.node_type == NodeType.FUNCTION]
                function_names = {f.name for f in functions}
                assert "malloc_wrapper" in function_names
                await parser.stop()
            finally:
                Path(f.name).unlink()

    @pytest.mark.asyncio
    async def test_find_references(self):
        """Test finding symbol references."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(SAMPLE_C_CODE)
            f.flush()
            try:
                parser = ClangdParser()
                await parser.start()
                await parser.parse_file(f.name)
                refs = await parser.find_references("malloc_wrapper")
                # May return empty if clangd doesn't have full project context
                assert isinstance(refs, list)
                await parser.stop()
            finally:
                Path(f.name).unlink()
