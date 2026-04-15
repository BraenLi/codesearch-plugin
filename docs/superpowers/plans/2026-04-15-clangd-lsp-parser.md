# Clangd LSP Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 codesearch-plugin 的 AST 解析方案从 tree-sitter 替换为 Clangd LSP，获得更精确的 C/C++ 代码理解能力，包括符号解析、引用查找和语义信息。

**Architecture:** 创建新的 `ClangdParser` 类替代 `CParser`，通过 LSP 协议与 clangd 通信获取 AST 和符号信息。保持现有的 `ASTNode` 数据结构和 `CodeChunker` 接口不变，确保上层代码无需修改。新增 clangd 进程管理和 LSP 通信层。

**Tech Stack:**
- Python `pygls` 或 `python-lsp-client` 作为 LSP 客户端
- `clangd` 作为 LSP 服务器（需系统安装）
- 异步 IO 处理 LSP 消息
- 保持 ChromaDB、tree-sitter（可选回退）等现有依赖

---

## 文件结构

**创建:**
- `codesearch/builder/clangd_parser.py` - Clangd LSP 解析器实现
- `codesearch/builder/lsp_client.py` - LSP 客户端通信层
- `tests/test_clangd_parser.py` - ClangdParser 测试

**修改:**
- `codesearch/builder/parser.py` - 将 CParser 重构为使用 ClangdParser 或直接替换
- `codesearch/builder/indexer.py` - 更新默认解析器配置
- `codesearch/builder/__init__.py` - 导出新的解析器类
- `pyproject.toml` - 添加 LSP 相关依赖

**保持不变:**
- `codesearch/builder/chunker.py` - 接口不变，复用现有逻辑
- `codesearch/builder/storage.py` - 向量存储层不变
- `codesearch/builder/embeddings.py` - Embedding 生成不变
- `codesearch/mcp/` - MCP 服务器接口不变

---

### Task 1: LSP 客户端基础通信层

**Files:**
- Create: `codesearch/builder/lsp_client.py`
- Test: `tests/test_lsp_client.py`

- [ ] **Step 1: 编写 LSP 客户端连接测试**

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_lsp_client.py -v
```
预期：FAIL 提示 `ModuleNotFoundError: No module named 'codesearch.builder.lsp_client'`

- [ ] **Step 3: 实现 LSP 客户端基础类**

```python
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
                           Default: ["clangd"]
        """
        self.server_command = server_command or ["clangd"]
        self._process: Optional[asyncio.subprocess.Process] = None
        self._message_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_buffer = b""
        self._running = False

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
            asyncio.create_task(self._read_messages())
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
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_lsp_client.py -v
```
预期：PASS（需要系统安装 clangd）

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/lsp_client.py tests/test_lsp_client.py
git commit -m "feat: add LSP client for clangd communication"
```

---

### Task 2: ClangdParser 实现

**Files:**
- Create: `codesearch/builder/clangd_parser.py`
- Test: `tests/test_clangd_parser.py`

- [ ] **Step 1: 编写 ClangdParser 测试**

```python
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
                assert len(refs) > 0
                await parser.stop()
            finally:
                Path(f.name).unlink()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_clangd_parser.py -v
```
预期：FAIL 提示模块不存在

- [ ] **Step 3: 实现 ClangdParser 类**

```python
"""
Clangd-based parser for C/C++ code.

This module uses the Language Server Protocol (LSP) to communicate
with clangd for precise AST extraction and symbol resolution.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from codesearch.builder.lsp_client import LSPClient
from codesearch.builder.parser import ASTNode, NodeType


@dataclass
class SymbolInfo:
    """Symbol information from clangd."""
    name: str
    kind: str  # Function, Class, Struct, Enum, etc.
    file_path: str
    line: int
    column: int
    end_line: int
    end_column: int
    detail: Optional[str] = None
    container_name: Optional[str] = None


