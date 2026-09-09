"""Convert a mermerd-generated Mermaid ER diagram (`.mmd`) into the structured
JSON the `.er_explorer` tool consumes (`.er.json`).

The `.mmd` is great for `mmdc` (→ static SVG) but awful to drive an interactive
canvas from: it's a text grammar a browser would have to re-parse, and the
column key flags (`PK`/`FK`/`UK`) and the crow's-foot cardinality are baked into
punctuation. This pass parses it once, on the Python side, into an explicit shape
so the front-end can just render:

    {
      "source": "docs/db_er.mmd",
      "table_count": 8, "relationship_count": 7,
      "tables": [
        {"name": "agent_runs", "columns": [
          {"name": "id", "type": "bigint", "keys": ["PK"],
           "pk": true, "fk": false, "uk": false, "comment": null}, ...]}
      ],
      "relationships": [
        {"from": "agent_run_steps", "to": "agent_runs",
         "key": "run_id", "label": "run_id",
         "cardinality": "}o--||", "left": "}o", "right": "||",
         "line": "solid", "constraint": true}
      ]
    }

`constraint` is False for the fuzzy `F__`-prefixed edges that
`add_non_constraint_relationship.py` appends (links that live only in app code);
the tool draws those dashed. Run standalone, or as the JSON step of the
`render_er` pipeline:

    python dev/er_diagram.py docs/db_er.mmd docs/db_er.er.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# A column line inside a `table { ... }` block, e.g.
#   `bigint id PK`  ·  `text component`  ·  `text token_hash UK "unique"`.
# type + name are required; the key flags and a quoted comment are optional.
_COLUMN_RE = re.compile(r"^(\S+)\s+(\S+)\s*(.*)$")
_COMMENT_RE = re.compile(r'"([^"]*)"')

# A relationship line, e.g. `agent_run_steps }o--|| agent_runs : "run_id"`.
_REL_RE = re.compile(r'^(\w+)\s+([|}{o.\-]+)\s+(\w+)\s*:\s*"([^"]+)"\s*$')
# Split a crow's-foot cardinality (`}o--||`) into left / line / right.
_CARD_RE = re.compile(r"^([|}{o]+)(--|\.\.)([|}{o]+)$")


def _parse_column(line: str) -> Optional[Dict[str, Any]]:
    m = _COLUMN_RE.match(line.strip())
    if not m:
        return None
    col_type, name, rest = m.group(1), m.group(2), m.group(3).strip()

    comment: Optional[str] = None
    cm = _COMMENT_RE.search(rest)
    if cm:
        comment = cm.group(1)
        rest = (rest[: cm.start()] + rest[cm.end() :]).strip()

    keys = [k.upper() for k in re.split(r"[,\s]+", rest) if k]
    return {
        "name": name,
        "type": col_type,
        "keys": keys,
        "pk": "PK" in keys,
        "fk": "FK" in keys,
        "uk": "UK" in keys,
        "comment": comment,
    }


def _parse_relationship(line: str) -> Optional[Dict[str, Any]]:
    m = _REL_RE.match(line.strip())
    if not m:
        return None
    from_entity, cardinality, to_entity, key = m.groups()

    left, right, line_style = "", "", "solid"
    cm = _CARD_RE.match(cardinality)
    if cm:
        left, sep, right = cm.groups()
        line_style = "dashed" if sep == ".." else "solid"

    constraint = not key.startswith("F__")
    return {
        "from": from_entity,
        "to": to_entity,
        "key": key,
        "label": key[3:] if not constraint else key,  # strip the F__ prefix for display
        "cardinality": cardinality,
        "left": left,
        "right": right,
        "line": line_style,
        "constraint": constraint,
    }


def parse_mmd(text: str, source: Optional[str] = None) -> Dict[str, Any]:
    """Parse a mermerd `erDiagram` into the `.er.json` shape (see module docstring)."""
    tables: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []

    current: Optional[Dict[str, Any]] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "erDiagram" or line.startswith("%%"):
            continue

        if current is not None:
            if line == "}":
                tables.append(current)
                current = None
            else:
                col = _parse_column(line)
                if col:
                    current["columns"].append(col)
            continue

        # A `name {` opens a table block (the brace may sit on the same line).
        opener = re.match(r"^(\w+)\s*\{$", line)
        if opener:
            current = {"name": opener.group(1), "columns": []}
            continue

        rel = _parse_relationship(line)
        if rel:
            relationships.append(rel)

    return {
        "source": source,
        "table_count": len(tables),
        "relationship_count": len(relationships),
        "tables": tables,
        "relationships": relationships,
    }


def convert(mmd_path: Path, out_path: Path) -> Dict[str, Any]:
    if not mmd_path.is_file():
        raise FileNotFoundError(f"Mermaid file not found: {mmd_path}")
    data = parse_mmd(mmd_path.read_text(encoding="utf-8"), source=str(mmd_path))
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a Mermaid ER diagram (.mmd) to .er.json")
    ap.add_argument("mmd_file", type=Path, help="input Mermaid ER diagram (.mmd)")
    ap.add_argument("out_file", type=Path, nargs="?", help="output .er.json (default: <mmd>.er.json)")
    args = ap.parse_args()

    out = args.out_file or args.mmd_file.with_suffix(".er.json")
    data = convert(args.mmd_file, out)
    print(f"wrote {out}  ({data['table_count']} tables, {data['relationship_count']} relationships)")


if __name__ == "__main__":
    main()
