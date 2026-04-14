"""
Language parsers using tree-sitter for AST extraction.

This module provides parsers for different languages using tree-sitter.
Currently supports C, with extensibility for other languages.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import tree_sitter_c as tsc
from tree_sitter import Parser, Tree, Node, Language


class NodeType(Enum):
    """Types of code structures we track."""

    FUNCTION = "function"
    CLASS = "class"
    STRUCT = "struct"
    UNION = "union"
    ENUM = "enum"
    TYPEDEF = "typedef"
    MACRO = "macro"
    VARIABLE = "variable"
    COMMENT = "comment"
    INCLUDE = "include"
    BLOCK = "block"


@dataclass
class ASTNode:
    """Represents a node in the AST with semantic information."""

    node_type: NodeType
    name: str
    code: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    children: list["ASTNode"] = field(default_factory=list)
    parent: Optional["ASTNode"] = None
    file_path: str = ""
    docstring: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "node_type": self.node_type.value,
            "name": self.name,
            "code": self.code,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_column": self.start_column,
            "end_column": self.end_column,
            "children": [child.to_dict() for child in self.children],
            "file_path": self.file_path,
            "docstring": self.docstring,
        }


class CParser:
    """Parser for C language using tree-sitter."""

    # Node type mappings for tree traversal
    NODE_TYPE_MAP = {
        "function_definition": NodeType.FUNCTION,
        "struct_specifier": NodeType.STRUCT,
        "union_specifier": NodeType.UNION,
        "enum_specifier": NodeType.ENUM,
        "type_definition": NodeType.TYPEDEF,
        "preproc_def": NodeType.MACRO,
        "preproc_include": NodeType.INCLUDE,
        "declaration": NodeType.VARIABLE,
        "comment": NodeType.COMMENT,
    }

    def __init__(self):
        """Initialize the C parser with tree-sitter language."""
        self.language = Language(tsc.language())
        self.parser = Parser(self.language)

    def parse_file(self, file_path: str | Path) -> Tree:
        """Parse a C source file and return the AST tree."""
        file_path = Path(file_path)
        with open(file_path, "rb") as f:
            source = f.read()
        return self.parser.parse(source)

    def parse_string(self, source: str) -> Tree:
        """Parse a C source string and return the AST tree."""
        return self.parser.parse(source.encode())

    def extract_nodes(
        self, tree: Tree, source: bytes, file_path: str = ""
    ) -> list[ASTNode]:
        """Extract semantic nodes from the parsed tree."""
        nodes = []
        root_node = tree.root_node

        # Track seen nodes to avoid duplicates
        seen_nodes: set[int] = set()

        def walk(node: Node) -> None:
            """Walk the AST and extract nodes."""
            node_id = id(node)
            if node_id in seen_nodes:
                return
            seen_nodes.add(node_id)

            # Check if this node type should be extracted
            node_type = self._get_node_type_from_tree(node.type)

            if node_type is not None:
                # Get the code for this node
                start_byte = node.start_byte
                end_byte = node.end_byte
                code = source[start_byte:end_byte].decode("utf-8", errors="ignore")

                # Get the name
                name = self._get_node_name_from_tree(node, source)

                # Create AST node
                ast_node = ASTNode(
                    node_type=node_type,
                    name=name,
                    code=code,
                    start_line=node.start_point[0] + 1,  # 1-indexed
                    end_line=node.end_point[0] + 1,
                    start_column=node.start_point[1],
                    end_column=node.end_point[1],
                    file_path=file_path,
                )

                # Extract docstring (comment before the node)
                ast_node.docstring = self._extract_docstring(node, source)

                nodes.append(ast_node)

            # Recurse into children
            for child in node.children:
                walk(child)

        walk(root_node)
        return nodes

    def _get_node_type_from_tree(self, node_type: str) -> Optional[NodeType]:
        """Map tree-sitter node type to NodeType."""
        return self.NODE_TYPE_MAP.get(node_type)

    def _get_node_name_from_tree(self, node: Node, source: bytes) -> str:
        """Extract the name of a node based on its type."""
        node_type = node.type

        if node_type == "function_definition":
            # Navigate through declarators to find the function name
            # function_definition -> pointer_declarator -> function_declarator -> identifier
            declarator = node.child_by_field_name("declarator")
            while declarator:
                # Check if this declarator has an identifier child
                for child in declarator.children:
                    if child.type == "identifier":
                        return child.text.decode("utf-8", errors="ignore")
                # Go deeper into the declarator chain
                next_decl = declarator.child_by_field_name("declarator")
                if not next_decl:
                    next_decl = declarator.child_by_field_name("function_declarator")
                declarator = next_decl

        elif node_type in ("struct_specifier", "union_specifier", "enum_specifier"):
            # Look for type_identifier
            for child in node.children:
                if child.type == "type_identifier":
                    return child.text.decode("utf-8", errors="ignore")
            # Anonymous struct/union/enum - use a generated name
            return f"anonymous_{node_type}"

        elif node_type == "type_definition":
            # For typedef, look for the type identifier being defined
            # typedef struct { ... } Name;
            # The name comes after the body
            for child in node.children:
                if child.type == "type_identifier":
                    return child.text.decode("utf-8", errors="ignore")
                elif child.type == "primitive_type":
                    return child.text.decode("utf-8", errors="ignore")
            # Check for identifier after the type (typedef alias)
            for child in node.children:
                if child.type == "type_descriptor":
                    # Look for identifier after the type descriptor
                    prev = child
                    while prev.next_sibling:
                        prev = prev.next_sibling
                        if prev.type == "identifier":
                            return prev.text.decode("utf-8", errors="ignore")

        elif node_type == "preproc_def":
            # Look for identifier in #define
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8", errors="ignore")

        elif node_type == "preproc_include":
            # Look for string_literal in #include
            for child in node.children:
                if child.type == "string_literal":
                    return child.text.decode("utf-8", errors="ignore").strip('"')

        elif node_type == "declaration":
            # Look for identifier in declaration
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8", errors="ignore")

        # Default: use the node text
        return node.text.decode("utf-8", errors="ignore")[:50]

    def _extract_docstring(self, node: Node, source: bytes) -> Optional[str]:
        """Extract comment/docstring before a node."""
        prev_sibling = node.prev_sibling
        if prev_sibling and prev_sibling.type == "comment":
            comment = prev_sibling.text.decode("utf-8", errors="ignore")
            # Strip comment markers
            comment = comment.strip()
            if comment.startswith("/*"):
                comment = comment[2:-2].strip() if comment.endswith("*/") else comment[2:].strip()
                # Handle multi-line comments
                lines = []
                for line in comment.split("\n"):
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    lines.append(line)
                return "\n".join(lines)
            elif comment.startswith("//"):
                return comment[2:].strip()
        return None

    def get_function_at_line(self, tree: Tree, line: int, source: bytes) -> Optional[ASTNode]:
        """Find the function containing the given line number."""
        root_node = tree.root_node

        def find_function(node: Node) -> Optional[ASTNode]:
            if node.type == "function_definition":
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                if start_line <= line <= end_line:
                    # Extract the function name
                    declarator = node.child_by_field_name("declarator")
                    name_node = None
                    if declarator:
                        name_node = declarator.child_by_field_name("declarator")

                    name = name_node.text.decode("utf-8", errors="ignore") if name_node else "unknown"

                    return ASTNode(
                        node_type=NodeType.FUNCTION,
                        name=name,
                        code=source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore"),
                        start_line=start_line,
                        end_line=end_line,
                        start_column=node.start_point[1],
                        end_column=node.end_point[1],
                        children=[],
                    )

            # Recurse into children
            for child in node.children:
                result = find_function(child)
                if result:
                    return result
            return None

        return find_function(root_node)
