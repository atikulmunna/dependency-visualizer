"""Graph data structures — Node, Graph (adjacency list), and builder."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """A single node in the dependency graph."""

    name: str
    version: str | None = None
    metadata: dict = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.name == other.name

    def __repr__(self) -> str:
        ver = f"=={self.version}" if self.version else ""
        return f"Node({self.name}{ver})"


class Graph:
    """Directed graph using adjacency list representation.

    Edges go from dependant → dependency:
        add_edge("app", "flask")  means  app depends-on flask
    """

    def __init__(self) -> None:
        self._adj: dict[str, set[str]] = {}
        self._nodes: dict[str, Node] = {}

    # ── Mutators ──────────────────────────────────────────────

    def add_node(self, name: str, version: str | None = None, **meta) -> Node:
        """Add a node, or return the existing one if already present."""
        if name not in self._nodes:
            self._nodes[name] = Node(name=name, version=version, metadata=meta)
            self._adj[name] = set()
        else:
            # Update version / metadata if provided on an existing node
            node = self._nodes[name]
            if version is not None:
                node.version = version
            node.metadata.update(meta)
        return self._nodes[name]

    def add_edge(self, src: str, dst: str) -> None:
        """Add a directed edge *src* → *dst*.

        Both nodes are created automatically if they don't exist.
        """
        self.add_node(src)
        self.add_node(dst)
        self._adj[src].add(dst)

    # ── Queries ───────────────────────────────────────────────

    def neighbors(self, name: str) -> set[str]:
        """Return direct dependencies (outgoing neighbors) of *name*."""
        if name not in self._adj:
            raise KeyError(f"Node '{name}' not in graph")
        return self._adj[name]

    def has_node(self, name: str) -> bool:
        return name in self._nodes

    def has_edge(self, src: str, dst: str) -> bool:
        return src in self._adj and dst in self._adj[src]

    def get_node(self, name: str) -> Node:
        return self._nodes[name]

    def nodes(self) -> list[Node]:
        """Return all nodes in insertion order."""
        return list(self._nodes.values())

    def node_names(self) -> list[str]:
        return list(self._nodes.keys())

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return sum(len(deps) for deps in self._adj.values())

    def roots(self) -> list[str]:
        """Return nodes with no incoming edges (i.e. top-level dependants)."""
        has_incoming: set[str] = set()
        for deps in self._adj.values():
            has_incoming.update(deps)
        return [n for n in self._nodes if n not in has_incoming]

    # ── Dunder helpers ────────────────────────────────────────

    def __contains__(self, name: str) -> bool:
        return self.has_node(name)

    def __len__(self) -> int:
        return self.node_count()

    def __repr__(self) -> str:
        return f"Graph(nodes={self.node_count()}, edges={self.edge_count()})"


# ── Builder ──────────────────────────────────────────────────


def build_graph(deps: dict[str, list[str]]) -> Graph:
    """Construct a *Graph* from a ``{node: [dependencies]}`` mapping.

    This is the output format of every parser.
    """
    g = Graph()
    for parent, children in deps.items():
        g.add_node(parent)
        for child in children:
            g.add_edge(parent, child)
    return g
