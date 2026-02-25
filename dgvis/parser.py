"""Parsers for dependency files — requirements.txt, YAML, package.json, and go.mod."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


class ParseError(Exception):
    """Raised when a dependency file contains unparseable content."""

    def __init__(self, message: str, line_no: int | None = None, line: str = "") -> None:
        self.line_no = line_no
        self.line = line
        detail = f" (line {line_no}: {line!r})" if line_no else ""
        super().__init__(f"{message}{detail}")


# ── requirements.txt ─────────────────────────────────────────

# Matches: package, package==1.0, package>=1.0,<2.0, etc.
_REQ_PATTERN = re.compile(
    r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)"  # package name (PEP 508)
    r"(\s*[\[;].*)?$"                                   # optional extras/markers (ignored)
    r"|"
    r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)"  # package name
    r"\s*[!=<>~]+.*$"                                    # version specifiers
)

# Simpler: just grab the package name before any specifier
_NAME_RE = re.compile(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)(.*)$")


def parse_requirements(filepath: str | Path) -> dict[str, list[str]]:
    """Parse a ``requirements.txt`` file into ``{"__root__": [packages]}``.

    Handles comments, blank lines, and version specifiers.
    Lines starting with ``-`` (flags) are skipped with a warning.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    packages: list[str] = []
    warnings: list[str] = []

    for line_no, raw in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        # Skip pip flags (-r, -e, --index-url, etc.)
        if line.startswith("-"):
            warnings.append(f"Skipped flag on line {line_no}: {line}")
            continue

        m = _NAME_RE.match(line)
        if m:
            pkg_name = m.group(1).lower().replace("_", "-")
            packages.append(pkg_name)
        else:
            raise ParseError("Invalid dependency line", line_no=line_no, line=raw)

    return {"__root__": packages, "__warnings__": warnings} if warnings else {"__root__": packages}


# ── Custom YAML format ──────────────────────────────────────


def parse_yaml(filepath: str | Path) -> dict[str, list[str]]:
    """Parse a custom ``deps.yaml`` file into ``{node: [deps]}`` mapping.

    Expected structure::

        project: my-app
        dependencies:
          app:
            - auth
            - database
          auth:
            - crypto
          crypto: []
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    data = yaml.safe_load(filepath.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or "dependencies" not in data:
        raise ParseError("YAML file must contain a 'dependencies' key")

    raw_deps: dict = data["dependencies"]
    if not isinstance(raw_deps, dict):
        raise ParseError("'dependencies' must be a mapping")

    deps: dict[str, list[str]] = {}
    for node, children in raw_deps.items():
        node_str = str(node)
        if children is None:
            deps[node_str] = []
        elif isinstance(children, list):
            deps[node_str] = [str(c) for c in children]
        else:
            raise ParseError(f"Dependencies for '{node}' must be a list or empty")

    return deps


# ── package.json (Node.js) ───────────────────────────────────


def parse_package_json(filepath: str | Path) -> dict[str, list[str]]:
    """Parse a ``package.json`` file into ``{"__root__": [packages]}``.

    Extracts both ``dependencies`` and ``devDependencies``.
    If a ``package-lock.json`` exists in the same directory, delegates to
    :func:`parse_package_lock` for full transitive depth.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check for lock file — use it for transitive tree if available
    lock_path = filepath.parent / "package-lock.json"
    if filepath.name == "package.json" and lock_path.exists():
        return parse_package_lock(str(lock_path))

    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ParseError("package.json must be a JSON object")

    packages: list[str] = []
    for section in ("dependencies", "devDependencies"):
        deps = data.get(section, {})
        if isinstance(deps, dict):
            packages.extend(deps.keys())

    return {"__root__": packages}


def parse_package_lock(filepath: str | Path) -> dict[str, list[str]]:
    """Parse a ``package-lock.json`` file into ``{package: [sub-deps]}``.

    Supports npm lockfile v2/v3 (``packages`` key) and v1 (``dependencies`` key).
    Returns the full transitive dependency tree.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    data = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ParseError("package-lock.json must be a JSON object")

    deps: dict[str, list[str]] = {}

    # npm v2/v3 format: "packages" with "node_modules/name" keys
    if "packages" in data:
        for pkg_path, pkg_info in data["packages"].items():
            if pkg_path == "":
                # Root project entry
                root_deps = list(pkg_info.get("dependencies", {}).keys())
                root_deps += list(pkg_info.get("devDependencies", {}).keys())
                if root_deps:
                    deps["__root__"] = root_deps
                continue

            # Extract package name from path like "node_modules/express"
            name = pkg_path.split("node_modules/")[-1]
            sub_deps = list(pkg_info.get("dependencies", {}).keys())
            deps[name] = sub_deps

    # npm v1 fallback: "dependencies" with nested structure
    elif "dependencies" in data:
        def _walk_v1(parent: str, dep_map: dict) -> None:
            children: list[str] = []
            for name, info in dep_map.items():
                children.append(name)
                nested = info.get("dependencies", {})
                if nested:
                    _walk_v1(name, nested)
                else:
                    deps[name] = []
            deps[parent] = children

        _walk_v1("__root__", data["dependencies"])
    else:
        raise ParseError("package-lock.json has no 'packages' or 'dependencies' key")

    return deps


# ── go.mod (Go) ──────────────────────────────────────────────

# Matches: github.com/user/repo v1.2.3
_GOMOD_REQ_RE = re.compile(r"^\s*([^\s]+)\s+v[^\s]+\s*$")


def parse_gomod(filepath: str | Path) -> dict[str, list[str]]:
    """Parse a ``go.mod`` file into ``{"__root__": [modules]}``.

    Handles both single-line ``require pkg v1.0`` and block
    ``require ( ... )`` syntax.  Module paths are shortened to the
    last segment for readability (e.g. ``github.com/gin-gonic/gin`` → ``gin``).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    text = filepath.read_text(encoding="utf-8")
    modules: list[str] = []
    in_require_block = False

    for line in text.splitlines():
        stripped = line.strip()

        # Skip comments & blank lines
        if not stripped or stripped.startswith("//"):
            continue

        # Block require start
        if stripped.startswith("require (") or stripped == "require(":
            in_require_block = True
            continue

        # Block require end
        if in_require_block and stripped == ")":
            in_require_block = False
            continue

        # Inside require block
        if in_require_block:
            m = _GOMOD_REQ_RE.match(stripped)
            if m:
                modules.append(_shorten_go_module(m.group(1)))
            continue

        # Single-line require
        if stripped.startswith("require ") and "(" not in stripped:
            remainder = stripped[len("require "):].strip()
            m = _GOMOD_REQ_RE.match(remainder)
            if m:
                modules.append(_shorten_go_module(m.group(1)))

    return {"__root__": modules}


