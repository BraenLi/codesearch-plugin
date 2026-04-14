"""
Vector storage layer using ChromaDB.

This module provides index storage and retrieval using ChromaDB,
a lightweight, embeddable vector database.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import QueryResult


@dataclass
class SearchResponse:
    """Response from a vector search."""

    id: str
    content: str
    score: float
    metadata: dict

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorStore:
    """Vector store using ChromaDB."""

    def __init__(
        self,
        collection_name: str = "code_chunks",
        persist_directory: Optional[str] = None,
        embedding_dimension: int = 1536,  # OpenAI text-embedding-3-small default
    ):
        """
        Initialize the vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
            embedding_dimension: Dimension of the embedding vectors
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embedding_dimension = embedding_dimension

        # Initialize ChromaDB client
        if persist_directory:
            settings = ChromaSettings(
                is_persistent=True,
                persist_directory=persist_directory,
            )
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=settings,
            )
        else:
            self.client = chromadb.Client()

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"dimension": embedding_dimension},
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """
        Add documents to the vector store.

        Args:
            ids: List of document IDs
            embeddings: List of embedding vectors
            documents: List of document texts
            metadatas: Optional list of metadata dictionaries
        """
        if metadatas is None:
            metadatas = [{}] * len(ids)

        # ChromaDB requires metadata values to be strings, numbers, or bools
        # and requires non-empty metadata dicts. None values are not allowed.
        sanitized_metadatas = []
        for meta in metadatas:
            sanitized = {}
            for k, v in meta.items():
                # Skip None values
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                elif isinstance(v, dict):
                    sanitized[k] = str(v)
                else:
                    sanitized[k] = str(v)
            # ChromaDB requires non-empty metadata
            if not sanitized:
                sanitized = {"_empty": "true"}
            sanitized_metadatas.append(sanitized)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=sanitized_metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> list[SearchResponse]:
        """
        Search for similar documents.

        Args:
            query_embedding: The query embedding vector
            n_results: Number of results to return
            where: Optional filter conditions
            where_document: Optional document filter conditions

        Returns:
            List of SearchResponse objects
        """
        results: QueryResult = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
        )

        responses = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                response = SearchResponse(
                    id=doc_id,
                    content=results["documents"][0][i] or "",
                    score=results["distances"][0][i] if results["distances"] else 0.0,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                )
                responses.append(response)

        return responses

    def search_by_text(
        self,
        query_text: str,
        query_embedding: list[float],
        n_results: int = 5,
        filters: Optional[dict] = None,
    ) -> list[SearchResponse]:
        """
        Search by text query with pre-computed embedding.

        Args:
            query_text: The query text (for reference)
            query_embedding: The query embedding vector
            n_results: Number of results to return
            filters: Optional filter conditions

        Returns:
            List of SearchResponse objects
        """
        return self.search(
            query_embedding=query_embedding,
            n_results=n_results,
            where=filters,
        )

    def get(
        self,
        ids: Optional[list[str]] = None,
        where: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get documents from the store.

        Args:
            ids: List of document IDs to retrieve
            where: Optional filter conditions
            limit: Maximum number of documents to return

        Returns:
            Dictionary with ids, documents, and metadatas
        """
        return self.collection.get(
            ids=ids,
            where=where,
            limit=limit,
        )

    def delete(
        self,
        ids: Optional[list[str]] = None,
        where: Optional[dict] = None,
    ) -> None:
        """
        Delete documents from the store.

        Args:
            ids: List of document IDs to delete
            where: Optional filter conditions
        """
        if ids:
            self.collection.delete(ids=ids, where=where)

    def count(self) -> int:
        """Get the total number of documents in the store."""
        return self.collection.count()

    def reset(self) -> None:
        """Reset the collection (delete all documents)."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"dimension": self.embedding_dimension},
        )

    def list_collections(self) -> list[str]:
        """List all collections in the database."""
        return [col.name for col in self.client.list_collections()]

    @staticmethod
    def generate_id(content: str, file_path: str = "") -> str:
        """Generate a unique ID for content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        if file_path:
            file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
            return f"{file_hash}_{content_hash}"
        return content_hash
