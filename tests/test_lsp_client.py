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
    # Note: This test is flaky on some systems due to timing issues with clangd
    # The ClangdParser tests (test_clangd_parser.py) test the full LSP flow
    pytest.skip("Integration tested via test_clangd_parser.py")

