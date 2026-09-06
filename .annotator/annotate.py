"""A tiny, template-driven dataset annotator — a friendlier stand-in for Label
Studio for the eval datasets under `eval/`.

    python .annotator/annotate.py <template.js> <dataset.(jsonl|json)>

    # examples
    python .annotator/annotate.py api/api/ai/main_agent/datasets/annotate.template.js api/api/ai/main_agent/datasets/queries.jsonl
    python .annotator/annotate.py api/api/ai/event_extractor/datasets/annotate.template.js api/api/ai/event_extractor/datasets/dev.jsonl

It serves a small single-page UI on localhost (stdlib only — no pip installs) and
writes every edit straight back to the dataset file, **atomically**, keeping a
one-time `<file>.bak` the first time it touches the file. The layout and the three
"entries" (context / input / output) are defined by the template module, so the
same shell annotates any dataset shape.

Nothing leaves your machine: the server binds to 127.0.0.1 and only reads files
inside the dataset's own directory (for the template's auxiliary corpora).
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"


# ── dataset load / save ──────────────────────────────────────────────────────
class Dataset:
    """A JSON or JSONL file of row objects, loaded into memory and saved back in
    the same format. Saves are atomic (temp file + os.replace) so a crash mid-write
    never truncates the dataset."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.is_jsonl = path.suffix == ".jsonl"
        self.rows = self._load()
        self._backed_up = False
        self._lock = threading.Lock()

    def _load(self) -> list[dict]:
        text = self.path.read_text(encoding="utf-8")
        if self.is_jsonl:
            return [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        data = json.loads(text)
        if not isinstance(data, list):
            raise SystemExit(f"{self.path} must be a JSON array of objects")
        return data

    def dump_text(self, rows: list[dict]) -> str:
        if self.is_jsonl:
            return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"

    def save(self, rows: list[dict]) -> None:
        with self._lock:
            if not self._backed_up:
                bak = self.path.with_suffix(self.path.suffix + ".bak")
                if not bak.exists():
                    bak.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
                self._backed_up = True
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(self.dump_text(rows), encoding="utf-8")
            os.replace(tmp, self.path)  # atomic on POSIX + Windows
            self.rows = rows


def _read_aux(dataset_dir: Path, name: str) -> list[dict]:
    """Load a sibling data file (e.g. the search corpus) named by the template.
    Confined to the dataset's own directory — no path traversal."""
    target = (dataset_dir / name).resolve()
    if dataset_dir.resolve() not in target.parents and target != dataset_dir.resolve():
        raise PermissionError("aux file must live in the dataset directory")
    text = target.read_text(encoding="utf-8")
    if target.suffix == ".jsonl":
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    return json.loads(text)


# ── HTTP server ──────────────────────────────────────────────────────────────
def make_handler(dataset: Dataset, template_path: Path):
    dataset_dir = dataset.path.parent

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

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _file(self, path: Path, ctype: str) -> None:
            try:
                self._send(200, path.read_bytes(), ctype)
            except FileNotFoundError:
                self._send(404, b"not found", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path)
            p = route.path
            if p == "/":
                self._file(STATIC / "index.html", "text/html; charset=utf-8")
            elif p == "/static/app.js":
                self._file(STATIC / "app.js", "application/javascript; charset=utf-8")
            elif p == "/static/app.css":
                self._file(STATIC / "app.css", "text/css; charset=utf-8")
            elif p == "/template.js":
                self._file(template_path, "application/javascript; charset=utf-8")
            elif p == "/api/state":
                self._json({
                    "path": str(dataset.path),
                    "name": dataset.path.name,
                    "format": "jsonl" if dataset.is_jsonl else "json",
                    "rows": dataset.rows,
                })
            elif p == "/api/aux":
                name = parse_qs(route.query).get("name", [""])[0]
                try:
                    self._json(_read_aux(dataset_dir, name))
                except (FileNotFoundError, PermissionError) as exc:
                    self._json({"error": str(exc)}, code=400)
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/save":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            rows = payload.get("rows")
            if not isinstance(rows, list):
                self._json({"error": "rows must be a list"}, code=400)
                return
            dataset.save(rows)
            self._json({"ok": True, "count": len(rows)})

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", type=Path, help="path to the <name>.template.js module")
    ap.add_argument("dataset", type=Path, help="path to the .jsonl / .json dataset to edit")
    ap.add_argument("--port", type=int, default=7900)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()

    for path in (args.template, args.dataset):
        if not path.is_file():
            raise SystemExit(f"not found: {path}")

    dataset = Dataset(args.dataset)
    handler = make_handler(dataset, args.template.resolve())
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"annotating {dataset.path}  ({len(dataset.rows)} rows)")
    print(f"open {url}   —   edits autosave to the file (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
