# `/.er_explorer` — an interactive viewer for the database ER diagram

`pypyr render_er` gives you a static `docs/db_er.svg` — fine for a glance, painful
for a real schema (no zoom, no filter, everything on one sheet). This is the
interactive counterpart: one small Python server + a single-page app that
**pans, zooms, filters, and inspects** the same schema in the browser. Same
spirit as [`/.annotator`](../.annotator) — stdlib-only server, no pip installs;
the drawing libraries are **vendored** under `static/vendor/` so it works
offline.

```bash
python .er_explorer/explore.py                    # docs/db_er.er.json (default)
python .er_explorer/explore.py docs/db_er.mmd      # a Mermaid file works too
python .er_explorer/explore.py docs/schema.er.json --port 7911
```

Or via **pypyr**:

```bash
pypyr er_explorer                                  # default diagram
pypyr er_explorer diagram=docs/db_er.mmd port=7911
```

It opens `http://127.0.0.1:7910/`. Read-only — nothing is written, and the
server binds to localhost.

## The UI

```
┌ db_er.er.json  8 tables · 7 rels ──── layout ▾  ↻  − +  ⤢fit   □compact ☑fuzzy ┐
├──────────────┬──────────────────────────────────────────────┬─────────────────┤
│ filter…      │                                              │  chat_messages  │  ← inspector
│ ☑ agent_runs │     ┌ chat_messages ┐      ┌ users ┐          │  COLUMNS · 6    │    (on select)
│ ☑ users    8 │     │ FK conv._id   │──────│ PK id │          │  PK id   bigint │
│ ☑ …          │     │ PK id         │      └───────┘          │  FK conv…       │
│              │     └───────────────┘                         │  REFERENCES · 1 │
│  legend      │        organic / layered auto-layout          │  REFERENCED BY  │
└──────────────┴──────────────────────────────────────────────┴─────────────────┘
```

- **Pan / zoom** — drag the canvas, scroll to zoom; `⤢ fit` (or press **F**)
  frames everything; `−`/`+` step the zoom.
- **Auto-layout** — pick **fCoSE** (organic force-directed), **Dagre**
  (layered, left→right or top→bottom), **Concentric**, or **Grid**; `↻ layout`
  re-runs it. Drag any table to nudge it.
- **Filter** — the search box matches table *and* column names, hiding the rest;
  the checkboxes toggle tables individually (`all` / `none` for bulk).
- **Focus** — click a table (canvas or list) to spotlight its neighbourhood and
  dim the rest; the highlighted edges show their **crow's-foot cardinality**
  (`1`, `0..1`, `0..N`, `1..N`) and FK column. Click empty space (or **Esc**) to
  reset.
- **Inspect** — the right panel lists every column with its type and PK/FK/UK
  badge, plus what the table **references** and is **referenced by** (click a
  relationship to jump).
- **compact** collapses cards to headers-only for the big picture; **fuzzy
  links** toggles the inferred (non-FK-constraint) edges, drawn dashed.

## The data format (`.er.json`)

The tool eats the structured JSON that `render_er` now emits alongside the
`.mmd`/`.svg` — parsed once, on the Python side, so the browser doesn't
re-implement the Mermaid grammar. The converter is
[`dev/er_diagram.py`](../dev/er_diagram.py) (the single source of truth: the
pipeline calls it, and this server reuses it to parse a raw `.mmd` on the fly):

```jsonc
{
  "tables": [
    { "name": "agent_runs", "columns": [
      { "name": "id", "type": "bigint", "keys": ["PK"],
        "pk": true, "fk": false, "uk": false, "comment": null } ] }
  ],
  "relationships": [
    { "from": "agent_run_steps", "to": "agent_runs",
      "key": "run_id", "label": "run_id",
      "cardinality": "}o--||", "left": "}o", "right": "||",
      "line": "solid", "constraint": true }
  ]
}
```

`constraint: false` marks the fuzzy `F__` edges that
`add_non_constraint_relationship.py` infers from `*_id` column names (links that
live only in app code); the explorer draws those dashed.

## Libraries

All vendored under `static/vendor/` (loaded in dependency order — see
`static/index.html`):

| library | role |
|---------|------|
| [Cytoscape.js](https://js.cytoscape.org) | graph drawing + built-in zoom / pan / select / filter |
| [cytoscape-fcose](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose) (+ cose-base, layout-base) | organic force-directed auto-layout |
| [cytoscape-dagre](https://github.com/cytoscape/cytoscape.js-dagre) (+ dagre) | layered (hierarchical) auto-layout |
| [cytoscape-node-html-label](https://github.com/kaluginserg/cytoscape-node-html-label) | renders each table as an HTML card (header + typed columns + badges) |

To refresh a pinned version, re-download it into `static/vendor/` (the versions
are in the CDN URLs used to fetch them). Nothing else changes — the server just
serves the files.
