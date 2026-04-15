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
    kind: int  # LSP SymbolKind
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
    # See https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#symbolKind
    SYMBOL_KIND_MAP = {
        12: NodeType.FUNCTION,      # SymbolKind.Function
        5: NodeType.FUNCTION,       # SymbolKind.Method
        2: NodeType.CLASS,          # SymbolKind.Class
        22: NodeType.STRUCT,        # SymbolKind.Struct
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
        self._client = LSPClient(clangd_path=self.clangd_path)
        await self._client.start_server()

    async def stop(self) -> None:
        """Stop the clangd server."""
        if self._client:
            await self._client.stop_server()
            self._client = None

    async def initialize(self, root_path: str) -> None:
        """Initialize the clangd server with project root."""
        if self._client:
            self._root_path = str(Path(root_path).absolute())
            await self._client.initialize(self._root_path)
            # Send initialized notification after initialize
            await self._client.send_notification("initialized", {})

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

        # Initialize with root path if provided, otherwise use temp dir
        if not self._root_path:
            init_path = root_path or str(Path(file_path).parent)
            await self.initialize(init_path)

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

        await self._client.send_notification(
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
