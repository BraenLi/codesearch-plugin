"""Builder module for code indexing."""

from codesearch.builder.parser import CParser, ASTNode, NodeType
from codesearch.builder.clangd_parser import ClangdParser, SymbolInfo
from codesearch.builder.chunker import CodeChunker, CodeChunk, ChunkStrategy
from codesearch.builder.embeddings import EmbeddingGenerator, EmbeddingProvider
from codesearch.builder.storage import VectorStore
from codesearch.builder.indexer import CodeIndexer, IndexConfig
from codesearch.builder.lsp_client import LSPClient

__all__ = [
    # Parser
    "CParser",
    "ClangdParser",
    "ASTNode",
    "NodeType",
    "SymbolInfo",
    # Chunker
    "CodeChunker",
    "ChunkStrategy",
    "CodeChunk",
    # Embeddings
    "EmbeddingGenerator",
    "EmbeddingProvider",
    # Storage
    "VectorStore",
    # Indexer
    "CodeIndexer",
    "IndexConfig",
    # LSP
    "LSPClient",
]
