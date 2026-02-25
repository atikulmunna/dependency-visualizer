"""Tests for dgvis.parser plugin registry."""

import pytest

from dgvis.parser import (
    ParseError,
    detect_format,
    parse_file,
    registry,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure the global registry is clean before/after each test."""
    registry.clear()
    yield
    registry.clear()


def _dummy_parser(filepath):
    """A minimal parser for testing."""
    return {"__root__": ["plugin-dep-a", "plugin-dep-b"]}


class TestParserRegistry:
    def test_register_by_extension(self, tmp_path):
        registry.register_parser(_dummy_parser, extensions=[".custom"])
        f = tmp_path / "deps.custom"
        f.write_text("", encoding="utf-8")
        result = parse_file(str(f))
        assert result == {"__root__": ["plugin-dep-a", "plugin-dep-b"]}

    def test_register_by_filename(self, tmp_path):
        registry.register_parser(_dummy_parser, filenames=["Pipfile.lock"])
        f = tmp_path / "Pipfile.lock"
        f.write_text("", encoding="utf-8")
        result = parse_file(str(f))
        assert result["__root__"] == ["plugin-dep-a", "plugin-dep-b"]

    def test_decorator_form(self, tmp_path):
        @registry.register(extensions=[".xyz"])
        def parse_xyz(filepath):
            return {"__root__": ["x", "y", "z"]}

        f = tmp_path / "test.xyz"
        f.write_text("", encoding="utf-8")
        result = parse_file(str(f))
        assert result["__root__"] == ["x", "y", "z"]

    def test_plugin_takes_priority(self, tmp_path):
        """Plugin for .txt should override built-in requirements parser."""
        registry.register_parser(_dummy_parser, extensions=[".txt"])
        f = tmp_path / "requirements.txt"
        f.write_text("flask\nrequests\n", encoding="utf-8")
        result = parse_file(str(f))
        # Plugin output, not built-in requirements parser
        assert result["__root__"] == ["plugin-dep-a", "plugin-dep-b"]

    def test_filename_over_extension(self, tmp_path):
        """Filename match should take priority over extension match."""
        def parse_special(filepath):
            return {"__root__": ["special"]}

        registry.register_parser(_dummy_parser, extensions=[".lock"])
        registry.register_parser(parse_special, filenames=["special.lock"])

        f = tmp_path / "special.lock"
        f.write_text("", encoding="utf-8")
        result = parse_file(str(f))
        assert result["__root__"] == ["special"]

    def test_detect_format_returns_plugin(self, tmp_path):
        registry.register_parser(_dummy_parser, extensions=[".custom"])
        assert detect_format("test.custom") == "plugin"

    def test_no_plugin_falls_through(self):
        """Without plugins, detect_format should work as before."""
        assert detect_format("requirements.txt") == "requirements"
        assert detect_format("deps.yaml") == "yaml"

    def test_clear(self):
        registry.register_parser(_dummy_parser, extensions=[".custom"])
        assert ".custom" in registry.registered_extensions
        registry.clear()
        assert registry.registered_extensions == []
        assert registry.registered_filenames == []

    def test_registered_properties(self):
        registry.register_parser(_dummy_parser, extensions=[".a", ".b"], filenames=["c.lock"])
        assert set(registry.registered_extensions) == {".a", ".b"}
        assert registry.registered_filenames == ["c.lock"]

    def test_unsupported_without_plugin(self):
        """Unregistered extension should still raise ParseError."""
        with pytest.raises(ParseError, match="Unsupported"):
            detect_format("deps.zzz")
