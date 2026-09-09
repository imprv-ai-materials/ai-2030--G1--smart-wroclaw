"""A standalone, zero-install viewer for the database ER diagram — pan, zoom,
filter, and inspect the schema in the browser instead of squinting at a static
SVG.

    python .er_explorer/explore.py [er.json | er.mmd]

    # examples
    python .er_explorer/explore.py                       # docs/db_er.er.json (default)
    python .er_explorer/explore.py docs/db_er.mmd        # parse a Mermaid file directly
    python .er_explorer/explore.py docs/schema.er.json --port 7911

It serves a small single-page app on localhost (Python stdlib only — no pip
installs; the drawing libraries are vendored under `static/vendor/`). The page
autolays the tables with a real graph-layout engine (Cytoscape.js + fCoSE /
Dagre) and gives you wheel-zoom, drag-pan, a searchable table filter, a
hide-fuzzy-links toggle, click-to-focus a table's neighbourhood, and a column
inspector.

Input is the structured `.er.json` produced by `pypyr render_er` (canonical),
but a mermerd `.mmd` also works — it's parsed on the fly by `dev/er_diagram.py`.
Read-only: nothing is written, and the server binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
ROOT = HERE.parent  # repo module root (where dev/ and docs/ live)

# A tiny table-shaped favicon, served inline so the browser's automatic
# /favicon.ico request doesn't 404.
_FAVICON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<rect x="5" y="4" width="22" height="24" rx="3" fill="#fff" stroke="#2b6cff" stroke-width="2"/>'
    b'<rect x="5" y="4" width="22" height="7" rx="3" fill="#2b6cff"/>'
    b'<line x1="5" y1="17" x2="27" y2="17" stroke="#2b6cff" stroke-width="1.5"/>'
    b'<line x1="5" y1="22" x2="27" y2="22" stroke="#2b6cff" stroke-width="1.5"/></svg>'
)

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".map": "application/json; charset=utf-8",
}


def _load_er_diagram_module():
    """Import the canonical Mermaid→JSON parser from the sibling `dev/` package
    (kept in one place so the tool and the `render_er` pipeline never drift)."""
    mod_path = ROOT / "dev" / "er_diagram.py"
    if not mod_path.is_file():
        raise SystemExit(f"cannot parse .mmd: {mod_path} not found (pass an .er.json instead)")
    spec = importlib.util.spec_from_file_location("er_diagram", mod_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_diagram(path: Path) -> Dict[str, Any]:
    """Load the ER model from either a structured `.er.json` or a raw `.mmd`."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return _load_er_diagram_module().parse_mmd(text, source=str(path))


def resolve_input(arg: str | None) -> Path:
    """Pick the diagram file: the explicit arg, else docs/db_er.er.json, falling
    back to docs/db_er.mmd. Also swaps a missing .er.json for a present .mmd."""
    if arg:
        p = Path(arg)
        if not p.is_file():
            raise SystemExit(f"not found: {p}")
        return p
    for candidate in (ROOT / "docs" / "db_er.er.json", ROOT / "docs" / "db_er.mmd"):
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "no diagram given and docs/db_er.er.json / docs/db_er.mmd are missing — "
        "run `pypyr render_er` first, or pass a path."
    )


def make_handler(diagram: Dict[str, Any], source: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # keep the console quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _static(self, rel: str) -> None:
            """Serve a file under static/, refusing any path traversal outside it."""
            target = (STATIC / rel).resolve()
            if STATIC.resolve() not in target.parents and target != STATIC.resolve():
                self._send(403, b"forbidden", "text/plain")
                return
            try:
                self._send(200, target.read_bytes(), _CTYPES.get(target.suffix, "application/octet-stream"))
            except (FileNotFoundError, IsADirectoryError):
                self._send(404, b"not found", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            p = self.path.split("?", 1)[0]
            if p == "/":
                self._static("index.html")
            elif p == "/favicon.ico":
                self._send(200, _FAVICON, "image/svg+xml")
            elif p == "/api/er":
                self._json(
                    {
                        "source": str(source),
                        "name": source.name,
                        "diagram": diagram,
                    }
                )
            elif p.startswith("/static/"):
                self._static(p[len("/static/") :])
            else:
                self._send(404, b"not found", "text/plain")

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("diagram", nargs="?", help="path to the .er.json (or .mmd) — default docs/db_er.er.json")
    ap.add_argument("--port", type=int, default=7910)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()

    source = resolve_input(args.diagram)
    diagram = load_diagram(source)
    n_tables = diagram.get("table_count", len(diagram.get("tables", [])))
    n_rels = diagram.get("relationship_count", len(diagram.get("relationships", [])))

    handler = make_handler(diagram, source)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"exploring {source}  ({n_tables} tables, {n_rels} relationships)")
    print(f"open {url}   —   pan · zoom · filter   (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
