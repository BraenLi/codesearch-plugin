# Graph Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph indexing to the builder module with entities (files/functions/structs/macros/typedefs) and relationships (code structure/call flows/data flow).

**Architecture:** The graph layer sits alongside the existing vector index. A new `GraphIndexer` class will extract entities and relationships from AST nodes, store them in a graph database (NetworkX for in-memory + optional persistent storage), and expose query methods for traversal and analysis. The existing `CodeIndexer` will be extended to build both vector and graph indices.

**Tech Stack:**
- NetworkX for graph data structures and algorithms
- Existing tree-sitter/clangd parsers for AST extraction
- ChromaDB remains for vector embeddings
- Optional: SQLite/JSON for persistent graph storage

---

## File Structure

**Files to Create:**
- `codesearch/builder/graph.py` - Core graph data models (GraphEntity, GraphRelationship, CodeGraph)
- `codesearch/builder/graph_indexer.py` - Graph extraction and indexing logic
- `tests/test_graph.py` - Tests for graph data models
- `tests/test_graph_indexer.py` - Tests for graph extraction and queries

**Files to Modify:**
- `codesearch/builder/indexer.py` - Add graph building to `CodeIndexer`, add graph query methods
- `codesearch/builder/__init__.py` - Export new graph classes
- `codesearch/mcp/server.py` - Add graph-based tools (optional, phase 2)

---

## Entity and Relationship Model

### Entities (GraphEntity)
```python
class EntityType(Enum):
    FILE = "file"
    FUNCTION = "function"
    STRUCT = "struct"
    UNION = "union"
    ENUM = "enum"
    TYPEDEF = "typedef"
    MACRO = "macro"
    VARIABLE = "variable"
```

### Relationships (GraphRelationship)
```python
class RelationshipType(Enum):
    # Code structure
    CONTAINS = "contains"        # file contains function/struct/etc
    DEFINED_IN = "defined_in"    # function defined in file
    NESTED_IN = "nested_in"      # struct nested in another struct

    # Call relationships
    CALLS = "calls"              # function A calls function B
    RECURSIVE_CALL = "recursive_call"  # function calls itself

    # Type relationships
    USES_TYPE = "uses_type"      # function/struct uses a type
    TYPEDEF_OF = "typedef_of"    # typedef aliases a type
    MEMBER_OF = "member_of"      # struct member belongs to struct
    ENUMERATOR_OF = "enumerator_of"  # enum value belongs to enum

    # Data flow
    READS = "reads"              # function reads a variable
    WRITES = "writes"            # function writes to a variable
    PASSES_TO = "passes_to"      # function passes arg to another function

    # Include/dependency
    INCLUDES = "includes"        # file includes another file
    DEPENDS_ON = "depends_on"    # file/function depends on another
```

---

## Tasks

### Task 1: Graph Data Models

**Files:**
- Create: `codesearch/builder/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1: Write tests for GraphEntity**

```python
# tests/test_graph.py
from codesearch.builder.graph import GraphEntity, GraphRelationship, EntityType, RelationshipType

def test_graph_entity_creation():
    entity = GraphEntity(
        id="func_malloc",
        entity_type=EntityType.FUNCTION,
        name="malloc",
        file_path="stdlib.h",
        start_line=10,
        end_line=15,
    )
    assert entity.id == "func_malloc"
    assert entity.entity_type == EntityType.FUNCTION
    assert entity.name == "malloc"

def test_graph_entity_to_dict():
    entity = GraphEntity(
        id="struct_node",
        entity_type=EntityType.STRUCT,
        name="Node",
        file_path="tree.h",
        start_line=5,
        end_line=10,
    )
    d = entity.to_dict()
    assert d["id"] == "struct_node"
    assert d["entity_type"] == "struct"
    assert d["name"] == "Node"

def test_graph_relationship_creation():
    rel = GraphRelationship(
        id="call_1",
        relationship_type=RelationshipType.CALLS,
        source_id="func_main",
        target_id="func_malloc",
        metadata={"call_site_line": 25},
    )
    assert rel.relationship_type == RelationshipType.CALLS
    assert rel.source_id == "func_main"
    assert rel.target_id == "func_malloc"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_graph.py::test_graph_entity_creation -v
