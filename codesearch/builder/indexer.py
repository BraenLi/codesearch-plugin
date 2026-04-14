"""
Main indexer orchestrator.

This module ties together parser, chunker, embeddings, and storage
to build a complete code indexing pipeline.
"""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from codesearch.builder.parser import CParser, ASTNode
from codesearch.builder.chunker import CodeChunker, CodeChunk, ChunkStrategy
from codesearch.builder.embeddings import EmbeddingGenerator, EmbeddingProvider
from codesearch.builder.storage import VectorStore


@dataclass
class IndexStats:
    """Statistics about the indexing process."""

    files_processed: int = 0
    chunks_created: int = 0
    chunks_indexed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "chunks_indexed": self.chunks_indexed,
            "errors": self.errors,
        }


@dataclass
class IndexConfig:
    """Configuration for the code indexer."""

    # Index storage path
    persist_directory: str = "./.codesearch_index"

    # Chunking strategy
    chunk_strategy: ChunkStrategy = ChunkStrategy.HYBRID

    # Embedding provider
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    embedding_model: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None

    # Collection name
    collection_name: str = "code_chunks"

    # Batch size for embeddings
    embedding_batch_size: int = 10

    # File patterns to include
    include_patterns: list[str] = field(default_factory=lambda: ["*.c", "*.h"])

    # File patterns to exclude
    exclude_patterns: list[str] = field(
        default_factory=lambda: ["**/test/**", "**/tests/**", "**/vendor/**"]
    )


