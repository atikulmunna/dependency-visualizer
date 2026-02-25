"""Graph analysis algorithms — cycle detection, topological sort, metrics."""

from __future__ import annotations

from collections import deque

from dgvis.graph import Graph


# ── Cycle Detection (DFS + recursion stack) ──────────────────


def detect_cycles(graph: Graph) -> list[list[str]]:
    """Find all distinct cycles in the graph using iterative DFS.

    Returns a list of cycles, where each cycle is a list of node names
    forming the loop (e.g. ``['a', 'b', 'c', 'a']``).

    Time: O(V + E) — each node and edge visited at most once.
    Space: O(V) — explicit stack replaces recursion stack.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph.node_names()}
    parent: dict[str, str | None] = {n: None for n in graph.node_names()}
    cycles: list[list[str]] = []

    for start in graph.node_names():
        if color[start] != WHITE:
            continue

        # Iterative DFS using an explicit stack.
        # Each entry is (node, iterator_over_neighbors).
        stack: list[tuple[str, iter]] = [(start, iter(graph.neighbors(start)))]
        color[start] = GRAY

        while stack:
            u, neighbors_iter = stack[-1]
            try:
                v = next(neighbors_iter)
                if color[v] == GRAY:
                    # Back-edge → extract cycle
                    cycle = [v, u]
                    cur = u
                    while cur != v:
                        cur = parent[cur]  # type: ignore[assignment]
                        if cur is None:
                            break
                        cycle.append(cur)
                    cycle.reverse()
                    cycles.append(cycle)
                elif color[v] == WHITE:
                    parent[v] = u
                    color[v] = GRAY
                    stack.append((v, iter(graph.neighbors(v))))
            except StopIteration:
                color[u] = BLACK
                stack.pop()

    return cycles


# ── Topological Sort (Kahn's algorithm) ──────────────────────


def topological_sort(graph: Graph) -> list[str]:
    """Return nodes in topological order using Kahn's algorithm.

    Raises ``ValueError`` if the graph contains a cycle.

    Time: O(V + E).
    """
    in_degree: dict[str, int] = {n: 0 for n in graph.node_names()}
    for node in graph.node_names():
        for dep in graph.neighbors(node):
            in_degree[dep] = in_degree.get(dep, 0) + 1

    queue: deque[str] = deque(n for n, d in in_degree.items() if d == 0)
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for dep in graph.neighbors(node):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(order) != graph.node_count():
        raise ValueError("Graph contains a cycle — topological sort is impossible")

    return order


# ── Depth Calculation (BFS) ──────────────────────────────────


def compute_depth(graph: Graph, root: str | None = None) -> dict[str, int]:
    """Compute depth of each node reachable from *root* via BFS.

    If *root* is ``None``, uses the first root node found (a node with
    no incoming edges).  Returns ``{node_name: depth}``.
    """
    if root is None:
        roots = graph.roots()
        if not roots:
            return {}
        root = roots[0]

    if not graph.has_node(root):
        raise KeyError(f"Root node '{root}' not in graph")

    depth: dict[str, int] = {root: 0}
    queue: deque[str] = deque([root])

    while queue:
        node = queue.popleft()
        for dep in graph.neighbors(node):
            if dep not in depth:
                depth[dep] = depth[node] + 1
                queue.append(dep)

    return depth


# ── Transitive Dependencies (DFS) ───────────────────────────


def transitive_deps(graph: Graph, node: str) -> set[str]:
    """Return the set of *all* nodes reachable from *node* (excluding itself).

    Time: O(V + E).
    """
    if not graph.has_node(node):
        raise KeyError(f"Node '{node}' not in graph")

    visited: set[str] = set()
    stack: list[str] = list(graph.neighbors(node))

    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        stack.extend(graph.neighbors(cur) - visited)

    return visited


# ── Summary Statistics ──────────────────────────────────────


def graph_stats(graph: Graph) -> dict:
    """Compute summary statistics about the graph.

    Returns a dict with: node_count, edge_count, roots, max_depth,
    has_cycles, leaf_count, avg_deps.
    """
    roots = graph.roots()
    depths = compute_depth(graph, roots[0]) if roots else {}
    cycles = detect_cycles(graph)

    leaves = [n for n in graph.node_names() if len(graph.neighbors(n)) == 0]

    total_edges = graph.edge_count()
    n = graph.node_count()

    return {
        "node_count": n,
        "edge_count": total_edges,
        "root_nodes": roots,
        "leaf_nodes": leaves,
        "leaf_count": len(leaves),
        "max_depth": max(depths.values()) if depths else 0,
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
        "cycles": cycles,
        "avg_direct_deps": round(total_edges / n, 2) if n else 0,
    }