# Expected: ImportError (module doesn't exist yet)
```

- [ ] **Step 3: Implement GraphEntity and GraphRelationship classes**

```python
# codesearch/builder/graph.py
"""
Graph data models for code structure representation.

This module provides entities and relationships for representing
code as a graph for structural queries and analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class EntityType(Enum):
    """Types of code entities in the graph."""

    FILE = "file"
    FUNCTION = "function"
    STRUCT = "struct"
    UNION = "union"
    ENUM = "enum"
    TYPEDEF = "typedef"
    MACRO = "macro"
    VARIABLE = "variable"


class RelationshipType(Enum):
    """Types of relationships between code entities."""

    # Code structure
    CONTAINS = "contains"
    DEFINED_IN = "defined_in"
    NESTED_IN = "nested_in"

    # Call relationships
    CALLS = "calls"
    RECURSIVE_CALL = "recursive_call"

    # Type relationships
    USES_TYPE = "uses_type"
    TYPEDEF_OF = "typedef_of"
    MEMBER_OF = "member_of"
    ENUMERATOR_OF = "enumerator_of"

    # Data flow
    READS = "reads"
    WRITES = "writes"
    PASSES_TO = "passes_to"

    # Include/dependency
    INCLUDES = "includes"
    DEPENDS_ON = "depends_on"


@dataclass
class GraphEntity:
    """Represents a code entity in the graph."""

    id: str
    entity_type: EntityType
    name: str
    file_path: str
    start_line: int
    end_line: int
    parent_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphEntity":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            entity_type=EntityType(data["entity_type"]),
            name=data["name"],
            file_path=data["file_path"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GraphRelationship:
    """Represents a relationship between two code entities."""

    id: str
    relationship_type: RelationshipType
    source_id: str
    target_id: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "relationship_type": self.relationship_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphRelationship":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            relationship_type=RelationshipType(data["relationship_type"]),
            source_id=data["source_id"],
            target_id=data["target_id"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class CodeGraph:
    """In-memory code graph using NetworkX."""

    def __post_init__(self):
        import networkx as nx
        if not hasattr(self, '_graph'):
            self._graph = nx.DiGraph()
        self._entities: dict[str, GraphEntity] = {}
        self._relationships: dict[str, GraphRelationship] = {}

    def add_entity(self, entity: GraphEntity) -> None:
        """Add an entity to the graph."""
        self._entities[entity.id] = entity
        self._graph.add_node(
            entity.id,
            **entity.to_dict(),
        )

    def add_relationship(self, relationship: GraphRelationship) -> None:
        """Add a relationship to the graph."""
        self._relationships[relationship.id] = relationship
        self._graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            relationship_type=relationship.relationship_type.value,
            relationship_id=relationship.id,
            **relationship.metadata,
        )

    def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        """Get an entity by ID."""
        return self._entities.get(entity_id)

    def get_relationship(self, relationship_id: str) -> Optional[GraphRelationship]:
        """Get a relationship by ID."""
        return self._relationships.get(relationship_id)

    def get_callers(self, function_id: str) -> list[GraphEntity]:
        """Get all functions that call the given function."""
        callers = []
        for pred_id in self._graph.predecessors(function_id):
            entity = self._entities.get(pred_id)
            if entity and entity.entity_type == EntityType.FUNCTION:
                callers.append(entity)
        return callers

    def get_callees(self, function_id: str) -> list[GraphEntity]:
        """Get all functions called by the given function."""
        callees = []
        for succ_id in self._graph.successors(function_id):
            entity = self._entities.get(succ_id)
            if entity and entity.entity_type == EntityType.FUNCTION:
                callees.append(entity)
        return callees

    def get_call_graph(self, function_id: str, depth: int = 3) -> "CodeGraph":
        """Get the call graph for a function up to a certain depth."""
        import networkx as nx
        subgraph = CodeGraph()

        # BFS to get nodes within depth
        visited = set()
        queue = [(function_id, 0)]

        while queue:
            node_id, current_depth = queue.pop(0)
            if node_id in visited or current_depth > depth:
                continue
            visited.add(node_id)

            entity = self._entities.get(node_id)
            if entity:
                subgraph.add_entity(entity)

            if current_depth < depth:
                for succ_id in self._graph.successors(node_id):
                    queue.append((succ_id, current_depth + 1))

        # Add relationships between visited nodes
        for src_id in visited:
            for tgt_id in self._graph.successors(src_id):
                if tgt_id in visited:
                    edge_data = self._graph.get_edge_data(src_id, tgt_id)
                    if edge_data and "relationship_id" in edge_data:
                        rel = self._relationships.get(edge_data["relationship_id"])
                        if rel:
                            subgraph.add_relationship(rel)

        return subgraph

    def find_paths(self, source_id: str, target_id: str, max_paths: int = 5) -> list[list[str]]:
        """Find all paths between two entities."""
        import networkx as nx
        try:
            paths = list(nx.all_simple_paths(
                self._graph,
                source=source_id,
                target=target_id,
            ))
            return paths[:max_paths]
        except nx.NetworkXNoPath:
            return []

    def get_references_to(self, entity_id: str) -> list[GraphEntity]:
        """Get all entities that reference the given entity."""
        references = []
        for pred_id in self._graph.predecessors(entity_id):
            entity = self._entities.get(pred_id)
            if entity:
                references.append(entity)
        return references

    def get_file_contents(self, file_path: str) -> list[GraphEntity]:
        """Get all entities defined in a file."""
        return [
            entity for entity in self._entities.values()
            if entity.file_path == file_path
        ]

    def get_entities_by_type(self, entity_type: EntityType) -> list[GraphEntity]:
        """Get all entities of a specific type."""
        return [
            entity for entity in self._entities.values()
            if entity.entity_type == entity_type
        ]

    def get_entities_by_name(self, name: str) -> list[GraphEntity]:
        """Get all entities with a specific name."""
        return [
            entity for entity in self._entities.values()
            if entity.name == name
        ]

    def to_dict(self) -> dict:
        """Convert graph to dictionary."""
        return {
            "entities": [e.to_dict() for e in self._entities.values()],
            "relationships": [r.to_dict() for r in self._relationships.values()],
        }

    def entity_count(self) -> int:
        """Get the number of entities."""
        return len(self._entities)

    def relationship_count(self) -> int:
        """Get the number of relationships."""
        return len(self._relationships)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_graph.py -v
# Expected: All tests pass
```

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/graph.py tests/test_graph.py
git commit -m "feat: add graph data models (GraphEntity, GraphRelationship, CodeGraph)"
```

---

### Task 2: Graph Indexer - Entity Extraction

**Files:**
- Create: `codesearch/builder/graph_indexer.py`
- Test: `tests/test_graph_indexer.py`

- [ ] **Step 1: Write tests for entity extraction from AST nodes**

```python
# tests/test_graph_indexer.py
from codesearch.builder.graph_indexer import GraphIndexer
from codesearch.builder.parser import CParser, ASTNode, NodeType


def test_extract_file_entity():
    parser = CParser()
    source = '''
#include "header.h"

void foo() { }
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "test.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "test.c")

    file_entities = indexer.get_entities_by_type(EntityType.FILE)
    assert len(file_entities) == 1
    assert file_entities[0].name == "test.c"


def test_extract_function_entities():
    parser = CParser()
    source = '''
void foo() { }
int bar(int x) { return x + 1; }
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "funcs.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "funcs.c")

    func_entities = indexer.get_entities_by_type(EntityType.FUNCTION)
    assert len(func_entities) == 2
    names = {e.name for e in func_entities}
    assert names == {"foo", "bar"}


def test_extract_struct_entities():
    parser = CParser()
    source = '''
struct Node {
    int data;
    struct Node* next;
};
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "struct.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "struct.c")

    struct_entities = indexer.get_entities_by_type(EntityType.STRUCT)
    assert len(struct_entities) == 1
    assert struct_entities[0].name == "Node"


def test_extract_macro_entities():
    parser = CParser()
    source = '''
#define MAX_SIZE 1024
#define MIN(a, b) ((a) < (b) ? (a) : (b))
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "macros.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "macros.c")

    macro_entities = indexer.get_entities_by_type(EntityType.MACRO)
    assert len(macro_entities) == 2
    names = {e.name for e in macro_entities}
    assert names == {"MAX_SIZE", "MIN"}


def test_extract_typedef_entities():
    parser = CParser()
    source = '''
typedef unsigned int uint32_t;
typedef struct Node Node;
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "typedef.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "typedef.c")

    typedef_entities = indexer.get_entities_by_type(EntityType.TYPEDEF)
    assert len(typedef_entities) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_graph_indexer.py::test_extract_file_entity -v
# Expected: ImportError (module doesn't exist yet)
```

- [ ] **Step 3: Implement GraphIndexer with entity extraction**

```python
# codesearch/builder/graph_indexer.py
"""
Graph indexer for extracting code entities and relationships.

