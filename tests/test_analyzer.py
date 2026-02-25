"""Tests for dgvis.analyzer — cycle detection, topo sort, depth, transitive deps."""

import pytest

from dgvis.analyzer import (
    compute_depth,
    detect_cycles,
    graph_stats,
    topological_sort,
    transitive_deps,
)
from dgvis.graph import Graph, build_graph


# ── Helpers ──────────────────────────────────────────────────


def _acyclic_graph() -> Graph:
    return build_graph({
        "app": ["auth", "db"],
        "auth": ["crypto"],
        "db": ["pool"],
        "crypto": [],
        "pool": [],
    })


def _cyclic_graph() -> Graph:
    return build_graph({
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    })


def _diamond_graph() -> Graph:
    """Diamond: app → {A, B}, both A and B → C"""
    return build_graph({
        "app": ["a", "b"],
        "a": ["c"],
        "b": ["c"],
        "c": [],
    })


# ── Cycle detection tests ───────────────────────────────────


class TestDetectCycles:
    def test_no_cycles(self):
        cycles = detect_cycles(_acyclic_graph())
        assert cycles == []

    def test_simple_cycle(self):
        cycles = detect_cycles(_cyclic_graph())
        assert len(cycles) >= 1
        # The cycle should contain a, b, c
        cycle_nodes = set(cycles[0])
        assert {"a", "b", "c"}.issubset(cycle_nodes)

    def test_diamond_no_cycle(self):
        cycles = detect_cycles(_diamond_graph())
        assert cycles == []

    def test_empty_graph(self):
        g = Graph()
        assert detect_cycles(g) == []


# ── Topological sort tests ──────────────────────────────────


class TestTopologicalSort:
    def test_acyclic_order(self):
        g = _acyclic_graph()
        order = topological_sort(g)
        assert len(order) == g.node_count()
        # app must come before auth and db
        assert order.index("app") < order.index("auth")
        assert order.index("app") < order.index("db")
        # auth before crypto
        assert order.index("auth") < order.index("crypto")

    def test_cyclic_raises(self):
        with pytest.raises(ValueError, match="cycle"):
            topological_sort(_cyclic_graph())

    def test_diamond(self):
        order = topological_sort(_diamond_graph())
        assert order.index("app") < order.index("a")
        assert order.index("app") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_single_node(self):
        g = build_graph({"solo": []})
        assert topological_sort(g) == ["solo"]


# ── Depth tests ──────────────────────────────────────────────


class TestComputeDepth:
    def test_basic_depth(self):
        g = _acyclic_graph()
        depths = compute_depth(g, "app")
        assert depths["app"] == 0
        assert depths["auth"] == 1
        assert depths["crypto"] == 2
        assert depths["db"] == 1
        assert depths["pool"] == 2

    def test_auto_root(self):
        g = _acyclic_graph()
        depths = compute_depth(g)
        assert "app" in depths
        assert depths["app"] == 0

    def test_bad_root(self):
        g = _acyclic_graph()
        with pytest.raises(KeyError):
            compute_depth(g, "nonexistent")

    def test_empty_graph(self):
        g = Graph()
        assert compute_depth(g) == {}


# ── Transitive dependency tests ─────────────────────────────


class TestTransitiveDeps:
    def test_all_reachable(self):
        g = _acyclic_graph()
        td = transitive_deps(g, "app")
        assert td == {"auth", "db", "crypto", "pool"}

    def test_leaf_no_deps(self):
        g = _acyclic_graph()
        assert transitive_deps(g, "crypto") == set()

    def test_diamond_shared(self):
        g = _diamond_graph()
        td = transitive_deps(g, "app")
        assert "c" in td

    def test_bad_node(self):
        g = _acyclic_graph()
        with pytest.raises(KeyError):
            transitive_deps(g, "nonexistent")


# ── Stats tests ──────────────────────────────────────────────


class TestGraphStats:
    def test_acyclic_stats(self):
        st = graph_stats(_acyclic_graph())
        assert st["node_count"] == 5
        assert st["has_cycles"] is False
        assert st["max_depth"] == 2
        assert st["leaf_count"] == 2

    def test_cyclic_stats(self):
        st = graph_stats(_cyclic_graph())
        assert st["has_cycles"] is True
        assert st["cycle_count"] >= 1
