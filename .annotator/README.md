# `/.annotator` — a tiny, template-driven dataset annotator

A friendlier, no-dependency way to label the eval datasets that live next to each
agent under `api/api/ai/<agent>/datasets/`. One small Python server + a single-page
UI; the layout and the three "entries" (**context · input · output**) are defined
by a per-dataset **template**, so the same shell annotates any dataset shape.

```
python .annotator/annotate.py <template.js> <dataset.(jsonl|json)>
```

Or via **pypyr**, pointing at an agent + one of its datasets by name (uses that
agent's `datasets/annotate.template.js` automatically):

```bash
pypyr annotate agent=<agent> dataset=<dataset>   # e.g. agent=guardrails_agent dataset=guardrails
pypyr annotate agent=main_agent dataset=queries port=7901
```

Examples:

```bash
# Search ranking dataset — Context = searchable corpus, Output = ordered buckets
python .annotator/annotate.py \
  api/api/ai/main_agent/datasets/annotate.template.js \
  api/api/ai/main_agent/datasets/queries.jsonl

# Extractor dataset — 2 columns (no context): report → gold category
python .annotator/annotate.py \
  api/api/ai/event_extractor/datasets/annotate.template.js \
  api/api/ai/event_extractor/datasets/dev.jsonl
```

It opens `http://127.0.0.1:7900/`. **Every edit autosaves** straight back to the
dataset file, atomically (temp file + rename), keeping a one-time `<file>.bak` the
first time it writes. Stdlib only — no pip installs. Binds to localhost and only
reads files inside the dataset's own directory.

## The UI (the sketch, made real)

```
┌ dataset name ─────────────────────────────────────────────  [ all | dev | test ]  saved ✓ ┐
├ id: ____  difficulty ▾  split ▾  note: __________________________________________________  ┤  ← case meta (header)
├──────────┬───────────────────┬──────────────────┬──────────────────────────────────────────┤
│ cases    │ CONTEXT           │ INPUT            │ EXPECTED OUTPUT                            │
│ (by name,│ searchable event  │ the naked        │ ① expected extraction (type/cat/…)        │
│ hideable)│ cards, + buttons  │ free-text query  │ ② expected results (ordered card buckets) │
└──────────┴───────────────────┴──────────────────┴──────────────────────────────────────────┘
```

The layout mirrors the pipeline — **query → [extractor] → reading → [search] → results** —
so each stage sits where it belongs:

- **Case meta** (header strip) — the annotation bookkeeping (`id`, `difficulty`,
  `split`, `note`). Not part of the pipeline, so it's kept out of the columns.
- **Case list** (left) — every row by name, with a split dot + difficulty chip;
  toggle it with **☰**. `+ new` appends a blank case from the template.
- **Context** — the corpus, searchable; each card has quick `+bucket` buttons and
  is draggable. Adding a card refreshes only the Output column, so the search box
  and scroll stay put across many adds.
- **Input** — *pure input*: just the resident's naked free-text message.
- **Expected output** — the two things the pipeline should produce: ① the
  extractor's structured **reading**, then ② the search **results** as ordered
  buckets. Reorder by drag or ↑/↓, remove with ×, move between buckets by dragging.
  An event lives in at most one bucket.

## Writing a template

A template is a plain **ES module**. It never talks to the server — it builds DOM
from the widget kit on `ctx` and calls `ctx.mutate()` / `ctx.persist()`.

```js
export const meta = {
  title: "Annotating the X Dataset",
  caseName: (row) => row.id,       // left-list label
  splitField: "split",             // powers the all/dev/test filter (optional)
  aux: { corpus: "corpus.jsonl" }, // sibling files to load → ctx.aux.corpus
};

export function newRow() { return { id: "new", /* … blank case … */ }; }

export const panes = {
  header(host, ctx)  { /* optional — case-meta strip above the columns */ },
  context(host, ctx) { /* optional — omit for a 2-column layout */ },
  input(host, ctx)   { /* the pure input */ },
  output(host, ctx)  { /* what the pipeline should produce */ },
};
```

`ctx` gives you:

| member | use |
|--------|-----|
| `ctx.row` / `ctx.rows` | the current case / all cases |
| `ctx.aux.<name>` | a loaded auxiliary file (from `meta.aux`) |
| `ctx.index(auxName, key)` | a `Map` of that aux keyed by a field (e.g. `ext_id`) |
| `ctx.persist(fn)` | apply an in-place field edit + save, **no re-render** (keeps focus) |
| `ctx.mutate(fn, target?)` | apply a structural change + save + re-render a target (`'self'` \| `'header'` \| `'context'` \| `'input'` \| `'output'` \| `'all'`) |
| `ctx.refreshShell()` | re-draw the case list + split filter after a meta edit (id/split/difficulty) |
| `ctx.h(tag, props, …kids)` | a 1-line DOM helper |
| `ctx.w` | the widget kit ↓ |

Widget kit (`ctx.w`):

- `field(label, control, {grow})` — a compact labelled group for the header strip
- `text(value, onChange, {rows, placeholder})` · `line(value, onChange, {placeholder})`
- `select(value, options, onChange, {allowEmpty})`
- `tags(values, onChange, {placeholder})` — keyword chips
- `searchCards({items, card, actions, placeholder})` — the searchable Context list;
  `card(item) -> {id, title, sub, badges}`, `actions:[{label, title, on(item)}]`
- `bucket({title, ids, resolve, onChange, accent})` — one ordered Output bucket;
  `resolve(id) -> {title, sub}`, `onChange(newIds)` on every edit

See `api/api/ai/main_agent/datasets/annotate.template.js` (full 4-column case) and
`api/api/ai/event_extractor/datasets/annotate.template.js` (2-column case) as
worked examples.

## Why this instead of Label Studio?

Label Studio is powerful but heavy: a config XML, a running service, an
import/export round-trip, and a UI that doesn't map cleanly onto "rank these cards
into buckets for this query." This annotator is ~1 file + a ~40-line template,
edits the dataset **in place**, and shapes the panes to the task — so labelling the
search gold is drag-a-card-into-relevant instead of translating the task into a
generic labelling schema.
```
