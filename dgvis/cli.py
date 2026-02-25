"""CLI entry point — command routing via Click."""

from __future__ import annotations

from pathlib import Path

import click

from dgvis import __version__
from dgvis.analyzer import detect_cycles, graph_stats, strongly_connected_components, topological_sort
from dgvis.exporter import export_dot, export_json, export_tree
from dgvis.graph import build_graph
from dgvis.parser import ParseError, parse_file


def _load_graph(filepath: str) -> tuple:
    """Shared helper: parse file → build graph. Returns (graph, deps)."""
    path = Path(filepath)
    if not path.exists():
        raise click.BadParameter(f"File not found: {filepath}")
    try:
        deps = parse_file(filepath)
    except ParseError as e:
        raise click.ClickException(f"Parse error: {e}") from e

    # Print any parser warnings
    warnings = deps.pop("__warnings__", [])
    for w in warnings:
        click.echo(click.style(f"⚠ {w}", fg="yellow"), err=True)

    graph = build_graph(deps)
    return graph, deps


# ── Main group ───────────────────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="dgvis")
def main() -> None:
    """Dependency Graph Visualizer — parse, analyze, and export dependency graphs."""


# ── analyze ──────────────────────────────────────────────────


@main.command()
@click.argument("file")
@click.option("--verbose", "-v", is_flag=True, help="Show extra details.")
def analyze(file: str, verbose: bool) -> None:
    """Parse FILE and print a summary of the dependency graph."""
    graph, _ = _load_graph(file)
    stats = graph_stats(graph)

    click.echo(click.style("─── Dependency Graph Analysis ───", fg="cyan", bold=True))
    click.echo(f"  Nodes       : {stats['node_count']}")
    click.echo(f"  Edges       : {stats['edge_count']}")
    click.echo(f"  Root nodes  : {', '.join(stats['root_nodes']) or '(none)'}")
    click.echo(f"  Leaf nodes  : {stats['leaf_count']}")
    click.echo(f"  Max depth   : {stats['max_depth']}")
    click.echo(f"  Avg deps    : {stats['avg_direct_deps']}")

    if stats["has_cycles"]:
        click.echo(click.style(f"  Cycles      : {stats['cycle_count']} detected ⚠", fg="red", bold=True))
        if verbose:
            for i, cycle in enumerate(stats["cycles"], 1):
                click.echo(f"    Cycle {i}: {' → '.join(cycle)}")
    else:
        click.echo(click.style("  Cycles      : None ✓", fg="green"))

    if verbose:
        click.echo(f"\n  Leaves: {', '.join(stats['leaf_nodes'])}")


# ── visualize ────────────────────────────────────────────────


@main.command()
@click.argument("file")
@click.option("--format", "-f", "fmt", type=click.Choice(["dot", "json", "tree"]), default="tree", help="Output format.")
@click.option("--output", "-o", default=None, help="Write output to file instead of stdout.")
@click.option("--depth", "-d", type=int, default=None, help="Max tree depth to display.")
def visualize(file: str, fmt: str, output: str | None, depth: int | None) -> None:
    """Export the dependency graph of FILE in various formats."""
    graph, _ = _load_graph(file)

    if fmt == "dot":
        content = export_dot(graph, output=output)
    elif fmt == "json":
        content = export_json(graph, output=output)
    else:
        content = export_tree(graph, max_depth=depth)
        if output:
            Path(output).write_text(content, encoding="utf-8")

    if not output:
        click.echo(content, nl=False)
    else:
        click.echo(click.style(f"✓ Written to {output}", fg="green"))


# ── detect-cycles ────────────────────────────────────────────


@main.command("detect-cycles")
@click.argument("file")
def detect_cycles_cmd(file: str) -> None:
    """Check FILE for circular dependencies."""
    graph, _ = _load_graph(file)
    cycles = detect_cycles(graph)

    if not cycles:
        click.echo(click.style("✓ No circular dependencies found.", fg="green", bold=True))
    else:
        click.echo(click.style(f"⚠ Found {len(cycles)} cycle(s):", fg="red", bold=True))
        for i, cycle in enumerate(cycles, 1):
            click.echo(f"  {i}. {' → '.join(cycle)}")


# ── stats ────────────────────────────────────────────────────


@main.command()
@click.argument("file")
@click.option("--verbose", "-v", is_flag=True, help="Show per-node details.")
def stats(file: str, verbose: bool) -> None:
    """Show detailed metrics for the dependency graph in FILE."""
    graph, _ = _load_graph(file)

    click.echo(click.style("─── Graph Statistics ───", fg="cyan", bold=True))

    # Topological order (if acyclic)
    cycles = detect_cycles(graph)
    if not cycles:
        order = topological_sort(graph)
        click.echo(f"\n  Topological order ({len(order)} nodes):")
        click.echo(f"    {' → '.join(order)}")
    else:
        click.echo(click.style(f"\n  ⚠ Graph has {len(cycles)} cycle(s) — topological sort unavailable.", fg="yellow"))

    # Per-node stats
    if verbose:
        click.echo("\n  Per-node dependency counts:")
        for node in graph.nodes():
            direct = len(graph.neighbors(node.name))
            click.echo(f"    {node.name}: {direct} direct dep(s)")

    st = graph_stats(graph)
    click.echo(f"\n  Total: {st['node_count']} nodes, {st['edge_count']} edges, depth {st['max_depth']}")


# ── scc ──────────────────────────────────────────────────────


@main.command()
@click.argument("file")
def scc(file: str) -> None:
    """Find strongly connected components (tightly-coupled clusters) in FILE."""
    graph, _ = _load_graph(file)
    components = strongly_connected_components(graph)

    non_trivial = [c for c in components if len(c) > 1]

    if not non_trivial:
        click.echo(click.style("✓ No tightly-coupled clusters found.", fg="green", bold=True))
        click.echo(f"  All {len(components)} components are independent.")
    else:
        click.echo(click.style(f"⚠ Found {len(non_trivial)} tightly-coupled cluster(s):", fg="red", bold=True))
        for i, comp in enumerate(non_trivial, 1):
            click.echo(f"  {i}. [{len(comp)} nodes] {' ↔ '.join(comp)}")
        click.echo(f"\n  + {len(components) - len(non_trivial)} independent node(s)")
