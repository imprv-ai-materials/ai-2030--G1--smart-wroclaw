#!/usr/bin/env python3
"""Idempotently PRELOAD every eval dataset into Label Studio as its own project.

For each ``<EVAL_ROOT>/<agent>/data/`` folder that contains BOTH
``label_studio_config.xml`` (the labelling interface) and
``label_studio_import.json`` (the pre-annotated tasks), this:

  1. creates a project titled ``eval:<agent>`` with that labelling config
     (skipped if a project with the same title already exists), then
  2. imports the tasks — but ONLY if the project currently has zero tasks, so
     re-running on every container boot never duplicates data.

That two-level "create if missing / import if empty" guard is what makes this
safe to run as a startup sidecar: the first boot fills Label Studio, later boots
are no-ops. Seed labels ride in as editable *predictions*, so annotators review
and correct rather than label from scratch (see eval/event_extractor/README.md).

Talks to the REST API with stdlib only (urllib) — no SDK/pip needed, so it runs
under the stock label-studio image's Python. Config via env:

  LS_URL     base URL of the server            (default http://label-studio:8080)
  LS_TOKEN   legacy API token (required)        — must match LABEL_STUDIO_USER_TOKEN
  EVAL_ROOT  dir holding <agent>/data/ folders  (default /eval)
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

LS_URL = os.environ.get("LS_URL", "http://label-studio:8080").rstrip("/")
TOKEN = os.environ.get("LS_TOKEN", "")
EVAL_ROOT = os.environ.get("EVAL_ROOT", "/eval")
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, body=None):
    """One REST call. Raises with the server's error body on non-2xx."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(LS_URL + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"[bootstrap] {method} {path} -> HTTP {exc.code}: {detail}")


def wait_ready(timeout_s: int = 180) -> None:
    """Block until /health answers 200 (the server boots for a few seconds)."""
    for _ in range(timeout_s):
        try:
            with urllib.request.urlopen(LS_URL + "/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit(f"[bootstrap] label-studio not ready at {LS_URL} after {timeout_s}s")


def find_project(title: str):
    """Exact-title lookup (the ?title= filter is a substring search, so re-check)."""
    page = 1
    while True:
        res = api("GET", f"/api/projects/?title={title}&page={page}&page_size=100")
        for proj in res.get("results", []):
            if proj["title"] == title:
                return proj
        if not res.get("next"):
            return None
        page += 1


def main() -> None:
    if not TOKEN:
        raise SystemExit("[bootstrap] LS_TOKEN is required")
    wait_ready()

    data_dirs = sorted(glob.glob(os.path.join(EVAL_ROOT, "*", "data")))
    if not data_dirs:
        print(f"[bootstrap] no datasets under {EVAL_ROOT}/*/data — nothing to preload")
        return

    for data_dir in data_dirs:
        agent = os.path.basename(os.path.dirname(data_dir))
        cfg_path = os.path.join(data_dir, "label_studio_config.xml")
        imp_path = os.path.join(data_dir, "label_studio_import.json")
        if not (os.path.exists(cfg_path) and os.path.exists(imp_path)):
            print(f"[bootstrap] {agent}: no label_studio_config.xml + import.json — skipping")
            continue

        title = f"eval:{agent}"
        proj = find_project(title)
        if proj is None:
            with open(cfg_path, encoding="utf-8") as fh:
                label_config = fh.read()
            proj = api("POST", "/api/projects/", {"title": title, "label_config": label_config})
            print(f"[bootstrap] {agent}: created project #{proj['id']} '{title}'")
        else:
            print(f"[bootstrap] {agent}: project #{proj['id']} '{title}' already exists")

        if proj.get("task_number"):
            print(f"[bootstrap] {agent}: {proj['task_number']} tasks already present — skip import")
            continue

        with open(imp_path, encoding="utf-8") as fh:
            tasks = json.load(fh)
        res = api("POST", f"/api/projects/{proj['id']}/import", tasks)
        imported = res.get("task_count", len(tasks)) if isinstance(res, dict) else len(tasks)
        preds = res.get("prediction_count") if isinstance(res, dict) else None
        print(f"[bootstrap] {agent}: imported {imported} tasks"
              + (f", {preds} predictions" if preds is not None else ""))

    print("[bootstrap] done")


if __name__ == "__main__":
    main()
