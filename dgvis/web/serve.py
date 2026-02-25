"""Lightweight HTTP server for the dgvis web dashboard."""

from __future__ import annotations

import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from dgvis.analyzer import (
    compute_depth,
    detect_cycles,
    strongly_connected_components,
)
from dgvis.exporter import export_json
from dgvis.graph import Graph


_WEB_DIR = Path(__file__).parent
_TEMPLATE = _WEB_DIR / "index.html"
_PLACEHOLDER = "/*GRAPH_DATA_PLACEHOLDER*/"


def _build_graph_json(graph: Graph) -> str:
    """Build the full JSON payload that the web UI expects.

    Extends the standard export_json with metadata (depth, cycles, SCCs, etc.)
    that the UI uses for coloring and highlighting.
    """
    # Base JSON from exporter
    raw = export_json(graph)
    data = json.loads(raw)

    # Compute extra metadata
    roots = graph.roots()
    leaves = [n for n in graph.node_names() if len(graph.neighbors(n)) == 0]
    depths = compute_depth(graph, roots[0]) if roots else {}
    cycles = detect_cycles(graph)
    sccs = strongly_connected_components(graph)
    non_trivial_sccs = [c for c in sccs if len(c) > 1]

    # Attach depth to each node
    for node_entry in data["nodes"]:
        node_entry["depth"] = depths.get(node_entry["name"], 0)

    data["meta"] = {
        "max_depth": max(depths.values()) if depths else 0,
        "cycles": [[n for n in cycle] for cycle in cycles],
        "sccs": [[n for n in comp] for comp in non_trivial_sccs],
        "roots": roots,
        "leaves": leaves,
    }

    return json.dumps(data)


def render_html(graph: Graph) -> str:
    """Render the index.html template with graph data injected."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    graph_json = _build_graph_json(graph)
    # Replace the placeholder JSON with real data
    return template.replace(
        _PLACEHOLDER + '{"nodes":[],"edges":[],"stats":{"node_count":0,"edge_count":0},"meta":{"max_depth":0,"cycles":[],"sccs":[],"roots":[],"leaves":[]}}',
        graph_json,
    )


def serve(graph: Graph, port: int = 8080, open_browser: bool = True) -> None:
    """Start a local HTTP server serving the graph dashboard.

    Args:
        graph: The dependency graph to visualize.
        port: Port to listen on (default 8080).
        open_browser: Whether to auto-open the browser.
    """
    html_content = render_html(graph)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content.encode())))
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        def log_message(self, fmt, *args) -> None:
            # Suppress default logging noise
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"

    print(f"⬡ dgvis web dashboard")
    print(f"  ➜ {url}")
    print(f"  Press Ctrl+C to stop\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped.")
    finally:
        server.server_close()
