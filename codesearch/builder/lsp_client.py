"""
LSP client for communicating with language servers.

This module provides a lightweight LSP client for communicating
with clangd or other LSP servers.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class LSPMessage:
    """LSP protocol message."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[dict] = None
    result: Optional[Any] = None
    error: Optional[dict] = None


class LSPClient:
    """
    Lightweight LSP client for clangd communication.

    Usage:
        client = LSPClient()
        await client.start_server()
        await client.initialize(root_path)
        # Use client.send_request() for LSP methods
        await client.stop_server()
    """

    def __init__(self, server_command: Optional[list[str]] = None):
        """
        Initialize LSP client.

        Args:
            server_command: Command to start LSP server.
                           Default: ["clangd", "--enable-config-flag"]
        """
        self.server_command = server_command or ["clangd", "--enable-config-flag"]
        self._process: Optional[asyncio.subprocess.Process] = None
        self._message_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_buffer = b""
        self._running = False
        self._initialized = False
        self._read_task: Optional[asyncio.Task] = None

    async def start_server(self) -> bool:
        """Start the LSP server process."""
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._running = True
            # Start the message reading task and wait for it to be ready
            self._read_task = asyncio.create_task(self._read_messages())
            # Give the server time to initialize
            await asyncio.sleep(0.5)
            return True
        except FileNotFoundError:
            raise RuntimeError(
                "clangd not found. Please install clangd: "
                "apt install clangd (Linux) or brew install llvm (macOS)"
            )

    async def stop_server(self) -> None:
        """Stop the LSP server process."""
        if self._process and self._process.returncode is None:
            self._running = False
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                self._process.kill()
                await self._process.wait()

    async def initialize(self, root_path: str) -> dict:
        """Send initialize request."""
        return await self.send_request(
            "initialize",
            {
                "processId": None,
                "clientInfo": {"name": "codesearch-plugin", "version": "0.1.0"},
                "rootUri": f"file://{Path(root_path).absolute()}",
                "capabilities": {
                    "textDocument": {
                        "synchronization": {"dynamicRegistration": True},
                        "documentSymbol": {"dynamicRegistration": True},
                        "reference": {"dynamicRegistration": True},
                        "definition": {"dynamicRegistration": True},
                    }
                },
            },
        )

    async def send_request(self, method: str, params: dict) -> Any:
        """Send an LSP request and wait for response."""
        self._message_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params,
        }

        future = asyncio.Future()
        self._pending_requests[self._message_id] = future

        await self._send_message(message)

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            del self._pending_requests[self._message_id]
            raise RuntimeError(f"Request timeout for method: {method}")

    async def send_notification(self, method: str, params: dict) -> None:
        """Send an LSP notification (no response expected)."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._send_message(message)

    async def _send_message(self, message: dict) -> None:
        """Send a message to the LSP server."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("LSP server not started")

        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n".encode("ascii")
        body = content.encode("utf-8")

        self._process.stdin.write(header + body)
        await self._process.stdin.drain()

    async def _read_messages(self) -> None:
        """Read and parse messages from LSP server."""
        if not self._process or not self._process.stdout:
            return

        while self._running:
            try:
                # Read Content-Length header
                line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=1.0
                )
                if not line:
                    break

                self._read_buffer += line

                if b"\r\n" in self._read_buffer:
                    header_line, _, rest = self._read_buffer.partition(b"\r\n")
                    self._read_buffer = rest

                    if header_line.startswith(b"Content-Length: "):
                        content_length = int(header_line[16:])

                        # Read blank line
                        while b"\r\n" not in self._read_buffer:
                            chunk = await self._process.stdout.read(1)
                            if not chunk:
                                break
                            self._read_buffer += chunk

                        self._read_buffer = self._read_buffer[2:]  # Skip \r\n

                        # Read content
                        while len(self._read_buffer) < content_length:
                            chunk = await self._process.stdout.read(
                                content_length - len(self._read_buffer)
                            )
                            if not chunk:
                                break
                            self._read_buffer += chunk

                        content = self._read_buffer[:content_length].decode("utf-8")
                        self._read_buffer = self._read_buffer[content_length:]

                        # Parse and handle message
                        self._handle_message(json.loads(content))

            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    def _handle_message(self, message: dict) -> None:
        """Handle incoming LSP message."""
        if "id" in message:
            if message["id"] in self._pending_requests:
                future = self._pending_requests.pop(message["id"])
                if "error" in message:
                    future.set_exception(RuntimeError(message["error"]))
                else:
                    future.set_result(message.get("result"))
