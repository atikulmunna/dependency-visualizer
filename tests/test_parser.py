"""Tests for dgvis.parser — requirements.txt, YAML, package.json, go.mod, and auto-detection."""

import json

import pytest

from dgvis.parser import (
    ParseError,
    detect_format,
    parse_file,
    parse_gomod,
    parse_package_json,
    parse_package_lock,
    parse_requirements,
    parse_yaml,
)

FIXTURES = "fixtures"


# ── requirements.txt tests ───────────────────────────────────


class TestParseRequirements:
    def test_simple(self):
        deps = parse_requirements(f"{FIXTURES}/simple.txt")
        assert "__root__" in deps
        packages = deps["__root__"]
        assert "flask" in packages
        assert "requests" in packages
        assert "click" in packages
        assert "pyyaml" in packages

    def test_with_versions(self):
        deps = parse_requirements(f"{FIXTURES}/with_versions.txt")
        packages = deps["__root__"]
        assert "flask" in packages
        assert "numpy" in packages
        assert "pandas" in packages
        assert len(packages) == 6

    def test_skips_comments_and_blanks(self):
        deps = parse_requirements(f"{FIXTURES}/simple.txt")
        packages = deps["__root__"]
        # Comments and blank lines should not be in the output
        for p in packages:
            assert not p.startswith("#")
            assert p.strip() != ""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_requirements("nonexistent.txt")

    def test_normalizes_names(self):
        """Package names should be lowercased and underscores replaced with hyphens."""
        deps = parse_requirements(f"{FIXTURES}/simple.txt")
        for pkg in deps["__root__"]:
            assert pkg == pkg.lower()
            assert "_" not in pkg


# ── YAML tests ───────────────────────────────────────────────


