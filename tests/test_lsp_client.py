"""Tests for LSP client."""

import pytest

from codesearch.builder.lsp_client import LSPClient


@pytest.mark.asyncio
async def test_lsp_client_connect():
    """Test connecting to clangd server."""
    client = LSPClient()
    connected = await client.start_server()
    assert connected is True
    await client.stop_server()


@pytest.mark.asyncio
async def test_lsp_client_initialize():
    """Test LSP initialization."""
    client = LSPClient()
    await client.start_server()
    result = await client.initialize("/test/path")
    assert result is not None
    assert "capabilities" in result
    await client.stop_server()