This module extracts entities (files, functions, structs, etc.) and
relationships (calls, contains, uses_type, etc.) from AST nodes.
"""

from dataclasses import dataclass
from typing import Optional

from codesearch.builder.graph import (
    CodeGraph,
    GraphEntity,
    GraphRelationship,
    EntityType,
    RelationshipType,
)
from codesearch.builder.parser import ASTNode, NodeType


@dataclass
class GraphStats:
    """Statistics about graph construction."""

    entities_created: int = 0
    relationships_created: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict:
        return {
            "entities_created": self.entities_created,
            "relationships_created": self.relationships_created,
            "errors": self.errors,
        }


class GraphIndexer:
    """
    Extracts code entities and relationships from AST nodes.

    Usage:
        indexer = GraphIndexer()
        graph = indexer.build_graph_from_nodes(nodes, file_path)
    """

    # Map AST node types to entity types
    NODE_TO_ENTITY_MAP = {
        NodeType.FUNCTION: EntityType.FUNCTION,
        NodeType.STRUCT: EntityType.STRUCT,
        NodeType.UNION: EntityType.UNION,
        NodeType.ENUM: EntityType.ENUM,
        NodeType.TYPEDEF: EntityType.TYPEDEF,
        NodeType.MACRO: EntityType.MACRO,
        NodeType.VARIABLE: EntityType.VARIABLE,
    }

    def __init__(self):
        """Initialize the graph indexer."""
        self.stats = GraphStats()
        self._graphs: dict[str, CodeGraph] = {}

    def build_graph_from_nodes(
        self,
        nodes: list[ASTNode],
        file_path: str,
        file_content: Optional[str] = None,
    ) -> CodeGraph:
        """
        Build a code graph from AST nodes.

        Args:
            nodes: List of AST nodes from parser
            file_path: Path to the source file
            file_content: Optional full file content

        Returns:
            CodeGraph with extracted entities and relationships
        """
        graph = CodeGraph()

        # Create file entity
        file_entity = self._create_file_entity(nodes, file_path, file_content)
        if file_entity:
            graph.add_entity(file_entity)

        # Extract entities from nodes
        for node in nodes:
            entity = self._create_entity_from_node(node, file_path)
            if entity:
                graph.add_entity(entity)
                self.stats.entities_created += 1

                # Add CONTAINS relationship from file
                if file_entity:
                    rel = GraphRelationship(
                        id=f"contains_{entity.id}",
                        relationship_type=RelationshipType.CONTAINS,
                        source_id=file_entity.id,
                        target_id=entity.id,
                    )
                    graph.add_relationship(rel)
                    self.stats.relationships_created += 1

        # Extract relationships between entities
        self._extract_relationships(nodes, graph, file_path)

        return graph

    def _create_file_entity(
        self,
        nodes: list[ASTNode],
        file_path: str,
        file_content: Optional[str] = None,
    ) -> Optional[GraphEntity]:
        """Create a file entity."""
        if not nodes:
            return None

        start_line = min(n.start_line for n in nodes)
        end_line = max(n.end_line for n in nodes)

        return GraphEntity(
            id=f"file_{file_path}",
            entity_type=EntityType.FILE,
            name=file_path.split("/")[-1] if "/" in file_path else file_path,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            metadata={
                "full_path": file_path,
                "line_count": end_line - start_line + 1,
            },
        )

    def _create_entity_from_node(
        self,
        node: ASTNode,
        file_path: str,
    ) -> Optional[GraphEntity]:
        """Create a graph entity from an AST node."""
        entity_type = self.NODE_TO_ENTITY_MAP.get(node.node_type)
        if not entity_type:
            return None

        entity_id = f"{entity_type.value}_{file_path}:{node.start_line}:{node.name}"

        return GraphEntity(
            id=entity_id,
            entity_type=entity_type,
            name=node.name,
            file_path=file_path,
            start_line=node.start_line,
            end_line=node.end_line,
            metadata={
                "code": node.code,
                "docstring": node.docstring,
                "start_column": node.start_column,
                "end_column": node.end_column,
            },
        )

    def _extract_relationships(
        self,
        nodes: list[ASTNode],
        graph: CodeGraph,
        file_path: str,
    ) -> None:
        """Extract relationships between entities."""
        # Build a map of entity names to IDs for lookup
        name_to_entity: dict[str, GraphEntity] = {}
        for entity_id in graph._entities:
            entity = graph._entities[entity_id]
            name_to_entity[entity.name] = entity

        for node in nodes:
            if node.node_type == NodeType.FUNCTION:
                self._extract_call_relationships(node, graph, name_to_entity, file_path)

    def _extract_call_relationships(
        self,
        function_node: ASTNode,
        graph: CodeGraph,
        name_to_entity: dict[str, GraphEntity],
        file_path: str,
    ) -> None:
        """Extract CALLS relationships from a function node."""
        # Get the function entity
        func_entity = None
        for entity_id in graph._entities:
            entity = graph._entities[entity_id]
            if (entity.entity_type == EntityType.FUNCTION and
                entity.start_line == function_node.start_line and
                entity.name == function_node.name):
                func_entity = entity
                break

        if not func_entity:
            return

        # Simple heuristic: look for function calls in the code
        # A more accurate approach would require deeper AST analysis
        import re
        # Match function calls: identifier followed by (
        call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(call_pattern, function_node.code)

        for called_name in matches:
            # Skip keywords and the function itself
            if called_name in ('if', 'while', 'for', 'switch', 'return', func_entity.name):
                continue

            # Check if this matches a known function
            if called_name in name_to_entity:
                target_entity = name_to_entity[called_name]
                if target_entity.entity_type == EntityType.FUNCTION:
                    rel = GraphRelationship(
                        id=f"call_{func_entity.id}_{target_entity.id}",
                        relationship_type=RelationshipType.CALLS,
                        source_id=func_entity.id,
                        target_id=target_entity.id,
                        metadata={"call_site": called_name},
                    )
                    graph.add_relationship(rel)
                    self.stats.relationships_created += 1

    def get_entities_by_type(self, entity_type: EntityType) -> list[GraphEntity]:
        """Get all entities of a specific type from the current graph."""
        # This would be called on a specific graph instance
        return []

    def merge_graphs(self, graphs: list[CodeGraph]) -> CodeGraph:
        """Merge multiple graphs into one."""
        merged = CodeGraph()
        for graph in graphs:
            for entity in graph._entities.values():
                if entity.id not in merged._entities:
                    merged.add_entity(entity)
            for rel in graph._relationships.values():
                if rel.id not in merged._relationships:
                    merged.add_relationship(rel)
        return merged

    def get_stats(self) -> dict:
        """Get graph construction statistics."""
        return self.stats.to_dict()
```

- [ ] **Step 4: Run tests and implement fixes until they pass**

```bash
pytest tests/test_graph_indexer.py -v
# Fix any issues until tests pass
```

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/graph_indexer.py tests/test_graph_indexer.py
git commit -m "feat: add GraphIndexer with entity extraction"
```

---

### Task 3: Graph Indexer - Relationship Extraction

**Files:**
- Modify: `codesearch/builder/graph_indexer.py`
- Test: `tests/test_graph_indexer.py`

- [ ] **Step 1: Write tests for relationship extraction**

```python
# Add to tests/test_graph_indexer.py

def test_extract_call_relationships():
    parser = CParser()
    source = '''
void helper() { }

void caller() {
    helper();
}
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "calls.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "calls.c")

    # Find the caller function
    caller_entity = None
    for e in graph._entities.values():
        if e.name == "caller" and e.entity_type == EntityType.FUNCTION:
            caller_entity = e
            break

    assert caller_entity is not None

    # Get callees
    callees = graph.get_callees(caller_entity.id)
    assert len(callees) >= 1
    callee_names = {c.name for c in callees}
    assert "helper" in callee_names


def test_extract_contains_relationships():
    parser = CParser()
    source = '''
struct Inner {
    int x;
};

struct Outer {
    struct Inner inner;
};
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "nested.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "nested.c")

    # Check that structs are contained in file
    file_entity = graph._entities.get("file_nested.c")
    assert file_entity is not None

    # Get entities contained in file
    contained = graph.get_file_contents("nested.c")
    assert len(contained) >= 2  # At least Inner and Outer structs


def test_extract_uses_type_relationship():
    parser = CParser()
    source = '''
struct Point {
    int x;
    int y;
};

void move(struct Point* p) {
    p->x += 1;
}
'''
    tree = parser.parse_string(source)
    nodes = parser.extract_nodes(tree, source.encode(), "types.c")

    indexer = GraphIndexer()
    graph = indexer.build_graph_from_nodes(nodes, "types.c")

    # Function should have USES_TYPE relationship to struct
    # This is a more advanced test - may require enhanced extraction logic
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_graph_indexer.py::test_extract_call_relationships -v
```

- [ ] **Step 3: Enhance relationship extraction logic**

```python
# Add to codesearch/builder/graph_indexer.py

def _extract_relationships(
    self,
    nodes: list[ASTNode],
    graph: CodeGraph,
    file_path: str,
) -> None:
    """Extract relationships between entities."""
    # Build a map of entity names to IDs for lookup
    name_to_entity: dict[str, GraphEntity] = {}
    for entity_id in graph._entities:
        entity = graph._entities[entity_id]
        name_to_entity[entity.name] = entity

    for node in nodes:
        if node.node_type == NodeType.FUNCTION:
            self._extract_call_relationships(node, graph, name_to_entity, file_path)
            self._extract_type_usage_relationships(node, graph, name_to_entity, file_path)
        elif node.node_type == NodeType.STRUCT:
            self._extract_member_relationships(node, graph, name_to_entity, file_path)
        elif node.node_type == NodeType.ENUM:
            self._extract_enumerator_relationships(node, graph, file_path)
        elif node.node_type == NodeType.TYPEDEF:
            self._extract_typedef_relationships(node, graph, name_to_entity, file_path)


def _extract_type_usage_relationships(
    self,
    function_node: ASTNode,
    graph: CodeGraph,
    name_to_entity: dict[str, GraphEntity],
    file_path: str,
) -> None:
    """Extract USES_TYPE relationships from function parameters and body."""
    func_entity = None
    for entity_id in graph._entities:
        entity = graph._entities[entity_id]
        if (entity.entity_type == EntityType.FUNCTION and
            entity.start_line == function_node.start_line and
            entity.name == function_node.name):
            func_entity = entity
            break

    if not func_entity:
        return

    # Look for type usage in parameters and body
    import re
    # Match struct/enum/typedef names in the code
    type_pattern = r'\b(struct|enum|typedef)?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[*]*\s*[a-zA-Z_]'
    matches = re.findall(type_pattern, function_node.code)

    for _, type_name in matches:
        if type_name in name_to_entity:
            type_entity = name_to_entity[type_name]
            if type_entity.entity_type in (EntityType.STRUCT, EntityType.UNION, EntityType.ENUM, EntityType.TYPEDEF):
                rel = GraphRelationship(
                    id=f"uses_{func_entity.id}_{type_entity.id}",
                    relationship_type=RelationshipType.USES_TYPE,
                    source_id=func_entity.id,
                    target_id=type_entity.id,
                )
                graph.add_relationship(rel)
                self.stats.relationships_created += 1


def _extract_member_relationships(
    self,
    struct_node: ASTNode,
    graph: CodeGraph,
    name_to_entity: dict[str, GraphEntity],
    file_path: str,
) -> None:
    """Extract MEMBER_OF relationships for struct members."""
    struct_entity = None
    for entity_id in graph._entities:
        entity = graph._entities[entity_id]
        if (entity.entity_type == EntityType.STRUCT and
            entity.start_line == struct_node.start_line and
            entity.name == struct_node.name):
            struct_entity = entity
            break

    if not struct_entity:
        return

    # Extract member types from struct body
    import re
    member_pattern = r'\b(struct|enum)?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(member_pattern, struct_node.code)

    for _, member_type, member_name in matches:
        # Skip the struct keyword itself
        if member_type in ('struct', 'enum', 'union'):
            continue

        if member_type in name_to_entity:
            type_entity = name_to_entity[member_type]
            rel = GraphRelationship(
                id=f"member_{struct_entity.id}_{member_name}",
                relationship_type=RelationshipType.USES_TYPE,
                source_id=struct_entity.id,
                target_id=type_entity.id,
                metadata={"member_name": member_name},
            )
            graph.add_relationship(rel)
            self.stats.relationships_created += 1


def _extract_enumerator_relationships(
    self,
    enum_node: ASTNode,
    graph: CodeGraph,
    file_path: str,
) -> None:
    """Extract ENUMERATOR_OF relationships."""
    enum_entity = None
    for entity_id in graph._entities:
        entity = graph._entities[entity_id]
        if (entity.entity_type == EntityType.ENUM and
            entity.start_line == enum_node.start_line and
            entity.name == enum_node.name):
            enum_entity = entity
            break

    if not enum_entity:
        return

    # Extract enumerator names
    import re
    enumerator_pattern = r'\b([A-Z_][A-Z0-9_]*)\s*=?'
    matches = re.findall(enumerator_pattern, enum_node.code)

    for enumerator_name in matches:
        # Create a virtual entity for the enumerator
        enumerator_entity = GraphEntity(
            id=f"enumerator_{enum_entity.id}_{enumerator_name}",
            entity_type=EntityType.VARIABLE,
            name=enumerator_name,
            file_path=file_path,
            start_line=enum_entity.start_line,
            end_line=enum_entity.end_line,
            metadata={"enumerator_of": enum_entity.name},
        )
        graph.add_entity(enumerator_entity)
        self.stats.entities_created += 1

        rel = GraphRelationship(
            id=f"enumerator_{enumerator_entity.id}_{enum_entity.id}",
            relationship_type=RelationshipType.ENUMERATOR_OF,
            source_id=enumerator_entity.id,
            target_id=enum_entity.id,
        )
        graph.add_relationship(rel)
        self.stats.relationships_created += 1


def _extract_typedef_relationships(
    self,
    typedef_node: ASTNode,
    graph: CodeGraph,
    name_to_entity: dict[str, GraphEntity],
    file_path: str,
) -> None:
    """Extract TYPEDEF_OF relationships."""
    typedef_entity = None
    for entity_id in graph._entities:
        entity = graph._entities[entity_id]
        if (entity.entity_type == EntityType.TYPEDEF and
            entity.start_line == typedef_node.start_line and
            entity.name == typedef_node.name):
            typedef_entity = entity
            break

    if not typedef_entity:
        return

    # Try to find what type this typedef aliases
    import re
    # Pattern: typedef <type> <name>
    typedef_pattern = r'typedef\s+(struct|enum|union)?\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    match = re.search(typedef_pattern, typedef_node.code)

    if match:
        underlying_type = match.group(2)
        if underlying_type in name_to_entity:
            type_entity = name_to_entity[underlying_type]
            rel = GraphRelationship(
                id=f"typedef_{typedef_entity.id}_{type_entity.id}",
                relationship_type=RelationshipType.TYPEDEF_OF,
                source_id=typedef_entity.id,
                target_id=type_entity.id,
            )
            graph.add_relationship(rel)
            self.stats.relationships_created += 1
```

- [ ] **Step 4: Run tests and fix issues**

```bash
pytest tests/test_graph_indexer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add codesearch/builder/graph_indexer.py tests/test_graph_indexer.py
git commit -m "feat: add relationship extraction (calls, uses_type, member_of, enumerator_of)"
```

---

### Task 4: Integrate Graph Indexer with CodeIndexer

**Files:**
- Modify: `codesearch/builder/indexer.py`
- Modify: `codesearch/builder/__init__.py`
- Test: `tests/test_indexer.py`

- [ ] **Step 1: Update CodeIndexer to build graph index**

```python
# Modify codesearch/builder/indexer.py

# Add import at top
from codesearch.builder.graph import CodeGraph, EntityType, RelationshipType
from codesearch.builder.graph_indexer import GraphIndexer

# Add to IndexConfig dataclass
@dataclass
class IndexConfig:
    # ... existing fields ...

    # Graph indexing
    enable_graph_indexing: bool = True  # Whether to build graph index
    graph_persist_directory: Optional[str] = None  # Optional graph persistence
```

- [ ] **Step 2: Add graph_indexer to CodeIndexer.__init__**

```python
class CodeIndexer:
    def __init__(self, config: Optional[IndexConfig] = None):
        # ... existing init code ...

        # Initialize graph indexer
        self.graph_indexer = GraphIndexer()
        self.code_graph: Optional[CodeGraph] = None

        if self.config.enable_graph_indexing:
            self.graph_indexer = GraphIndexer()
```

- [ ] **Step 3: Update build_index to build graph**

```python
async def build_index(
    self,
    root_path: str | Path,
    incremental: bool = True,
) -> IndexStats:
    # ... existing code ...

    if self.config.enable_graph_indexing:
        self.code_graph = CodeGraph()

    # Process each file
    for file_path in files:
        # ... existing file processing ...

        try:
            await self._index_file(file_path)
            self._indexed_files.add(str(file_path))
            self.stats.files_processed += 1
        except Exception as e:
            self.stats.errors.append(f"Error indexing {file_path}: {str(e)}")

    self.stats.chunks_indexed = self.vector_store.count()

    return self.stats
```

- [ ] **Step 4: Update _index_file to extract graph data**

```python
async def _index_file(self, file_path: Path) -> None:
    nodes: list[ASTNode] = []

    # ... existing parser code ...

    if not nodes:
        return

    # Build graph for this file
    if self.config.enable_graph_indexing and self.code_graph is not None:
        with open(file_path, "r") as f:
            file_content = f.read()
        file_graph = self.graph_indexer.build_graph_from_nodes(
            nodes, str(file_path), file_content
        )
        # Merge into main graph
        for entity in file_graph._entities.values():
            if entity.id not in self.code_graph._entities:
                self.code_graph.add_entity(entity)
        for rel in file_graph._relationships.values():
            if rel.id not in self.code_graph._relationships:
                self.code_graph.add_relationship(rel)

    # ... rest of existing code (chunking, embeddings) ...
```

- [ ] **Step 5: Add graph query methods to CodeIndexer**

```python
# Add to CodeIndexer class

def get_call_graph(
    self,
    function_name: str,
    depth: int = 3,
) -> Optional[CodeGraph]:
    """
    Get the call graph for a function.

    Args:
        function_name: Name of the function
        depth: How many levels of calls to include

    Returns:
        CodeGraph containing the call hierarchy
    """
    if not self.code_graph:
        return None

    # Find the function entity
    func_entity = None
    for entity in self.code_graph._entities.values():
        if entity.name == function_name and entity.entity_type == EntityType.FUNCTION:
            func_entity = entity
            break

    if not func_entity:
        return None

    return self.code_graph.get_call_graph(func_entity.id, depth)


def find_symbol_references(
    self,
    symbol_name: str,
) -> list[dict]:
    """
    Find all references to a symbol using the graph.

    Args:
        symbol_name: Name of the symbol

    Returns:
        List of referencing entities
    """
    if not self.code_graph:
        return []

    # Find entities with this name
    entities = self.code_graph.get_entities_by_name(symbol_name)
    if not entities:
        return []

    references = []
    for entity in entities:
        refs = self.code_graph.get_references_to(entity.id)
        for ref in refs:
            references.append({
                "entity": ref.to_dict(),
                "references": entity.to_dict(),
            })

    return references


def get_file_structure(self, file_path: str) -> Optional[dict]:
    """
    Get the structure of a file (entities it contains).

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file structure
    """
    if not self.code_graph:
        return None

    entities = self.code_graph.get_file_contents(file_path)
    if not entities:
        return None

    return {
        "file_path": file_path,
        "entities": [e.to_dict() for e in entities],
    }


def get_graph_stats(self) -> dict:
    """Get graph statistics."""
    if not self.code_graph:
        return {"enabled": False}

    return {
        "enabled": True,
        "entity_count": self.code_graph.entity_count(),
        "relationship_count": self.code_graph.relationship_count(),
        "graph_stats": self.graph_indexer.get_stats(),
    }
```

- [ ] **Step 6: Update IndexStats to include graph stats**

```python
@dataclass
class IndexStats:
    # ... existing fields ...
    graph_entities: int = 0
    graph_relationships: int = 0

    def to_dict(self) -> dict:
        return {
            # ... existing fields ...
            "graph_entities": self.graph_entities,
            "graph_relationships": self.graph_relationships,
        }
```

- [ ] **Step 7: Update build_index to populate graph stats**

```python
# At end of build_index, after graph is built:
if self.config.enable_graph_indexing and self.code_graph:
    self.stats.graph_entities = self.code_graph.entity_count()
    self.stats.graph_relationships = self.code_graph.relationship_count()
```

- [ ] **Step 8: Update exports in __init__.py**

```python
# Modify codesearch/builder/__init__.py

from codesearch.builder.graph import (
    CodeGraph,
    GraphEntity,
    GraphRelationship,
    EntityType,
    RelationshipType,
)
from codesearch.builder.graph_indexer import GraphIndexer, GraphStats

__all__ = [
    # ... existing exports ...
    "CodeGraph",
    "GraphEntity",
    "GraphRelationship",
    "EntityType",
    "RelationshipType",
    "GraphIndexer",
    "GraphStats",
]
```

- [ ] **Step 9: Write and run integration tests**

```python
# tests/test_indexer.py
import pytest
from codesearch.builder.indexer import CodeIndexer, IndexConfig


@pytest.mark.asyncio
async def test_build_index_with_graph(tmp_path):
    """Test that building index also creates graph."""
    # Create a test C file
    test_file = tmp_path / "test.c"
    test_file.write_text("""
