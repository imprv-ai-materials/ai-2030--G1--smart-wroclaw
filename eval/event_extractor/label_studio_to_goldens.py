"""Convert a Label Studio JSON export back into the dataset JSONL.

    python eval/category_agent/label_studio_to_goldens.py export.json [--out data/category_dataset.jsonl] [--split-out]

After you review/enhance the tasks in Label Studio, export the project as JSON
(the full export — an array of task objects) and run this to fold your human
labels back into the eval dataset. There is no official LS→DeepEval adapter, so
this is the ~40-line mapper the research recommended.

Mapping (Label Studio → our row):
  data.text                          → text
  annotation `primary`  choices[0]   → primary_category
  annotation `secondary` choices     → secondary_categories
  annotation `notes` textarea        → note
  meta.id / meta.split / difficulty  → carried through if present
We keep the GROUND-TRUTH annotation when one is starred; otherwise the most
recent annotation. Tasks with no annotation are skipped (still just predictions).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CATEGORIES = {"WATER", "ROADS", "WASTE", "GREENERY", "LIGHTING", "PUBLIC_TRANSPORT", "OTHER"}


def _pick_annotation(task: dict) -> dict | None:
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not anns:
        return None
    gt = [a for a in anns if a.get("ground_truth")]
    return (gt or anns)[-1]


def _results_by_name(annotation: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in annotation.get("result", []):
        out[r.get("from_name", "")] = r.get("value", {})
    return out


def convert(export_path: Path) -> list[dict]:
    tasks = json.loads(export_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    skipped = 0
    for task in tasks:
        ann = _pick_annotation(task)
        if ann is None:
            skipped += 1
            continue
        vals = _results_by_name(ann)
        primary_choices = vals.get("primary", {}).get("choices", [])
        if not primary_choices:
            skipped += 1
            continue
        primary = primary_choices[0].strip().upper()
        if primary not in CATEGORIES:
            skipped += 1
            continue
        secondary = [
            c.strip().upper()
            for c in vals.get("secondary", {}).get("choices", [])
            if c.strip().upper() in CATEGORIES and c.strip().upper() != primary
        ]
        notes = vals.get("notes", {}).get("text") or [""]
        meta = task.get("meta", {}) or {}
        rows.append(
            {
                "id": meta.get("id", f"ls-{task.get('id', len(rows))}"),
                "text": task.get("data", {}).get("text", ""),
                "primary_category": primary,
                "secondary_categories": secondary,
                "difficulty": meta.get("difficulty", ""),
                "note": notes[0] if notes else "",
                "split": meta.get("split", "dev"),
            }
        )
    if skipped:
        print(f"  skipped {skipped} task(s) with no usable annotation")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path, help="Label Studio JSON export file")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data" / "category_dataset.jsonl")
    ap.add_argument("--split-out", action="store_true", help="also (re)write dev.jsonl / test.jsonl")
    args = ap.parse_args()

    rows = convert(args.export)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows → {args.out}")

    if args.split_out:
        for split in ("dev", "test"):
            sub = [r for r in rows if r.get("split") == split]
            p = args.out.parent / f"{split}.jsonl"
            with p.open("w", encoding="utf-8") as f:
                for r in sub:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"  {split}: {len(sub)} → {p}")


if __name__ == "__main__":
    main()
