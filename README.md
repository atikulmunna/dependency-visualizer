# dgvis — Dependency Graph Visualizer

A systems-focused CLI tool that parses dependency files, builds directed graphs, detects circular dependencies, and exports visualizations. Built from scratch with zero graph library dependencies.

## Features

- **Multi-format parsing** — `requirements.txt`, `package.json`/`package-lock.json`, `go.mod`, custom YAML
- **Cycle detection** — Iterative DFS with back-edge tracking, handles 10,000+ node graphs
- **Topological sorting** — Kahn's algorithm for build-order resolution
- **Transitive dependency analysis** — Discover all downstream dependencies
- **Multiple export formats** — Graphviz DOT, JSON, ASCII tree with dedup markers
- **Lock file support** — Auto-resolves `package-lock.json` for full transitive tree

## Quick Start

```bash
# Install dependencies
pip install click pyyaml pytest

# Clone and run
git clone https://github.com/atikulmunna/dependency-visualizer.git
cd dependency-visualizer

# Set PYTHONPATH and run
export PYTHONPATH="."          # Linux/macOS
$env:PYTHONPATH="."            # PowerShell

python -m dgvis analyze fixtures/simple.yaml
```

## Commands

### `dgvis analyze <file>`
Parse and summarize a dependency graph.
```
$ python -m dgvis analyze fixtures/package.json

─── Dependency Graph Analysis ───
  Nodes       : 11
  Edges       : 11
  Root nodes  : __root__
  Leaf nodes  : 5
  Max depth   : 3
  Avg deps    : 1.0
  Cycles      : None ✓
```

### `dgvis visualize <file>`
Export graph as ASCII tree, DOT, or JSON.
```
$ python -m dgvis visualize fixtures/deep_tree.yaml

level-0
    ├── level-1a
    │   ├── level-2a
    │   │   └── level-3a
    │   │       └── level-4a
    │   └── level-2b
    │       ├── level-3a (*)
    │       └── level-3b
    │           └── level-4a (*)
    └── level-1b
        └── level-2c
            ├── level-3b (*)
            └── level-3c
                └── level-4b
```

```bash
# Export as DOT for Graphviz rendering
python -m dgvis visualize fixtures/simple.yaml -f dot -o graph.dot

# Export as JSON
python -m dgvis visualize fixtures/simple.yaml -f json -o graph.json
```

### `dgvis detect-cycles <file>`
Check for circular dependencies.
```
$ python -m dgvis detect-cycles fixtures/cyclic.yaml

⚠ Found 1 cycle(s):
  1. service-a → service-b → service-c → service-a
```

### `dgvis stats <file>`
Detailed metrics with topological ordering.
```
$ python -m dgvis stats fixtures/simple.yaml -v

─── Graph Statistics ───

  Topological order (5 nodes):
    app → auth → database → crypto → connection-pool

  Per-node dependency counts:
    app: 2 direct dep(s)
    auth: 1 direct dep(s)
    database: 1 direct dep(s)
    crypto: 0 direct dep(s)
    connection-pool: 0 direct dep(s)

  Total: 5 nodes, 4 edges, depth 2
```

## Supported Formats

| Format | File | Depth | Notes |
|--------|------|-------|-------|
| Python | `requirements.txt` | Direct | Handles version specifiers, comments, pip flags |
| Node.js | `package.json` | Direct or tree | Auto-uses `package-lock.json` if present |
| Node.js | `package-lock.json` | Full tree | npm v2/v3 `packages` + v1 `dependencies` |
| Go | `go.mod` | Direct | Block + single-line `require`, path shortening |
| Custom | `deps.yaml` | Full tree | For testing and manual graph definition |

### Custom YAML Format
```yaml
project: my-app
dependencies:
  app:
    - auth
    - database
  auth:
    - crypto
  database:
    - connection-pool
  crypto: []
  connection-pool: []
```

## Architecture

```
dgvis/
├── cli.py        → Click-based CLI with 4 subcommands
├── parser.py     → Format detection + 5 parsers
├── graph.py      → Node/Graph (adjacency list, from scratch)
├── analyzer.py   → DFS, topo sort, BFS depth, transitive deps
├── exporter.py   → DOT, JSON, ASCII tree renderers
└── __main__.py   → python -m dgvis entry point
```

### Data Flow
```
Input File → Parser → {node: [deps]} → Graph Builder → Graph
                                                         ↓
                                              ┌──────────┼──────────┐
                                              ↓          ↓          ↓
                                          Analyzer   Exporter    CLI Output
                                        (cycles,    (DOT, JSON,  (stats,
                                        topo sort,   tree)        tables)
                                        depth)
```

## Algorithms & Complexity

| Algorithm | Use | Time | Space |
|-----------|-----|------|-------|
| Iterative DFS | Cycle detection | O(V + E) | O(V) |
| Kahn's Algorithm | Topological sort | O(V + E) | O(V) |
| BFS | Depth calculation | O(V + E) | O(V) |
| Iterative DFS | Transitive deps | O(V + E) | O(V) |

## Testing

```bash
# Run all tests
$env:PYTHONPATH="."; python -m pytest tests/ -v

# 100 tests across 6 test files
# Includes stress test with 10,000+ nodes
```

| Test File | Tests | Covers |
|-----------|-------|--------|
| `test_graph.py` | 16 | Node, Graph, builder |
| `test_parser.py` | 32 | All formats, detection, edge cases |
| `test_analyzer.py` | 16 | Cycles, topo sort, depth, transitive |
| `test_exporter.py` | 10 | DOT, JSON, tree output |
| `test_cli.py` | 15 | All commands, flags, errors |
| `test_performance.py` | 4 | 10k+ nodes, < 5s benchmark |

## Development

```bash
# Clone
git clone https://github.com/atikulmunna/dependency-visualizer.git
cd dependency-visualizer

# Install dependencies
pip install click pyyaml pytest pytest-cov

# Run tests
$env:PYTHONPATH="."; python -m pytest tests/ -v

# Run with coverage
$env:PYTHONPATH="."; python -m pytest tests/ --cov=dgvis --cov-report=term-missing
```

## License

MIT
