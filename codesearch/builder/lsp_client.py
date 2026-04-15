<<<<<<< HEAD
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
=======
"""LSP client for communicating with clangd or other LSP servers."""

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
>>>>>>> feature/clangd-lsp


@dataclass
class LSPMessage:
    """LSP protocol message."""
<<<<<<< HEAD
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: Optional[str] = None
    params: Optional[dict] = None
    result: Optional[Any] = None
    error: Optional[dict] = None

    def to_request_dict(self) -> dict:
        """Convert to dictionary for sending request."""
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params,
        }

    def to_notification_dict(self) -> dict:
        """Convert to dictionary for sending notification (no id)."""
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }

    @classmethod
    def from_response(cls, data: dict) -> "LSPMessage":
        """Parse incoming response into LSPMessage."""
=======

    jsonrpc: str = "2.0"
    id: int | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LSPMessage":
        """Create LSPMessage from dictionary."""
>>>>>>> feature/clangd-lsp
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )


class LSPClient:
<<<<<<< HEAD
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
=======
    """Lightweight LSP client for clangd communication."""

    def __init__(self, clangd_path: str = "clangd"):
        """Initialize LSP client.

        Args:
            clangd_path: Path to clangd executable or "clangd" to search PATH.
        """
        self._clangd_path = clangd_path
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self._buffer = b""

    async def start_server(self) -> bool:
        """Start clangd subprocess.

        Returns:
            True if successfully started, False otherwise.
        """
        # Resolve clangd path
        if self._clangd_path == "clangd":
            resolved = shutil.which("clangd")
            if resolved is None:
                return False
            self._clangd_path = resolved

        try:
            # Start clangd with stdin/stdout pipes for LSP communication
            self._process = await asyncio.create_subprocess_exec(
                self._clangd_path,
                "--background-index=false",
                "--clang-tidy=false",
                "--completion-style=detailed",
>>>>>>> feature/clangd-lsp
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
<<<<<<< HEAD
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

        message = LSPMessage(
            id=self._message_id,
            method=method,
            params=params,
        )

        future = asyncio.Future()
        self._pending_requests[self._message_id] = future

        await self._send_message(message.to_request_dict())

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            del self._pending_requests[self._message_id]
            raise RuntimeError(f"Request timeout for method: {method}")

    async def send_notification(self, method: str, params: dict) -> None:
        """Send an LSP notification (no response expected)."""
        message = LSPMessage(
            method=method,
            params=params,
        )
        await self._send_message(message.to_notification_dict())

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

    def _handle_message(self, data: dict) -> None:
        """Handle incoming LSP message."""
        message = LSPMessage.from_response(data)

        if message.id is not None:
            if message.id in self._pending_requests:
                future = self._pending_requests.pop(message.id)
                if message.error:
                    future.set_exception(RuntimeError(message.error))
                else:
                    future.set_result(message.result)
=======

            # Start message reader task
            self._read_task = asyncio.create_task(self._read_messages())

            return True
        except (FileNotFoundError, OSError):
            return False

    async def stop_server(self) -> None:
        """Terminate clangd subprocess."""
        # Send shutdown notification if process is running
        if self._process is not None:
            try:
                await self.send_request("shutdown", {})
            except Exception:
                pass

            # Send exit notification
            try:
                await self._send_message(LSPMessage(method="exit"))
            except Exception:
                pass

        # Cancel read task
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # Terminate process
        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                self._process.kill()
                await self._process.wait()

        self._process = None
        self._read_task = None

    async def initialize(self, root_path: str) -> dict[str, Any]:
        """Send LSP initialize request.

        Args:
            root_path: Root path of the workspace.

        Returns:
            Server capabilities dictionary.
        """
        root_uri = Path(root_path).resolve().as_uri()

        params = {
            "processId": None,
            "rootUri": root_uri,
            "rootPath": root_path,
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": False,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "didSave": True,
                    },
                    "completion": {
                        "dynamicRegistration": False,
                        "completionItem": {
                            "snippetSupport": False,
                            "commitCharactersSupport": False,
                        },
                    },
                    "hover": {
                        "dynamicRegistration": False,
                        "contentFormat": ["markdown", "plaintext"],
                    },
                    "definition": {
                        "dynamicRegistration": False,
                        "linkSupport": True,
                    },
                    "references": {
                        "dynamicRegistration": False,
                    },
                },
                "workspace": {
                    "workspaceFolders": False,
                    "configuration": False,
                },
            },
            "initializationOptions": {},
        }

        result = await self.send_request("initialize", params)
        return result

    async def send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send LSP request and wait for response.

        Args:
            method: LSP method name (e.g., "textDocument/definition").
            params: Request parameters.

        Returns:
            Response result dictionary.

        Raises:
            RuntimeError: If server is not running.
            Exception: If request fails.
        """
        if self._process is None:
            raise RuntimeError("LSP server is not running. Call start_server() first.")

        self._request_id += 1
        request_id = self._request_id

        # Create future for this request
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        # Send request
        message = LSPMessage(id=request_id, method=method, params=params)
        await self._send_message(message)

        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError as e:
            del self._pending_requests[request_id]
            raise RuntimeError(f"Request '{method}' timed out") from e
        finally:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]

    async def _send_message(self, message: LSPMessage) -> None:
        """Send raw LSP message with Content-Length header.

        Args:
            message: LSPMessage to send.
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("LSP server is not running")

        # Serialize message to JSON
        content = json.dumps(message.to_dict(), separators=(",", ":"))
        content_bytes = content.encode("utf-8")

        # Build LSP message with Content-Length header
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        header_bytes = header.encode("utf-8")

        # Write to stdin
        self._process.stdin.write(header_bytes + content_bytes)
        await self._process.stdin.drain()

    async def _read_messages(self) -> None:
        """Async task to read and parse LSP responses from stdout."""
        if self._process is None or self._process.stdout is None:
            return

        try:
            while True:
                # Read header to get content length
                header = await self._read_until(b"\r\n\r\n")
                if not header:
                    break

                # Parse Content-Length
                header_str = header.decode("utf-8")
                content_length = None
                for line in header_str.split("\r\n"):
                    if line.startswith("Content-Length: "):
                        content_length = int(line.split(": ")[1])
                        break

                if content_length is None:
                    continue

                # Read content
                content_bytes = await self._read_exact(content_length)
                if not content_bytes:
                    break

                # Parse JSON and handle message
                content_str = content_bytes.decode("utf-8")
                data = json.loads(content_str)
                message = LSPMessage.from_dict(data)
                await self._handle_message(message)

        except asyncio.CancelledError:
            pass
        except Exception:
            # Log error but continue reading
            pass

    async def _read_until(self, delimiter: bytes) -> bytes:
        """Read from stdout until delimiter is found.

        Args:
            delimiter: Byte sequence to read until.

        Returns:
            Bytes read including delimiter.
        """
        if self._process is None or self._process.stdout is None:
            return b""

        while delimiter not in self._buffer:
            try:
                chunk = await asyncio.wait_for(self._process.stdout.read(4096), timeout=30.0)
                if not chunk:
                    return b""
                self._buffer += chunk
            except asyncio.TimeoutError:
                return b""

        # Split at delimiter
        idx = self._buffer.index(delimiter)
        result = self._buffer[: idx + len(delimiter)]
        self._buffer = self._buffer[idx + len(delimiter) :]
        return result

    async def _read_exact(self, length: int) -> bytes:
        """Read exact number of bytes from stdout.

        Args:
            length: Number of bytes to read.

        Returns:
            Bytes read.
        """
        if self._process is None or self._process.stdout is None:
            return b""

        while len(self._buffer) < length:
            try:
                chunk = await asyncio.wait_for(self._process.stdout.read(4096), timeout=30.0)
                if not chunk:
                    break
                self._buffer += chunk
            except asyncio.TimeoutError:
                break

        result = self._buffer[:length]
        self._buffer = self._buffer[length:]
        return result

    async def _handle_message(self, message: LSPMessage) -> None:
        """Route responses to pending requests.

        Args:
            message: LSPMessage received from server.
        """
        # Handle response to request
        if message.id is not None and message.id in self._pending_requests:
            future = self._pending_requests[message.id]
            if not future.done():
                if message.error is not None:
                    future.set_exception(RuntimeError(f"LSP Error: {message.error}"))
                else:
                    future.set_result(message.result or {})

        # Handle notifications (server -> client messages without ID)
        elif message.id is None and message.method is not None:
            # Could handle notifications here (e.g., publishDiagnostics)
            pass
>>>>>>> feature/clangd-lsp
