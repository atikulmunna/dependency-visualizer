"""Tests for dgvis.exporter — DOT, JSON, and text-tree output."""

import json

import pytest

from dgvis.exporter import export_dot, export_json, export_tree
from dgvis.graph import build_graph


def _sample_graph():
    return build_graph({
        "app": ["flask", "click"],
        "flask": ["werkzeug"],
        "click": [],
        "werkzeug": [],
    })


class TestExportDot:
    def test_valid_dot(self):
        dot = export_dot(_sample_graph())
        assert dot.startswith("digraph dependencies {")
        assert dot.strip().endswith("}")
        assert '"app" -> "flask"' in dot
        assert '"flask" -> "werkzeug"' in dot

    def test_write_to_file(self, tmp_path):
        out = tmp_path / "test.dot"
        export_dot(_sample_graph(), output=str(out))
        assert out.exists()
        content = out.read_text()
        assert "digraph" in content

    def test_version_in_label(self):
        from dgvis.graph import Graph
        g = Graph()
        g.add_node("flask", version="2.3.2")
        g.add_edge("app", "flask")
        dot = export_dot(g)
        assert "2.3.2" in dot


class TestExportJson:
    def test_valid_json(self):
        raw = export_json(_sample_graph())
        data = json.loads(raw)
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data
        assert data["stats"]["node_count"] == 4
        assert data["stats"]["edge_count"] == 3

    def test_node_names(self):
        data = json.loads(export_json(_sample_graph()))
        names = {n["name"] for n in data["nodes"]}
        assert names == {"app", "flask", "click", "werkzeug"}

    def test_write_to_file(self, tmp_path):
        out = tmp_path / "test.json"
        export_json(_sample_graph(), output=str(out))
        data = json.loads(out.read_text())
        assert data["stats"]["node_count"] == 4


class TestExportTree:
    def test_basic_tree(self):
        tree = export_tree(_sample_graph())
        assert "app" in tree
        assert "flask" in tree
        assert "werkzeug" in tree

    def test_connectors(self):
        tree = export_tree(_sample_graph())
        assert "├──" in tree or "└──" in tree

    def test_max_depth(self):
        tree = export_tree(_sample_graph(), max_depth=1)
        assert "..." in tree  # truncated

    def test_no_root(self):
        from dgvis.graph import Graph
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        tree = export_tree(g)
        # Both have incoming edges — should still produce output
        assert len(tree) > 0

    def test_missing_root(self):
        g = _sample_graph()
        tree = export_tree(g, root="nonexistent")
        assert "not found" in tree
