"""Lightweight HTTP server for the dgvis web dashboard."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from dgvis.analyzer import (
    compute_depth,
    detect_cycles,
    strongly_connected_components,
)
from dgvis.exporter import export_json
from dgvis.graph import Graph, build_graph
from dgvis.parser import parse_file


_WEB_DIR = Path(__file__).parent
_TEMPLATE = _WEB_DIR / "index.html"
_PLACEHOLDER = "/*GRAPH_DATA_PLACEHOLDER*/"


def _build_graph_json(graph: Graph) -> str:
    """Build the full JSON payload that the web UI expects."""
    raw = export_json(graph)
    data = json.loads(raw)

    roots = graph.roots()
    leaves = [n for n in graph.node_names() if len(graph.neighbors(n)) == 0]
    depths = compute_depth(graph, roots[0]) if roots else {}
    cycles = detect_cycles(graph)
    sccs = strongly_connected_components(graph)
    non_trivial_sccs = [c for c in sccs if len(c) > 1]

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
    pattern = re.escape(_PLACEHOLDER) + r'\s*\{[^;]*\}'
    return re.sub(pattern, graph_json, template, count=1)


# ── Auto-reload snippet (injected when --watch is used) ──────

_RELOAD_SCRIPT = """
<script>
// Auto-reload: poll server for changes
(function() {
    let lastHash = '';
    setInterval(async () => {
        try {
            const r = await fetch('/__hash');
            const h = await r.text();
            if (lastHash && h !== lastHash) location.reload();
            lastHash = h;
        } catch(e) {}
    }, 1500);
})();
</script>
"""


def serve(
    graph: Graph,
    port: int = 8080,
    open_browser: bool = True,
    watch_file: str | None = None,
) -> None:
    """Start a local HTTP server serving the graph dashboard.

    Args:
        graph: The dependency graph to visualize.
        port: Port to listen on (default 8080).
        open_browser: Whether to auto-open the browser.
        watch_file: If set, watch this file for changes and auto-reload.
    """
    # Mutable state shared between threads
    state = {
        "html": render_html(graph),
        "hash": "0",
    }

    if watch_file:
        # Inject auto-reload script
        state["html"] = state["html"].replace("</body>", _RELOAD_SCRIPT + "</body>")
        state["hash"] = str(os.path.getmtime(watch_file))

        def _watcher():
            """Poll file for changes and rebuild HTML."""
            last_mtime = os.path.getmtime(watch_file)
            while True:
                time.sleep(1)
                try:
                    mtime = os.path.getmtime(watch_file)
                    if mtime != last_mtime:
                        last_mtime = mtime
                        print("  ↻ File changed, rebuilding...")
                        deps = parse_file(watch_file)
                        new_graph = build_graph(deps)
                        new_html = render_html(new_graph)
                        state["html"] = new_html.replace(
                            "</body>", _RELOAD_SCRIPT + "</body>"
                        )
                        state["hash"] = str(mtime)
                        print("  ✓ Dashboard updated\n")
                except Exception as e:
                    print(f"  ⚠ Watch error: {e}")

        t = threading.Thread(target=_watcher, daemon=True)
        t.start()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/__hash":
                body = state["hash"].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            body = state["html"].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"

    print(f"⬡ dgvis web dashboard")
    print(f"  ➜ {url}")
    if watch_file:
        print(f"  👁 Watching: {watch_file}")
    print(f"  Press Ctrl+C to stop\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped.")
    finally:
        server.server_close()