class CodeIndexer:
    """
    Main indexer for building semantic code search indices.

    Usage:
        indexer = CodeIndexer()
        await indexer.build_index("/path/to/codebase")

        # Search
        results = await indexer.search("find all functions that allocate memory")
    """

    def __init__(self, config: Optional[IndexConfig] = None):
        """
        Initialize the code indexer.

        Args:
            config: Indexer configuration
        """
        self.config = config or IndexConfig()
        self.stats = IndexStats()

        # Initialize components
        self.parser = CParser()
        self.chunker = CodeChunker(strategy=self.config.chunk_strategy)

        self.embedding_generator = EmbeddingGenerator(
            provider=self.config.embedding_provider,
            api_key=self.config.embedding_api_key or os.getenv("OPENAI_API_KEY"),
            model=self.config.embedding_model,
            base_url=self.config.embedding_base_url,
        )

        self.vector_store = VectorStore(
            collection_name=self.config.collection_name,
            persist_directory=self.config.persist_directory,
        )

        # Track indexed files
        self._indexed_files: set[str] = set()

    async def build_index(
        self,
        root_path: str | Path,
        incremental: bool = True,
    ) -> IndexStats:
        """
        Build an index for all code files in the given path.

        Args:
            root_path: Root path of the codebase to index
            incremental: If True, skip already indexed files

        Returns:
            IndexStats with indexing statistics
        """
        root_path = Path(root_path)

        if not root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")

        # Reset stats for new indexing run
        self.stats = IndexStats()

        # Find all C files
        files = self._find_code_files(root_path)

        if not files:
            return self.stats

        # Process each file
        for file_path in files:
            # Skip if already indexed (incremental mode)
            if incremental and str(file_path) in self._indexed_files:
                continue

            try:
                await self._index_file(file_path)
                self._indexed_files.add(str(file_path))
                self.stats.files_processed += 1
            except Exception as e:
                self.stats.errors.append(f"Error indexing {file_path}: {str(e)}")

        self.stats.chunks_indexed = self.vector_store.count()

        return self.stats

    def _find_code_files(self, root_path: Path) -> list[Path]:
        """Find all code files matching the include/exclude patterns."""
        files = []

        for pattern in self.config.include_patterns:
            # Handle glob patterns
            if "**" in pattern:
                matched = list(root_path.glob(pattern[2:]))  # Remove **/
            else:
                matched = list(root_path.glob(f"**/{pattern}"))

            for file_path in matched:
                if file_path.is_file() and self._should_include(file_path, root_path):
                    files.append(file_path)

        return files

    def _should_include(self, file_path: Path, root_path: Path) -> bool:
        """Check if a file should be included based on exclude patterns."""
        rel_path = str(file_path.relative_to(root_path))

        for pattern in self.config.exclude_patterns:
            # Simple pattern matching
            if pattern.startswith("**/"):
                if pattern[3:] in rel_path:
                    return False
            elif pattern in rel_path:
                return False

        return True

    async def _index_file(self, file_path: Path) -> None:
        """Index a single file."""
        # Parse the file
        tree = self.parser.parse_file(file_path)

        with open(file_path, "rb") as f:
            source = f.read()

        # Extract AST nodes
        nodes = self.parser.extract_nodes(tree, source, str(file_path))

        if not nodes:
            return

        # Chunk the code
        chunks = self.chunker.chunk(nodes, str(file_path))
        self.stats.chunks_created += len(chunks)

        # Generate embeddings and add to store
        await self._index_chunks(chunks)

    async def _index_chunks(self, chunks: list[CodeChunk]) -> None:
        """Generate embeddings and index chunks."""
        if not chunks:
            return

        # Generate embeddings in batches
        all_embeddings = []
        for i in range(0, len(chunks), self.config.embedding_batch_size):
            batch = chunks[i : i + self.config.embedding_batch_size]
            texts = [chunk.content for chunk in batch]

            results = await self.embedding_generator.generate_batch(
                texts, batch_size=self.config.embedding_batch_size
            )

            for result in results:
                all_embeddings.append(result.embedding)

        # Add to vector store
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.embedding_metadata() for chunk in chunks]

        self.vector_store.add(
            ids=ids,
            embeddings=all_embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def search(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for code matching the query.

        Args:
            query: The search query
            n_results: Number of results to return
            filters: Optional filter conditions

        Returns:
            List of search results
        """
        # Generate embedding for the query
        embedding_result = await self.embedding_generator.generate_embedding(query)

        # Search the vector store
        results = self.vector_store.search(
            query_embedding=embedding_result.embedding,
            n_results=n_results,
            where=filters,
        )

        return [result.to_dict() for result in results]

    def search_sync(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """Synchronous wrapper for search."""
        return asyncio.run(self.search(query, n_results, filters))

    async def find_symbol(
        self,
        symbol_name: str,
        symbol_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Find a symbol by name.

        Args:
            symbol_name: Name of the symbol to find
            symbol_type: Optional type filter (function, struct, etc.)

        Returns:
            List of matching symbols
        """
        filters = {"name": symbol_name}
        if symbol_type:
            filters["chunk_type"] = symbol_type

        # Search by metadata first
        results = self.vector_store.get(where=filters)

        # Also do a semantic search for the symbol name
        semantic_results = await self.search(
            f"function or symbol named {symbol_name}",
            n_results=10,
        )

        # Combine results
        seen_ids = set()
        combined = []

        for result in semantic_results:
            if result["id"] not in seen_ids:
                if result["metadata"].get("name") == symbol_name:
                    combined.append(result)
                    seen_ids.add(result["id"])

        return combined

    async def find_references(
        self,
        symbol_name: str,
    ) -> list[dict]:
        """
        Find references to a symbol.

        Args:
            symbol_name: Name of the symbol

        Returns:
            List of code chunks that may reference the symbol
        """
        # Search for code containing the symbol name
        results = self.vector_store.search_by_text(
            query_text=symbol_name,
            query_embedding=[],  # Will be computed from query_text
            n_results=20,
            filters=None,
        )

        # Filter results that contain the symbol name
        matching = []
        for result in results:
            if symbol_name in result.content:
                matching.append(result.to_dict())

        return matching

    async def get_file_context(
        self,
        file_path: str,
        line_number: Optional[int] = None,
    ) -> dict:
        """
        Get context for a file or specific line.

        Args:
            file_path: Path to the file
            line_number: Optional line number for specific context

        Returns:
            Dictionary with file context
        """
        # Get all chunks for this file
        results = self.vector_store.get(
            where={"file_path": file_path},
        )

        if not results.get("ids"):
            return {"error": f"No indexed content found for {file_path}"}

        context = {
            "file_path": file_path,
            "chunks": [],
        }

        for i, doc_id in enumerate(results["ids"]):
            chunk_info = {
                "id": doc_id,
                "content": results["documents"][i] if results["documents"] else "",
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            }
            context["chunks"].append(chunk_info)

        # If line number specified, find the containing chunk
        if line_number:
            context["line_number"] = line_number
            for chunk in context["chunks"]:
                start = chunk["metadata"].get("start_line", 0)
                end = chunk["metadata"].get("end_line", 0)
                if start <= line_number <= end:
                    context["containing_chunk"] = chunk
                    break

        return context

    def get_stats(self) -> dict:
        """Get indexing statistics."""
        return {
            **self.stats.to_dict(),
            "total_chunks": self.vector_store.count(),
            "indexed_files": len(self._indexed_files),
        }

    def reset(self) -> None:
        """Reset the index."""
        self.vector_store.reset()
        self._indexed_files.clear()
        self.stats = IndexStats()