class TestParseYaml:
    def test_simple(self):
        deps = parse_yaml(f"{FIXTURES}/simple.yaml")
        assert "app" in deps
        assert "auth" in deps["app"]
        assert "database" in deps["app"]
        assert deps["crypto"] == []

    def test_deep_tree(self):
        deps = parse_yaml(f"{FIXTURES}/deep_tree.yaml")
        assert "level-0" in deps
        assert "level-4a" in deps
        assert deps["level-4a"] == []

    def test_cyclic(self):
        deps = parse_yaml(f"{FIXTURES}/cyclic.yaml")
        assert "service-a" in deps
        assert "service-b" in deps["service-a"]
        # Cycle: service-c depends on service-a
        assert "service-a" in deps["service-c"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_yaml("nonexistent.yaml")

    def test_missing_dependencies_key(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("project: test\n", encoding="utf-8")
        with pytest.raises(ParseError, match="dependencies"):
            parse_yaml(str(bad_file))


# ── package.json tests ─────────────────────────────────────────


class TestParsePackageJson:
    def test_basic(self, tmp_path):
        """Parse a standalone package.json (no lock file) → flat deps."""
        pj = tmp_path / "package.json"
        pj.write_text(json.dumps({
            "dependencies": {"express": "^4.0", "lodash": "^4.0"},
            "devDependencies": {"jest": "^29.0"},
        }), encoding="utf-8")
        deps = parse_package_json(str(pj))
        assert "__root__" in deps
        assert set(deps["__root__"]) == {"express", "lodash", "jest"}

    def test_delegates_to_lock(self):
        """When package-lock.json exists alongside, should use it for tree."""
        deps = parse_package_json(f"{FIXTURES}/package.json")
        # Lock file gives transitive tree, so we should have nested deps
        assert "express" in deps
        assert "body-parser" in deps["express"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_package_json("nonexistent.json")

    def test_no_deps(self, tmp_path):
        pj = tmp_path / "package.json"
        pj.write_text(json.dumps({"name": "empty"}), encoding="utf-8")
        deps = parse_package_json(str(pj))
        assert deps["__root__"] == []


class TestParsePackageLock:
    def test_v3_format(self):
        deps = parse_package_lock(f"{FIXTURES}/package-lock.json")
        assert "__root__" in deps
        assert "express" in deps["__root__"]
        assert "axios" in deps["__root__"]
        # Transitive: express -> body-parser
        assert "body-parser" in deps["express"]
        # Leaf nodes have empty lists
        assert deps["ms"] == []

    def test_all_packages_present(self):
        deps = parse_package_lock(f"{FIXTURES}/package-lock.json")
        expected = {"__root__", "express", "axios", "body-parser", "cookie",
                    "debug", "follow-redirects", "form-data", "raw-body", "ms", "mime-types"}
        assert expected == set(deps.keys())

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_package_lock("nonexistent-lock.json")


# ── go.mod tests ──────────────────────────────────────────────


class TestParseGomod:
    def test_basic(self):
        deps = parse_gomod(f"{FIXTURES}/go.mod")
        assert "__root__" in deps
        modules = deps["__root__"]
        assert "gin" in modules
        assert "mysql" in modules
        assert "godotenv" in modules

    def test_single_line_require(self):
        deps = parse_gomod(f"{FIXTURES}/go.mod")
        modules = deps["__root__"]
        assert "testify" in modules

    def test_total_count(self):
        deps = parse_gomod(f"{FIXTURES}/go.mod")
        assert len(deps["__root__"]) == 4

    def test_shortens_module_paths(self):
        """Full paths like github.com/gin-gonic/gin should become just 'gin'."""
        deps = parse_gomod(f"{FIXTURES}/go.mod")
        for mod in deps["__root__"]:
            assert "/" not in mod

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_gomod("nonexistent.mod")


# ── Format detection tests ──────────────────────────────────


class TestDetectFormat:
    def test_txt(self):
        assert detect_format("requirements.txt") == "requirements"

    def test_yaml(self):
        assert detect_format("deps.yaml") == "yaml"

    def test_yml(self):
        assert detect_format("deps.yml") == "yaml"

    def test_package_json(self):
        assert detect_format("package.json") == "package_json"

    def test_package_lock_json(self):
        assert detect_format("package-lock.json") == "package_json"

    def test_gomod(self):
        assert detect_format("go.mod") == "gomod"

    def test_unsupported(self):
        with pytest.raises(ParseError, match="Unsupported"):
            detect_format("deps.zzz")


# ── parse_file integration ───────────────────────────────────


class TestParseFile:
    def test_auto_requirements(self):
        deps = parse_file(f"{FIXTURES}/simple.txt")
        assert "__root__" in deps

    def test_auto_yaml(self):
        deps = parse_file(f"{FIXTURES}/simple.yaml")
        assert "app" in deps

    def test_auto_package_json(self):
        deps = parse_file(f"{FIXTURES}/package.json")
        assert "express" in deps  # lock file tree

    def test_auto_gomod(self):
        deps = parse_file(f"{FIXTURES}/go.mod")
        assert "gin" in deps["__root__"]

    def test_auto_cargo(self):
        deps = parse_file(f"{FIXTURES}/Cargo.toml")
        assert "serde" in deps["__root__"]

    def test_auto_gemfile(self):
        deps = parse_file(f"{FIXTURES}/Gemfile")
        assert "rails" in deps["__root__"]

    def test_auto_pom(self):
        deps = parse_file(f"{FIXTURES}/pom.xml")
        assert "guava" in deps["__root__"]


# ── Cargo.toml ───────────────────────────────────────────────


class TestCargoToml:
    def test_basic(self):
        deps = parse_file(f"{FIXTURES}/Cargo.toml")
        names = deps["__root__"]
        assert "serde" in names
        assert "tokio" in names
        assert "clap" in names
        assert "serde_json" in names
        assert "reqwest" in names

    def test_dev_deps(self):
        deps = parse_file(f"{FIXTURES}/Cargo.toml")
        names = deps["__root__"]
        assert "criterion" in names
        assert "mockall" in names

    def test_count(self):
        deps = parse_file(f"{FIXTURES}/Cargo.toml")
        assert len(deps["__root__"]) == 7  # 5 deps + 2 dev-deps

    def test_detect_format(self):
        assert detect_format("Cargo.toml") == "cargo"


# ── Gemfile ──────────────────────────────────────────────────


class TestGemfile:
    def test_basic(self):
        deps = parse_file(f"{FIXTURES}/Gemfile")
        names = deps["__root__"]
        assert "rails" in names
        assert "pg" in names
        assert "puma" in names
        assert "redis" in names
        assert "sidekiq" in names

    def test_group_gems(self):
        deps = parse_file(f"{FIXTURES}/Gemfile")
        names = deps["__root__"]
        assert "rspec-rails" in names
        assert "debug" in names
        assert "rubocop" in names

    def test_count(self):
        deps = parse_file(f"{FIXTURES}/Gemfile")
        assert len(deps["__root__"]) == 8

    def test_detect_format(self):
        assert detect_format("Gemfile") == "gemfile"


# ── pom.xml ──────────────────────────────────────────────────


class TestPomXml:
    def test_basic(self):
        deps = parse_file(f"{FIXTURES}/pom.xml")
        names = deps["__root__"]
        assert "spring-boot-starter-web" in names
        assert "postgresql" in names
        assert "guava" in names
        assert "lombok" in names

    def test_count(self):
        deps = parse_file(f"{FIXTURES}/pom.xml")
        assert len(deps["__root__"]) == 4

    def test_detect_format(self):
        assert detect_format("pom.xml") == "pom"

