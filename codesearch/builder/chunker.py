"""
Code chunking strategies for semantic indexing.

This module provides strategies for breaking code into meaningful chunks
for embedding and indexing.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from codesearch.builder.parser import ASTNode, NodeType


class ChunkStrategy(Enum):
    """Strategies for chunking code."""

    BY_FUNCTION = "function"  # Chunk by function definitions
    BY_CLASS = "class"  # Chunk by class/struct definitions
    BY_BLOCK = "block"  # Chunk by top-level blocks
    BY_FILE = "file"  # Entire file as one chunk
    HYBRID = "hybrid"  # Combine multiple strategies


@dataclass
class CodeChunk:
    """A chunk of code with metadata for indexing."""

    id: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    name: str
    parent_name: Optional[str] = None
    language: str = "c"
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "name": self.name,
            "parent_name": self.parent_name,
            "language": self.language,
            "metadata": self.metadata,
        }

    def embedding_metadata(self) -> dict:
        """Get metadata for embedding indexing."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "chunk_type": self.chunk_type,
            "name": self.name,
            "parent_name": self.parent_name,
            "language": self.language,
            **self.metadata,
        }


class CodeChunker:
    """Chunks code based on AST nodes."""

    def __init__(self, strategy: ChunkStrategy = ChunkStrategy.HYBRID):
        """Initialize the chunker with a strategy."""
        self.strategy = strategy

    def chunk(self, nodes: list[ASTNode], file_path: str = "") -> list[CodeChunk]:
        """Chunk code based on the configured strategy."""
        if self.strategy == ChunkStrategy.BY_FUNCTION:
            return self._chunk_by_type(nodes, NodeType.FUNCTION, file_path)
        elif self.strategy == ChunkStrategy.BY_CLASS:
            return self._chunk_by_types(
                nodes, [NodeType.STRUCT, NodeType.UNION, NodeType.ENUM], file_path
            )
        elif self.strategy == ChunkStrategy.BY_BLOCK:
            return self._chunk_by_block(nodes, file_path)
        elif self.strategy == ChunkStrategy.BY_FILE:
            return self._chunk_by_file(nodes, file_path)
        elif self.strategy == ChunkStrategy.HYBRID:
            return self._chunk_hybrid(nodes, file_path)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _chunk_by_type(
        self,
        nodes: list[ASTNode],
        node_type: NodeType,
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk by a specific node type."""
        chunks = []
        seen_ids: set[str] = set()
        for i, node in enumerate(nodes):
            if node.node_type == node_type:
                # Generate unique ID including node type and index
                base_id = f"{file_path}:{node.node_type.value}:{node.name}:{node.start_line}"
                chunk_id = self.generate_chunk_id(base_id)

                # Ensure uniqueness
                if chunk_id in seen_ids:
                    chunk_id = f"{chunk_id}_{i}"
                seen_ids.add(chunk_id)

                chunk = CodeChunk(
                    id=chunk_id,
                    content=node.code,
                    file_path=file_path,
                    start_line=node.start_line,
                    end_line=node.end_line,
                    chunk_type=node.node_type.value,
                    name=node.name,
                    metadata={"docstring": node.docstring},
                )
                chunks.append(chunk)
        return chunks

    def _chunk_by_types(
        self,
        nodes: list[ASTNode],
        node_types: list[NodeType],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk by multiple node types."""
        chunks = []
        seen_ids: set[str] = set()
        for i, node in enumerate(nodes):
            if node.node_type in node_types:
                # Generate unique ID including node type and index
                base_id = f"{file_path}:{node.node_type.value}:{node.name}:{node.start_line}"
                chunk_id = self.generate_chunk_id(base_id)

                # Ensure uniqueness
                if chunk_id in seen_ids:
                    chunk_id = f"{chunk_id}_{i}"
                seen_ids.add(chunk_id)

                chunk = CodeChunk(
                    id=chunk_id,
                    content=node.code,
                    file_path=file_path,
                    start_line=node.start_line,
                    end_line=node.end_line,
                    chunk_type=node.node_type.value,
                    name=node.name,
                    metadata={"docstring": node.docstring},
                )
                chunks.append(chunk)
        return chunks

    def _chunk_by_block(
        self, nodes: list[ASTNode], file_path: str
    ) -> list[CodeChunk]:
        """Chunk by top-level blocks (functions, structs, etc.)."""
        chunks = []
        seen_ids: set[str] = set()
        block_types = {
            NodeType.FUNCTION,
            NodeType.STRUCT,
            NodeType.UNION,
            NodeType.ENUM,
            NodeType.TYPEDEF,
        }

        for i, node in enumerate(nodes):
            if node.node_type in block_types:
                # Generate unique ID including node type and index
                base_id = f"{file_path}:{node.node_type.value}:{node.name}:{node.start_line}"
                chunk_id = self.generate_chunk_id(base_id)

                # Ensure uniqueness
                if chunk_id in seen_ids:
                    chunk_id = f"{chunk_id}_{i}"
                seen_ids.add(chunk_id)

                chunk = CodeChunk(
                    id=chunk_id,
                    content=node.code,
                    file_path=file_path,
                    start_line=node.start_line,
                    end_line=node.end_line,
                    chunk_type=node.node_type.value,
                    name=node.name,
                    metadata={"docstring": node.docstring},
                )
                chunks.append(chunk)

        # If no blocks found, create a single chunk for the file
        if not chunks and nodes:
            full_content = "\n".join(n.code for n in nodes)
            chunks.append(
                CodeChunk(
                    id=f"{file_path}:full",
                    content=full_content,
                    file_path=file_path,
                    start_line=min(n.start_line for n in nodes),
                    end_line=max(n.end_line for n in nodes),
                    chunk_type="file",
                    name=file_path.split("/")[-1] if file_path else "unknown",
                )
            )

        return chunks

    def _chunk_by_file(
        self, nodes: list[ASTNode], file_path: str
    ) -> list[CodeChunk]:
        """Create a single chunk for the entire file."""
        if not nodes:
            return []

        full_content = "\n".join(n.code for n in nodes)
        return [
            CodeChunk(
                id=f"{file_path}:full",
                content=full_content,
                file_path=file_path,
                start_line=min(n.start_line for n in nodes),
                end_line=max(n.end_line for n in nodes),
                chunk_type="file",
                name=file_path.split("/")[-1] if file_path else "unknown",
            )
        ]

    def _chunk_hybrid(
        self, nodes: list[ASTNode], file_path: str
    ) -> list[CodeChunk]:
        """Hybrid chunking: prioritize functions and types, include macros."""
        chunks = []

        # First, chunk by functions
        function_chunks = self._chunk_by_type(nodes, NodeType.FUNCTION, file_path)
        chunks.extend(function_chunks)

        # Then, chunk by classes/structs
        type_chunks = self._chunk_by_types(
            nodes, [NodeType.STRUCT, NodeType.UNION, NodeType.ENUM], file_path
        )
        chunks.extend(type_chunks)

        # Add typedefs
        typedef_chunks = self._chunk_by_type(nodes, NodeType.TYPEDEF, file_path)
        chunks.extend(typedef_chunks)

        # If no meaningful chunks, fall back to file-level
        if not chunks and nodes:
            chunks = self._chunk_by_file(nodes, file_path)

        return chunks

    @staticmethod
    def generate_chunk_id(content: str) -> str:
        """Generate a unique chunk ID from content string."""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()[:16]
