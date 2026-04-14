"""
Embedding generation for code chunks.

This module provides embedding generation via configurable API endpoints.
Supports Anthropic, OpenAI, and custom embedding services.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx


class EmbeddingProvider(Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


@dataclass
class EmbeddingResult:
    """Result of an embedding generation request."""

    embedding: list[float]
    model: str
    usage: dict = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}


class EmbeddingGenerator:
    """Generates embeddings for code chunks via API."""

    def __init__(
        self,
        provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the embedding generator.

        Args:
            provider: The embedding provider to use
            api_key: API key for the provider (or env var will be used)
            model: Model name for embeddings
            base_url: Custom base URL for API requests
            timeout: Request timeout in seconds
        """
        self.provider = provider
        self.api_key = api_key
        self.timeout = timeout

        # Set defaults based on provider
        if provider == EmbeddingProvider.OPENAI:
            self.model = model or "text-embedding-3-small"
            self.base_url = base_url or "https://api.openai.com/v1"
            self.embeddings_endpoint = "/embeddings"
        elif provider == EmbeddingProvider.ANTHROPIC:
            self.model = model or "claude-3-5-sonnet-20241022"
            self.base_url = base_url or "https://api.anthropic.com/v1"
            # Anthropic doesn't have a dedicated embeddings API
            # This is a placeholder for future implementation
            self.embeddings_endpoint = "/embeddings"
        elif provider == EmbeddingProvider.CUSTOM:
            self.model = model or "default"
            self.base_url = base_url or "http://localhost:8000"
            self.embeddings_endpoint = "/embed"
        else:
            raise ValueError(f"Unknown provider: {provider}")

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "codesearch-plugin/0.1.0",
        }

        if self.api_key:
            if self.provider == EmbeddingProvider.OPENAI:
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.provider == EmbeddingProvider.ANTHROPIC:
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"

        return headers

    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """
        Generate an embedding for the given text.

        Args:
            text: The text to embed

        Returns:
            EmbeddingResult with the embedding vector
        """
        client = await self._get_client()

        if self.provider == EmbeddingProvider.OPENAI:
            return await self._generate_openai_embedding(client, text)
        elif self.provider == EmbeddingProvider.ANTHROPIC:
            return await self._generate_anthropic_embedding(client, text)
        elif self.provider == EmbeddingProvider.CUSTOM:
            return await self._generate_custom_embedding(client, text)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _generate_openai_embedding(
        self, client: httpx.AsyncClient, text: str
    ) -> EmbeddingResult:
        """Generate embedding using OpenAI API."""
        response = await client.post(
            self.embeddings_endpoint,
            json={
                "model": self.model,
                "input": text,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        data = response.json()

        return EmbeddingResult(
            embedding=data["data"][0]["embedding"],
            model=data["model"],
            usage=data.get("usage", {}),
        )

    async def _generate_anthropic_embedding(
        self, client: httpx.AsyncClient, text: str
    ) -> EmbeddingResult:
        """
        Generate embedding using Anthropic API.

        Note: Anthropic doesn't currently offer embeddings.
        This is a placeholder that uses their text API to generate
        a simple representation. In practice, you'd use a different
        embedding provider.
        """
        # For now, use OpenAI-compatible endpoint if available
        # Many providers offer OpenAI-compatible APIs
        response = await client.post(
            self.embeddings_endpoint,
            json={
                "model": self.model,
                "input": text,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        data = response.json()

        return EmbeddingResult(
            embedding=data["data"][0]["embedding"],
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
        )

    async def _generate_custom_embedding(
        self, client: httpx.AsyncClient, text: str
    ) -> EmbeddingResult:
        """Generate embedding using a custom API."""
        response = await client.post(
            self.embeddings_endpoint,
            json={
                "text": text,
                "model": self.model,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Expect format: {"embedding": [...], "model": "..."}
        return EmbeddingResult(
            embedding=data["embedding"],
            model=data.get("model", self.model),
        )

    async def generate_batch(
        self, texts: list[str], batch_size: int = 10
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch

        Returns:
            List of EmbeddingResult objects
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            tasks = [self.generate_embedding(text) for text in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    # Add None for failed requests
                    results.append(
                        EmbeddingResult(
                            embedding=[],
                            model=self.model,
                            usage={"error": str(result)},
                        )
                    )
                else:
                    results.append(result)

        return results

    def generate_embedding_sync(self, text: str) -> EmbeddingResult:
        """Synchronous wrapper for generate_embedding."""
        return asyncio.run(self.generate_embedding(text))

    def generate_batch_sync(
        self, texts: list[str], batch_size: int = 10
    ) -> list[EmbeddingResult]:
        """Synchronous wrapper for generate_batch."""
        return asyncio.run(self.generate_batch(texts, batch_size))

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, "_client") and self._client and not self._client.is_closed:
            try:
                asyncio.run(self._client.aclose())
            except RuntimeError:
                pass  # No event loop available