def _shorten_go_module(module_path: str) -> str:
    """Shorten a Go module path to its last segment.

    ``github.com/gin-gonic/gin`` → ``gin``
    """
    return module_path.rstrip("/").rsplit("/", 1)[-1]


# ── Plugin Registry ──────────────────────────────────────────


from typing import Callable

ParserFunc = Callable[[str | Path], dict[str, list[str]]]


class ParserRegistry:
    """Registry for custom dependency-file parsers.

    Allows external parsers to be registered via decorator or function call.
    Registered parsers take priority over built-in ones.

    Usage::

        from dgvis.parser import registry

        @registry.register(extensions=[".lock"], filenames=["custom.lock"])
        def parse_custom_lock(filepath):
            ...
    """

    def __init__(self) -> None:
        self._by_extension: dict[str, ParserFunc] = {}
        self._by_filename: dict[str, ParserFunc] = {}

    def register(
        self,
        extensions: list[str] | None = None,
        filenames: list[str] | None = None,
    ) -> Callable[[ParserFunc], ParserFunc]:
        """Decorator to register a parser for given extensions/filenames.

        Args:
            extensions: File extensions to match (e.g. ``['.lock', '.deps']``).
            filenames: Exact filenames to match (e.g. ``['custom.lock']``).
        """
        def decorator(func: ParserFunc) -> ParserFunc:
            for ext in (extensions or []):
                self._by_extension[ext.lower()] = func
            for name in (filenames or []):
                self._by_filename[name.lower()] = func
            return func
        return decorator

    def register_parser(
        self,
        func: ParserFunc,
        extensions: list[str] | None = None,
        filenames: list[str] | None = None,
    ) -> None:
        """Imperatively register a parser (non-decorator form)."""
        for ext in (extensions or []):
            self._by_extension[ext.lower()] = func
        for name in (filenames or []):
            self._by_filename[name.lower()] = func

    def lookup(self, filepath: str | Path) -> ParserFunc | None:
        """Find a registered parser for the given filepath, or None."""
        p = Path(filepath)
        name = p.name.lower()
        ext = p.suffix.lower()

        # Exact filename match first (higher specificity)
        if name in self._by_filename:
            return self._by_filename[name]
        if ext in self._by_extension:
            return self._by_extension[ext]
        return None

    @property
    def registered_extensions(self) -> list[str]:
        return list(self._by_extension.keys())

    @property
    def registered_filenames(self) -> list[str]:
        return list(self._by_filename.keys())

    def clear(self) -> None:
        """Remove all registered parsers. Mainly for testing."""
        self._by_extension.clear()
        self._by_filename.clear()


# Global registry instance
registry = ParserRegistry()


# ── Auto-detection ───────────────────────────────────────────


_BUILTIN_PARSERS: dict[str, ParserFunc] = {
    "requirements": parse_requirements,
    "yaml": parse_yaml,
    "package_json": parse_package_json,
    "gomod": parse_gomod,
}


def detect_format(filepath: str | Path) -> str:
    """Detect file format by extension.

    Returns one of: ``'requirements'``, ``'yaml'``, ``'package_json'``, ``'gomod'``,
    or ``'plugin'`` if a registered plugin matches.
    """
    # Check plugin registry first (plugins take priority)
    if registry.lookup(filepath) is not None:
        return "plugin"

    p = Path(filepath)
    name = p.name.lower()
    ext = p.suffix.lower()

    # Exact filename matches first
    if name in ("package.json", "package-lock.json"):
        return "package_json"
    if name == "go.mod":
        return "gomod"

    # Extension-based fallback
    if ext in (".yaml", ".yml"):
        return "yaml"
    if ext in (".txt", ""):
        return "requirements"
    if ext == ".json":
        return "package_json"
    if ext == ".mod":
        return "gomod"

    raise ParseError(f"Unsupported file format: {name}")


def parse_file(filepath: str | Path) -> dict[str, list[str]]:
    """Auto-detect format and parse the dependency file.

    Plugin-registered parsers take priority over built-in ones.
    """
    # Check plugin registry first
    plugin_parser = registry.lookup(filepath)
    if plugin_parser is not None:
        return plugin_parser(filepath)

    fmt = detect_format(filepath)
    if fmt == "yaml":
        return parse_yaml(filepath)
    if fmt == "package_json":
        return parse_package_json(filepath)
    if fmt == "gomod":
        return parse_gomod(filepath)
    return parse_requirements(filepath)