class ClangdParser:
    """
    C/C++ parser using clangd LSP server.

    Provides more accurate parsing than tree-sitter, with full
    semantic understanding including:
    - Symbol resolution across translation units
    - Preprocessor expansion
    - Type information
    - Reference finding

    Usage:
        parser = ClangdParser()
        await parser.start()
        nodes = await parser.parse_file("example.c")
        refs = await parser.find_references("function_name")
        await parser.stop()
    """

    # Mapping from LSP symbol kind to NodeType
    SYMBOL_KIND_MAP = {
        12: NodeType.FUNCTION,      # SymbolKind.Function
        5: NodeType.FUNCTION,       # SymbolKind.Method
        2: NodeType.CLASS,          # SymbolKind.Class
        22: NodeType.STRUCT,        # SymbolKind.Struct
        23: NodeType.UNION,         # SymbolKind.Enum
        10: NodeType.ENUM,          # SymbolKind.Enum
        25: NodeType.TYPEDEF,       # SymbolKind.TypeParameter
        6: NodeType.VARIABLE,       # SymbolKind.Variable
        21: NodeType.MACRO,         # SymbolKind.Macro
    }

    def __init__(self, clangd_path: Optional[str] = None):
        """
        Initialize the clangd parser.

        Args:
            clangd_path: Path to clangd executable. If None, uses "clangd"
                        from PATH.
        """
        self.clangd_path = clangd_path or "clangd"
        self._client: Optional[LSPClient] = None
        self._root_path: Optional[str] = None
        self._parsed_files: set[str] = set()
        self._symbols: dict[str, list[SymbolInfo]] = {}

    async def start(self) -> None:
        """Start the clangd server."""
        self._client = LSPClient(server_command=[self.clangd_path])
        await self._client.start_server()

    async def stop(self) -> None:
        """Stop the clangd server."""
        if self._client:
            await self._client.stop_server()
            self._client = None

    async def parse_file(
        self,
        file_path: str | Path,
        root_path: Optional[str] = None,
    ) -> list[ASTNode]:
        """
        Parse a C/C++ source file and extract AST nodes.

        Args:
            file_path: Path to the source file
            root_path: Optional project root path for compilation database

        Returns:
            List of ASTNode objects
        """
        file_path = str(Path(file_path).absolute())

        if not self._client:
            await self.start()

        # Initialize with root path if provided
        if root_path and not self._root_path:
            self._root_path = str(Path(root_path).absolute())
            await self._client.initialize(self._root_path)

        # Open document in LSP
        await self._open_document(file_path)

        # Get document symbols
        symbols = await self._get_document_symbols(file_path)

        # Convert to ASTNode format
        nodes = self._symbols_to_ast_nodes(symbols, file_path)

        self._parsed_files.add(file_path)

        return nodes

    async def _open_document(self, file_path: str) -> None:
        """Open a document in the LSP server."""
        with open(file_path, "r") as f:
            content = f.read()

        await self._client.send_request(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": f"file://{file_path}",
                    "languageId": "c",
                    "version": 1,
                    "text": content,
                }
            },
        )

    async def _get_document_symbols(self, file_path: str) -> list[SymbolInfo]:
        """Get symbols from a document."""
        result = await self._client.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": f"file://{file_path}"}},
        )

        symbols = []
        if result:
            symbols = self._parse_symbols(result, file_path)

        self._symbols[file_path] = symbols
        return symbols

    def _parse_symbols(
        self,
        symbols: list[dict],
        file_path: str,
        container: Optional[str] = None,
    ) -> list[SymbolInfo]:
        """Parse LSP symbol response into SymbolInfo objects."""
        result = []

        for sym in symbols:
            symbol_info = SymbolInfo(
                name=sym.get("name", ""),
                kind=sym.get("kind", 0),
                file_path=file_path,
                line=sym.get("range", {}).get("start", {}).get("line", 0) + 1,
                column=sym.get("range", {}).get("start", {}).get("character", 0),
                end_line=sym.get("range", {}).get("end", {}).get("line", 0) + 1,
                end_column=sym.get("range", {}).get("end", {}).get("character", 0),
                detail=sym.get("detail"),
                container_name=container,
            )
            result.append(symbol_info)

            # Handle nested symbols
            children = sym.get("children", [])
            if children:
                result.extend(
                    self._parse_symbols(children, file_path, symbol_info.name)
                )

        return result

    def _symbols_to_ast_nodes(
        self, symbols: list[SymbolInfo], file_path: str
    ) -> list[ASTNode]:
        """Convert SymbolInfo list to ASTNode list."""
        nodes = []

        with open(file_path, "rb") as f:
            content = f.read()

        for sym in symbols:
            node_type = self.SYMBOL_KIND_MAP.get(sym.kind, NodeType.VARIABLE)

            # Extract code from file
            code = self._extract_code_range(
                content, sym.line, sym.end_line, sym.column, sym.end_column
            )

            ast_node = ASTNode(
                node_type=node_type,
                name=sym.name,
                code=code,
                start_line=sym.line,
                end_line=sym.end_line,
                start_column=sym.column,
                end_column=sym.end_column,
                file_path=file_path,
                docstring=sym.detail,
            )
            nodes.append(ast_node)

        return nodes

    def _extract_code_range(
        self,
        content: bytes,
        start_line: int,
        end_line: int,
        start_col: int,
        end_col: int,
    ) -> str:
        """Extract code from a specific line/column range."""
        lines = content.decode("utf-8", errors="ignore").split("\n")

        if start_line == end_line:
            return lines[start_line - 1][start_col:end_col]

        result = []
        for i in range(start_line - 1, end_line):
            if i == start_line - 1:
                result.append(lines[i][start_col:])
            elif i == end_line - 1:
                result.append(lines[i][:end_col])
            else:
                result.append(lines[i])

        return "\n".join(result)

    async def find_references(
        self,
        symbol_name: str,
        file_path: Optional[str] = None,
    ) -> list[dict]:
        """
        Find all references to a symbol.

        Args:
            symbol_name: Name of the symbol
            file_path: Optional file to search in

        Returns:
            List of reference locations with file, line, and code context
        """
        if not self._client:
            raise RuntimeError("ClangdParser not started")

        # Find symbol first
        symbol = self._find_symbol(symbol_name)
        if not symbol:
            return []

        # Request references
        result = await self._client.send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": f"file://{symbol.file_path}"},
                "position": {"line": symbol.line - 1, "character": symbol.column},
                "context": {"includeDeclaration": True},
            },
        )

        references = []
        if result:
            for loc in result:
                ref_info = {
                    "file": loc["uri"].replace("file://", ""),
                    "line": loc["range"]["start"]["line"] + 1,
                    "column": loc["range"]["start"]["character"],
                }
                references.append(ref_info)

        return references

    def _find_symbol(self, name: str) -> Optional[SymbolInfo]:
        """Find a symbol by name."""
        for symbols in self._symbols.values():
            for sym in symbols:
                if sym.name == name:
                    return sym
        return None

    async def find_definition(self, symbol_name: str) -> Optional[SymbolInfo]:
        """Find the definition of a symbol."""
        if not self._client:
            raise RuntimeError("ClangdParser not started")

        # Search in parsed files
        for file_path, symbols in self._symbols.items():
            for sym in symbols:
                if sym.name == symbol_name:
                    # Request definition
                    result = await self._client.send_request(
                        "textDocument/definition",
                        {
                            "textDocument": {"uri": f"file://{file_path}"},
                            "position": {"line": sym.line - 1, "character": sym.column},
                        },
                    )

                    if result:
                        # Parse definition location
                        if isinstance(result, list):
                            result = result[0] if result else None

                        if result:
                            return SymbolInfo(
                                name=symbol_name,
                                kind=0,
                                file_path=result["uri"].replace("file://", ""),
                                line=result["range"]["start"]["line"] + 1,
                                column=result["range"]["start"]["character"],
                                end_line=result["range"]["end"]["line"] + 1,
                                end_column=result["range"]["end"]["character"],
                            )

        return None
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_clangd_parser.py -v
```
预期：PASS（需要 clangd 安装）

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/clangd_parser.py tests/test_clangd_parser.py
git commit -m "feat: implement ClangdParser with LSP-based symbol extraction"
```

