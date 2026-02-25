"""Tests for dgvis.cli — CLI commands via Click's test runner."""

from click.testing import CliRunner

from dgvis.cli import main

FIXTURES = "fixtures"


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    # ── analyze ──────────────────────────────────────────────

    def test_analyze_simple(self):
        result = self.runner.invoke(main, ["analyze", f"{FIXTURES}/simple.txt"])
        assert result.exit_code == 0
        assert "Nodes" in result.output
        assert "Edges" in result.output

    def test_analyze_yaml(self):
        result = self.runner.invoke(main, ["analyze", f"{FIXTURES}/simple.yaml"])
        assert result.exit_code == 0
        assert "Nodes" in result.output

    def test_analyze_cyclic(self):
        result = self.runner.invoke(main, ["analyze", f"{FIXTURES}/cyclic.yaml"])
        assert result.exit_code == 0
        assert "detected" in result.output

    def test_analyze_verbose(self):
        result = self.runner.invoke(main, ["analyze", f"{FIXTURES}/cyclic.yaml", "-v"])
        assert result.exit_code == 0
        assert "→" in result.output

    # ── visualize ────────────────────────────────────────────

    def test_visualize_tree(self):
        result = self.runner.invoke(main, ["visualize", f"{FIXTURES}/simple.yaml"])
        assert result.exit_code == 0
        assert "app" in result.output

    def test_visualize_dot(self):
        result = self.runner.invoke(main, ["visualize", f"{FIXTURES}/simple.yaml", "-f", "dot"])
        assert result.exit_code == 0
        assert "digraph" in result.output

    def test_visualize_json(self):
        result = self.runner.invoke(main, ["visualize", f"{FIXTURES}/simple.yaml", "-f", "json"])
        assert result.exit_code == 0
        assert '"nodes"' in result.output

    def test_visualize_to_file(self, tmp_path):
        out = tmp_path / "out.dot"
        result = self.runner.invoke(main, ["visualize", f"{FIXTURES}/simple.yaml", "-f", "dot", "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_visualize_with_depth(self):
        result = self.runner.invoke(main, ["visualize", f"{FIXTURES}/deep_tree.yaml", "-d", "1"])
        assert result.exit_code == 0

    # ── detect-cycles ────────────────────────────────────────

    def test_detect_cycles_clean(self):
        result = self.runner.invoke(main, ["detect-cycles", f"{FIXTURES}/simple.yaml"])
        assert result.exit_code == 0
        assert "No circular" in result.output

    def test_detect_cycles_found(self):
        result = self.runner.invoke(main, ["detect-cycles", f"{FIXTURES}/cyclic.yaml"])
        assert result.exit_code == 0
        assert "cycle" in result.output.lower()

    # ── stats ────────────────────────────────────────────────

    def test_stats_basic(self):
        result = self.runner.invoke(main, ["stats", f"{FIXTURES}/simple.yaml"])
        assert result.exit_code == 0
        assert "Topological order" in result.output

    def test_stats_verbose(self):
        result = self.runner.invoke(main, ["stats", f"{FIXTURES}/simple.yaml", "-v"])
        assert result.exit_code == 0
        assert "direct dep" in result.output

    # ── scc ────────────────────────────────────────────────────

    def test_scc_acyclic(self):
        result = self.runner.invoke(main, ["scc", f"{FIXTURES}/simple.yaml"])
        assert result.exit_code == 0
        assert "No tightly-coupled" in result.output

    def test_scc_cyclic(self):
        result = self.runner.invoke(main, ["scc", f"{FIXTURES}/cyclic.yaml"])
        assert result.exit_code == 0
        assert "tightly-coupled cluster" in result.output

    # ── Error handling ───────────────────────────────────────

    def test_file_not_found(self):
        result = self.runner.invoke(main, ["analyze", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_version_flag(self):
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