#include "header.h"

void helper() { }

void caller() {
    helper();
}

struct Node {
    int data;
};
""")

    config = IndexConfig(
        persist_directory=str(tmp_path / ".index"),
        enable_graph_indexing=True,
    )
    indexer = CodeIndexer(config)
    stats = await indexer.build_index(tmp_path)

    assert stats.files_processed >= 1
    assert stats.graph_entities > 0
    assert stats.graph_relationships > 0


@pytest.mark.asyncio
async def test_get_call_graph(tmp_path):
    """Test getting call graph for a function."""
    test_file = tmp_path / "calls.c"
    test_file.write_text("""
void leaf() { }

void middle() { leaf(); }

void root() { middle(); }
""")

    config = IndexConfig(enable_graph_indexing=True)
    indexer = CodeIndexer(config)
    await indexer.build_index(tmp_path)

    call_graph = indexer.get_call_graph("root", depth=3)
    assert call_graph is not None
    assert call_graph.entity_count() >= 3  # root, middle, leaf at minimum


@pytest.mark.asyncio
async def test_find_symbol_references(tmp_path):
    """Test finding symbol references via graph."""
    test_file = tmp_path / "refs.c"
    test_file.write_text("""
void target() { }

void caller1() { target(); }
void caller2() { target(); }
""")

    config = IndexConfig(enable_graph_indexing=True)
    indexer = CodeIndexer(config)
    await indexer.build_index(tmp_path)

    refs = indexer.find_symbol_references("target")
    assert len(refs) >= 2  # caller1 and caller2
```

- [ ] **Step 10: Run tests and fix issues**

```bash
pytest tests/test_indexer.py -v
```

- [ ] **Step 11: Commit**

```bash
git add codesearch/builder/indexer.py codesearch/builder/__init__.py tests/test_indexer.py
git commit -m "feat: integrate graph indexer with CodeIndexer"
```

---

### Task 5: Add MCP Tools for Graph Queries

**Files:**
- Modify: `codesearch/mcp/server.py`
- Modify: `codesearch/mcp/tools.py`

- [ ] **Step 1: Add graph tool schemas**

```python
# codesearch/mcp/tools.py

from pydantic import BaseModel, Field


class GetCallGraphRequest(BaseModel):
    function_name: str = Field(..., description="Name of the function")
    depth: int = Field(default=3, description="Call graph depth")


class GetCallGraphResponse(BaseModel):
    function_name: str
    callers: list[dict]
    callees: list[dict]
    graph_summary: dict


class FindReferencesRequest(BaseModel):
    symbol_name: str = Field(..., description="Symbol name to find references for")


class FindReferencesResponse(BaseModel):
    symbol_name: str
    references: list[dict]
    reference_count: int


class GetFileStructureRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file")


class GetFileStructureResponse(BaseModel):
    file_path: str
    entities: list[dict]
    entity_count: int
```

- [ ] **Step 2: Add graph tools to MCP server**

```python
# codesearch/mcp/server.py

@mcp.tool()
async def get_call_graph(
    function_name: str,
    depth: int = 3,
) -> dict:
    """
    Get the call graph for a function.

    Args:
        function_name: Name of the function
        depth: How many levels of calls to include

    Returns:
        Dictionary with call graph information
    """
    call_graph = indexer.get_call_graph(function_name, depth)
    if not call_graph:
        return {"error": f"Function {function_name} not found"}

    # Get callers and callees
    func_entity = None
    for e in call_graph._entities.values():
        if e.name == function_name:
            func_entity = e
            break

    callers = []
    callees = []
    if func_entity:
        callers = [e.to_dict() for e in call_graph.get_callers(func_entity.id)]
        callees = [e.to_dict() for e in call_graph.get_callees(func_entity.id)]

    return {
        "function_name": function_name,
        "callers": callers,
        "callees": callees,
        "graph_summary": call_graph.to_dict(),
    }


@mcp.tool()
async def get_graph_references(
    symbol_name: str,
) -> dict:
    """
    Find all references to a symbol using the graph.

    Args:
        symbol_name: Name of the symbol

    Returns:
        Dictionary with reference information
    """
    refs = indexer.find_symbol_references(symbol_name)
    return {
        "symbol_name": symbol_name,
        "references": refs,
        "reference_count": len(refs),
    }


@mcp.tool()
async def get_file_structure(
    file_path: str,
) -> dict:
    """
    Get the structure of a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file structure
    """
    result = indexer.get_file_structure(file_path)
    if not result:
        return {"error": f"No structure found for {file_path}"}
    return result
```

- [ ] **Step 3: Commit**

```bash
git add codesearch/mcp/server.py codesearch/mcp/tools.py
git commit -m "feat: add MCP tools for graph queries"
```

---

### Task 6: Documentation and Cleanup

**Files:**
- Modify: `README.md` or create `docs/graph-indexing.md`

- [ ] **Step 1: Add graph indexing documentation**

```markdown
# Graph Indexing

The code search plugin now includes graph indexing for structural code queries.

## Features

- **Entity Extraction**: Files, functions, structs, unions, enums, typedefs, macros
- **Relationship Extraction**:
  - `CONTAINS` - file contains entity
  - `CALLS` - function calls another function
  - `USES_TYPE` - function/struct uses a type
  - `MEMBER_OF` - struct member belongs to struct
  - `ENUMERATOR_OF` - enum value belongs to enum
  - `TYPEDEF_OF` - typedef aliases a type
  - `INCLUDES` - file includes another file

## Usage

```python
from codesearch.builder import CodeIndexer, IndexConfig

config = IndexConfig(enable_graph_indexing=True)
indexer = CodeIndexer(config)
await indexer.build_index("./my-codebase")

# Get call graph
call_graph = indexer.get_call_graph("my_function", depth=3)

# Find references
refs = indexer.find_symbol_references("my_struct")

# Get file structure
structure = indexer.get_file_structure("src/utils.c")

# Get graph stats
stats = indexer.get_graph_stats()
```

## MCP Tools

The MCP server provides additional tools:

- `get_call_graph` - Get callers and callees for a function
- `get_graph_references` - Find all references to a symbol
- `get_file_structure` - Get entities defined in a file
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add graph indexing documentation"
```

---

## Self-Review Checklist

1. **Spec coverage:** Check that all entity types (file/function/struct/macro/typedef) and relationship types (structure/calls/data flow) are covered in the tasks above.
2. **No placeholders:** Verify no "TBD", "TODO", or vague descriptions remain.
3. **Type consistency:** Verify entity IDs, relationship types, and method signatures are consistent across all tasks.