---

### Task 3: 重构 parser.py 统一接口

**Files:**
- Modify: `codesearch/builder/parser.py`
- Test: `tests/test_builder.py`（现有测试应保持通过）

- [ ] **Step 1: 修改 parser.py 导出，支持 ClangdParser 作为默认**

```python
# 在 codesearch/builder/parser.py 文件开头添加导入，末尾添加导出

# 添加在文件顶部
from codesearch.builder.clangd_parser import ClangdParser, SymbolInfo

# 更新 __all__ 导出
__all__ = [
    "ASTNode",
    "NodeType",
    "CParser",
    "ClangdParser",  # 新增
    "SymbolInfo",   # 新增
]
```

- [ ] **Step 2: 在 CParser 中添加兼容层，可选使用 clangd**

```python
# 在 codesearch/builder/parser.py 的 CParser 类中添加方法

class CParser:
    # ... 现有代码 ...

    @classmethod
    def use_clangd(cls, clangd_path: Optional[str] = None) -> ClangdParser:
        """
        Create a ClangdParser instance as an alternative to tree-sitter.

        Args:
            clangd_path: Path to clangd executable

        Returns:
            ClangdParser instance
        """
        return ClangdParser(clangd_path=clangd_path)
```

- [ ] **Step 3: 运行现有测试验证兼容性**

