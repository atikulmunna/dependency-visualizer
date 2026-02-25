"""Performance stress test — verifies algorithms scale to 10,000+ nodes."""

import time

import pytest

from dgvis.analyzer import detect_cycles, topological_sort
from dgvis.graph import Graph


def _build_large_graph(n: int) -> Graph:
    """Build a wide DAG: root → {node_0 .. node_n}, each node_i → leaf_i."""
    g = Graph()
    for i in range(n):
        g.add_edge("root", f"node_{i}")
        g.add_edge(f"node_{i}", f"leaf_{i}")
    return g


def _build_chain_graph(n: int) -> Graph:
    """Build a long chain: n0 → n1 → n2 → ... → n_{n-1}."""
    g = Graph()
    for i in range(n - 1):
        g.add_edge(f"n{i}", f"n{i+1}")
    return g


class TestPerformance:
    def test_large_graph_cycle_detection(self):
        """Cycle detection on a 10,000+ node acyclic graph should complete in < 5s."""
        g = _build_large_graph(10_000)
        assert g.node_count() > 10_000

        start = time.perf_counter()
        cycles = detect_cycles(g)
        elapsed = time.perf_counter() - start

        assert cycles == []
        assert elapsed < 5.0, f"Cycle detection took {elapsed:.2f}s (> 5s limit)"

    def test_large_graph_topological_sort(self):
        """Topological sort on a 10,000+ node graph should complete in < 5s."""
        g = _build_large_graph(10_000)

        start = time.perf_counter()
        order = topological_sort(g)
        elapsed = time.perf_counter() - start

        assert len(order) == g.node_count()
        assert elapsed < 5.0, f"Topological sort took {elapsed:.2f}s (> 5s limit)"

    def test_deep_chain_cycle_detection(self):
        """Long chain (5,000 nodes) should not trigger excessive recursion."""
        g = _build_chain_graph(5_000)

        start = time.perf_counter()
        cycles = detect_cycles(g)
        elapsed = time.perf_counter() - start

        assert cycles == []
        assert elapsed < 5.0, f"Chain cycle detection took {elapsed:.2f}s (> 5s limit)"

    def test_node_edge_counts(self):
        """Verify graph builder handles large inputs correctly."""
        g = _build_large_graph(10_000)
        # root + 10k node_ + 10k leaf_ = 20,001
        assert g.node_count() == 20_001
        # root→node (10k) + node→leaf (10k) = 20,000
        assert g.edge_count() == 20_000
