"""Tests for dgvis.graph — Node, Graph, and build_graph."""

import pytest

from dgvis.graph import Graph, Node, build_graph


# ── Node tests ───────────────────────────────────────────────


class TestNode:
    def test_basic_creation(self):
        n = Node(name="flask")
        assert n.name == "flask"
        assert n.version is None
        assert n.metadata == {}

    def test_with_version(self):
        n = Node(name="flask", version="2.3.2")
        assert n.version == "2.3.2"
        assert "2.3.2" in repr(n)

    def test_equality(self):
        a = Node(name="flask")
        b = Node(name="flask", version="1.0")
        assert a == b  # equality by name only

    def test_hash(self):
        a = Node(name="flask")
        b = Node(name="flask")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


# ── Graph tests ──────────────────────────────────────────────


class TestGraph:
    def test_empty_graph(self):
        g = Graph()
        assert g.node_count() == 0
        assert g.edge_count() == 0
        assert len(g) == 0

    def test_add_node(self):
        g = Graph()
        n = g.add_node("flask", version="2.3.2")
        assert n.name == "flask"
        assert g.has_node("flask")
        assert g.node_count() == 1

    def test_no_duplicate_nodes(self):
        g = Graph()
        g.add_node("flask")
        g.add_node("flask")
        assert g.node_count() == 1

    def test_update_version_on_readd(self):
        g = Graph()
        g.add_node("flask")
        g.add_node("flask", version="2.3.2")
        assert g.get_node("flask").version == "2.3.2"

    def test_add_edge(self):
        g = Graph()
        g.add_edge("app", "flask")
        assert g.has_node("app")
        assert g.has_node("flask")
        assert g.has_edge("app", "flask")
        assert not g.has_edge("flask", "app")

    def test_neighbors(self):
        g = Graph()
        g.add_edge("app", "flask")
        g.add_edge("app", "click")
        assert g.neighbors("app") == {"flask", "click"}
        assert g.neighbors("flask") == set()

    def test_neighbors_missing_node(self):
        g = Graph()
        with pytest.raises(KeyError):
            g.neighbors("nonexistent")

    def test_edge_count(self):
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        g.add_edge("b", "c")
        assert g.edge_count() == 3

    def test_roots(self):
        g = Graph()
        g.add_edge("app", "flask")
        g.add_edge("app", "click")
        g.add_edge("flask", "werkzeug")
        assert g.roots() == ["app"]

    def test_contains(self):
        g = Graph()
        g.add_node("flask")
        assert "flask" in g
        assert "django" not in g

    def test_repr(self):
        g = Graph()
        g.add_edge("a", "b")
        assert "nodes=2" in repr(g)
        assert "edges=1" in repr(g)


# ── build_graph tests ────────────────────────────────────────


class TestBuildGraph:
    def test_simple_deps(self):
        deps = {"app": ["flask", "click"], "flask": ["werkzeug"]}
        g = build_graph(deps)
        assert g.node_count() == 4
        assert g.has_edge("app", "flask")
        assert g.has_edge("flask", "werkzeug")

    def test_flat_deps(self):
        deps = {"__root__": ["flask", "requests", "click"]}
        g = build_graph(deps)
        assert g.node_count() == 4
        assert g.has_edge("__root__", "flask")

    def test_empty_deps(self):
        g = build_graph({})
        assert g.node_count() == 0

    def test_leaf_with_empty_list(self):
        deps = {"app": ["lib"], "lib": []}
        g = build_graph(deps)
        assert g.node_count() == 2
        assert g.neighbors("lib") == set()