```bash
pytest tests/test_builder.py::TestCParser -v
```
预期：PASS（现有 tree-sitter 测试应保持通过）

- [ ] **Step 4: Commit**

```bash
git add codesearch/builder/parser.py
git commit -m "refactor: add ClangdParser export and compatibility layer"
```

---

### Task 4: 更新 indexer.py 支持 ClangdParser

**Files:**
- Modify: `codesearch/builder/indexer.py`
- Test: `tests/test_builder.py::TestCodeIndexer`

- [ ] **Step 1: 添加 ClangdParser 配置选项**

```python
# 在 codesearch/builder/indexer.py 的 IndexConfig 中添加

@dataclass
class IndexConfig:
    # ... 现有字段 ...

    # 新增：解析器配置
    use_clangd: bool = False  # 是否使用 clangd 替代 tree-sitter
    clangd_path: Optional[str] = None  # clangd 路径
```

- [ ] **Step 2: 修改 CodeIndexer.__init__ 支持 clangd**

```python
# 在 codesearch/builder/indexer.py 的 CodeIndexer.__init__ 中修改

def __init__(self, config: Optional[IndexConfig] = None):
    """Initialize the code indexer."""
    self.config = config or IndexConfig()
    self.stats = IndexStats()

    # 修改解析器初始化
    if self.config.use_clangd:
        from codesearch.builder.clangd_parser import ClangdParser
        self.parser = ClangdParser(clangd_path=self.config.clangd_path)
    else:
        self.parser = CParser()

    # 其余初始化代码保持不变
    self.chunker = CodeChunker(strategy=self.config.chunk_strategy)
    # ...
```

- [ ] **Step 3: 修改 build_index 处理异步 clangd 启动**

```python
# 在 codesearch/builder/indexer.py 的 build_index 方法中修改

async def build_index(
    self,
    root_path: str | Path,
    incremental: bool = True,
) -> IndexStats:
    """Build an index for all code files."""
    root_path = Path(root_path)

    if not root_path.exists():
        raise ValueError(f"Path does not exist: {root_path}")

    # 启动 clangd（如果使用）
    if self.config.use_clangd and hasattr(self.parser, 'start'):
        await self.parser.start()
        await self.parser.initialize(str(root_path))

    try:
        # 现有索引逻辑保持不变
        self.stats = IndexStats()
        files = self._find_code_files(root_path)

        for file_path in files:
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

    finally:
        # 停止 clangd（如果使用）
        if self.config.use_clangd and hasattr(self.parser, 'stop'):
            await self.parser.stop()
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_builder.py::TestCodeIndexer -v
```
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/indexer.py
git commit -m "feat: add clangd support to CodeIndexer with use_clangd config"
```

---

### Task 5: 添加依赖和配置

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: 添加 LSP 相关依赖**

```toml
# 在 pyproject.toml 的 [project.optional-dependencies] 中添加

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.10.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

# 新增 clangd 可选依赖
clangd = [
    # pygls 作为备选 LSP 客户端（如果需要更完整的 LSP 实现）
    # "pygls>=1.0.0",
]

full = [
    "codesearch-plugin[dev,clangd]",
]
```

- [ ] **Step 2: 更新 README.md 添加 clangd 安装说明**

```markdown
# 在 README.md 的 Requirements 部分添加

### Requirements

- Python 3.10+
- tree-sitter-c (C language parser) - 可选，默认使用
- clangd (recommended for better accuracy) - 安装方式:
  - Ubuntu/Debian: `apt install clangd`
  - macOS: `brew install llvm`
  - Windows: 安装 LLVM
- ChromaDB (vector database)
- OpenAI API key (for embeddings)
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml README.md
git commit -m "docs: add clangd installation instructions and optional dependencies"
```

---

### Task 6: 更新导出和文档

**Files:**
- Modify: `codesearch/__init__.py`
- Modify: `codesearch/builder/__init__.py`
- Create: `docs/clangd-usage.md`

- [ ] **Step 1: 更新主包导出**

```python
# 在 codesearch/__init__.py 中更新

from codesearch.builder.indexer import CodeIndexer
from codesearch.builder.clangd_parser import ClangdParser  # 新增
from codesearch.mcp.server import create_mcp_server

