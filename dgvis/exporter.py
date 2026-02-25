"""Export engine — DOT, JSON, and text-tree output formats."""

from __future__ import annotations

import json
from pathlib import Path

from dgvis.graph import Graph


# ── DOT (Graphviz) ───────────────────────────────────────────


def export_dot(graph: Graph, output: str | Path | None = None) -> str:
    """Generate a Graphviz DOT representation of the graph.

    If *output* is provided, writes to that file path and returns the content.
    """
    lines: list[str] = ["digraph dependencies {", '    rankdir=LR;', '    node [shape=box, style=filled, fillcolor="#e8f4fd", fontname="Helvetica"];', ""]

    # Nodes
    for node in graph.nodes():
        label = node.name
        if node.version:
            label += f"\\n{node.version}"
        lines.append(f'    "{node.name}" [label="{label}"];')

    lines.append("")

    # Edges
    for node in graph.nodes():
        for dep in sorted(graph.neighbors(node.name)):
            lines.append(f'    "{node.name}" -> "{dep}";')

    lines.append("}")
    content = "\n".join(lines) + "\n"

    if output:
        Path(output).write_text(content, encoding="utf-8")

    return content


# ── JSON ─────────────────────────────────────────────────────


def export_json(graph: Graph, output: str | Path | None = None) -> str:
    """Export graph as a JSON structure.

    Format::

        {
            "nodes": [{"name": "...", "version": "..."}],
            "edges": [{"from": "...", "to": "..."}],
            "stats": {"node_count": N, "edge_count": M}
        }
    """
    nodes = []
    for node in graph.nodes():
        entry: dict = {"name": node.name}
        if node.version:
            entry["version"] = node.version
        nodes.append(entry)

    edges = []
    for node in graph.nodes():
        for dep in sorted(graph.neighbors(node.name)):
            edges.append({"from": node.name, "to": dep})

    data = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": graph.node_count(),
            "edge_count": graph.edge_count(),
        },
    }

    content = json.dumps(data, indent=2) + "\n"

    if output:
        Path(output).write_text(content, encoding="utf-8")

    return content


# ── Text Tree ────────────────────────────────────────────────


def export_tree(
    graph: Graph,
    root: str | None = None,
    max_depth: int | None = None,
) -> str:
    """Render the graph as an indented ASCII tree.

    Uses ``├──`` and ``└──`` connectors for a clean tree display.
    Handles shared dependencies by marking them as ``(*)`` on revisit.
    """
    if root is None:
        roots = graph.roots()
        if not roots:
            return "(no root nodes found)\n"
        root = roots[0]

    if not graph.has_node(root):
        return f"(root node '{root}' not found)\n"

    lines: list[str] = []
    seen: set[str] = set()

    def _walk(node: str, prefix: str, is_last: bool, depth: int) -> None:
        connector = "└── " if is_last else "├── "
        if depth == 0:
            lines.append(node)
        else:
            lines.append(f"{prefix}{connector}{node}")

        if node in seen:
            # Already printed subtree — mark as circular reference
            lines[-1] += " (*)"
            return
        seen.add(node)

        if max_depth is not None and depth >= max_depth:
            children = list(sorted(graph.neighbors(node)))
            if children:
                child_prefix = prefix + ("    " if is_last else "│   ")
                lines.append(f"{child_prefix}└── ... ({len(children)} deps)")
            return

        children = list(sorted(graph.neighbors(node)))
        for i, child in enumerate(children):
            is_child_last = i == len(children) - 1
            child_prefix = prefix + ("    " if is_last or depth == 0 else "│   ")
            _walk(child, child_prefix, is_child_last, depth + 1)

    _walk(root, "", True, 0)
    return "\n".join(lines) + "\n"