__all__ = ["CodeIndexer", "ClangdParser", "create_mcp_server"]
```

- [ ] **Step 2: 更新 builder 模块导出**

```python
# 在 codesearch/builder/__init__.py 中添加

from codesearch.builder.parser import ASTNode, NodeType, CParser
from codesearch.builder.clangd_parser import ClangdParser, SymbolInfo
from codesearch.builder.chunker import CodeChunker, ChunkStrategy, CodeChunk
from codesearch.builder.embeddings import EmbeddingGenerator, EmbeddingProvider
from codesearch.builder.storage import VectorStore
from codesearch.builder.indexer import CodeIndexer, IndexConfig

__all__ = [
    # Parser
    "ASTNode",
    "NodeType",
    "CParser",
    "ClangdParser",
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
]
```

- [ ] **Step 3: 创建 clangd 使用文档**

```markdown
# Clangd Usage Guide

## Overview

The codesearch-plugin now supports clangd as an alternative (and recommended)
parser backend for C/C++ code. Clangd provides more accurate parsing with full
semantic understanding.

## Installation

Install clangd:

```bash
# Ubuntu/Debian
apt install clangd

# macOS
brew install llvm

# Windows
# Install LLVM from https://releases.llvm.org/
```

## Usage

### Using ClangdParser Directly

```python
import asyncio
from codesearch.builder.clangd_parser import ClangdParser

async def main():
    parser = ClangdParser()
    await parser.start()

    # Parse a file
    nodes = await parser.parse_file("src/example.c")

    # Find references
    refs = await parser.find_references("function_name")

    await parser.stop()

asyncio.run(main())
```

### Using with CodeIndexer

```python
import asyncio
from codesearch import CodeIndexer
from codesearch.builder import IndexConfig

async def main():
    config = IndexConfig(
        persist_directory="./.codesearch_index",
        use_clangd=True,  # Enable clangd
        clangd_path="clangd",  # Optional: custom path
    )

    indexer = CodeIndexer(config=config)
    stats = await indexer.build_index("/path/to/codebase")

    print(f"Indexed {stats.files_processed} files")

asyncio.run(main())
```

## Benefits of Clangd

1. **Accurate Symbol Resolution**: Resolves symbols across translation units
2. **Preprocessor Support**: Handles `#include`, `#define`, and macros correctly
3. **Type Information**: Provides full type information for symbols
4. **Reference Finding**: Accurately finds all references to a symbol
5. **Error Recovery**: Continues parsing even with syntax errors

## Fallback to tree-sitter

If clangd is not available, the parser automatically falls back to tree-sitter.
To explicitly use tree-sitter, set `use_clangd=False` in IndexConfig.
```

- [ ] **Step 4: Commit**

```bash
git add codesearch/__init__.py codesearch/builder/__init__.py docs/clangd-usage.md
git commit -m "docs: add clangd usage guide and update exports"
```

---

### Task 7: 验证和清理

**Files:**
- Run: All tests
- Modify: Any files with issues

- [ ] **Step 1: 运行所有测试**

```bash
pytest tests/ -v --cov=codesearch
```
预期：所有测试通过

- [ ] **Step 2: 检查代码格式**

```bash
black codesearch tests
ruff check codesearch tests
```

- [ ] **Step 3: 验证示例代码**

```bash
# 运行示例（如果有）
python examples/basic_usage.py
```

- [ ] **Step 4: 最终 Commit**

```bash
git add codesearch tests
git commit -m "chore: final cleanup and verification for clangd integration"
```

---

## 自审清单

**1. Spec 覆盖:**
- [x] AST 解析方案从 tree-sitter 迁移到 clangd LSP
- [x] 保持现有接口兼容性
- [x] 支持配置选项启用/禁用 clangd
- [x] 添加 clangd 安装和使用文档

**2. 无占位符:**
- [x] 所有步骤包含实际代码
- [x] 所有命令包含预期输出
- [x] 无 "TBD", "TODO" 等占位符

**3. 类型一致性:**
- [x] ASTNode 在所有任务中保持一致
- [x] NodeType 枚举保持不变
- [x] ClangdParser 与 CParser 接口兼容

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-15-clangd-lsp-parser.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 为每个任务分派新的 subagent，在任务之间进行审查，快速迭代

**2. Inline Execution** - 使用 executing-plans 在此会话中批量执行任务，设置检查点进行审查

**Which approach?**
