/* Annotator template for the SEARCH ranking dataset (../datasets/queries.jsonl).

   Context  — the 38-event corpus, searchable; each card has quick "+bucket" buttons.
   Input    — the resident query + the gold structured reading (type/category/district/keywords).
   Output   — four ordered buckets of event cards (relevant / acceptable / hard_negatives /
              must_exclude). A given event lives in at most one bucket; adding it to one
              removes it from the others. Drag to reorder or to move between buckets.

   Run:  python .annotator/annotate.py api/api/ai/main_agent/datasets/annotate.template.js api/api/ai/main_agent/datasets/queries.jsonl */

const TYPES = ["ISSUE", "ALARM", "VENUE", "PROMOTION", "MISSING_PET", "HAZARD", "OUTAGE", "ROADWORKS", "COMMUNITY"];
const CATEGORIES = ["WATER", "ROADS", "WASTE", "GREENERY", "LIGHTING", "PUBLIC_TRANSPORT", "OTHER"];
const DIFFICULTY = ["easy", "medium", "hard"];
const BUCKETS = [
  { key: "relevant", label: "Relevant (rank at top)", accent: "#2f8f4e" },
  { key: "acceptable", label: "Acceptable (ok to show)", accent: "#8a8a8e" },
  { key: "hard_negatives", label: "Hard negatives (must not crowd top)", accent: "#c8402f" },
  { key: "must_exclude", label: "Must exclude (never surface)", accent: "#111" },
];

export const meta = {
  title: "Annotating the Search Dataset",
  caseName: (r) => r.id || "(unnamed)",
  aux: { corpus: "corpus.jsonl" },
};

export function newRow() {
  return {
    id: "new-query", query: "", intent: "search",
    filters: { type: null, category: null, district: null, keywords: [] },
    relevant: [], acceptable: [], hard_negatives: [], must_exclude: [],
    difficulty: "medium", note: "",
  };
}

// keep an event in at most one bucket. Adding from the Context pane refreshes
// only Output, so the Context search box + scroll stay put across many adds.
function place(ctx, targetKey, id) {
  ctx.mutate((row) => {
    for (const b of BUCKETS) row[b.key] = (row[b.key] || []).filter((x) => x !== id);
    if (targetKey) row[targetKey] = [...(row[targetKey] || []), id];
  }, "output");
}
function setBucket(ctx, key, ids) {
  ctx.mutate((row) => {
    const taken = new Set(ids);
    for (const b of BUCKETS) row[b.key] = b.key === key ? ids : (row[b.key] || []).filter((x) => !taken.has(x));
  });
}

const docCard = (d) => ({
  id: d.ext_id,
  title: `${d.ext_id} · ${d.title}`,
  sub: [d.type, d.category, d.district].filter(Boolean).join(" · "),
  badges: [d.status, d.subtype].filter(Boolean),
});

function section(ctx, num, title, hint) {
  const h = ctx.h;
  return h("div", {},
    h("div", { class: "pane-section" }, h("span", { class: "num" }, String(num)), title),
    hint ? h("p", { class: "pane-hint" }, hint) : null);
}

export const panes = {
  // case bookkeeping — not part of the pipeline, so it lives in the header strip
  header(host, ctx) {
    const { row, w } = ctx;
    const meta = (fn) => { ctx.persist(fn); ctx.refreshShell(); };
    host.append(
      w.field("Case id", w.line(row.id, (v) => meta((r) => (r.id = v)), { placeholder: "query-id" }), { grow: 2 }),
      w.field("Difficulty", w.select(row.difficulty, DIFFICULTY, (v) => meta((r) => (r.difficulty = v)), { allowEmpty: false })),
      w.field("Note", w.line(row.note, (v) => ctx.persist((r) => (r.note = v)), { placeholder: "labelling rationale…" }), { grow: 5 }),
    );
  },

  context(host, ctx) {
    const corpus = ctx.aux.corpus || [];
    host.append(ctx.w.searchCards({
      items: corpus,
      card: docCard,
      placeholder: `search ${corpus.length} events…`,
      actions: [
        { label: "+ relevant", title: "add to relevant", on: (d) => place(ctx, "relevant", d.ext_id) },
        { label: "+ accept", on: (d) => place(ctx, "acceptable", d.ext_id) },
        { label: "+ hard-neg", on: (d) => place(ctx, "hard_negatives", d.ext_id) },
        { label: "+ exclude", on: (d) => place(ctx, "must_exclude", d.ext_id) },
      ],
    }));
  },

  // PURE input — only the resident's naked free-text message.
  input(host, ctx) {
    const { row, w, h } = ctx;
    host.append(
      h("label", { class: "field" }, "Query — the resident's free-text message"),
      w.text(row.query, (v) => ctx.persist((r) => (r.query = v)), { rows: 8, placeholder: "np. Nie ma wody na Krzykach, czy to znana awaria?" }),
      h("p", { class: "pane-hint" }, "This is the only input. Everything on the right is what the pipeline should produce from it."),
    );
  },

  // Two staged outputs: ① what the extractor should read, ② what search returns.
  output(host, ctx) {
    const { row, w, h } = ctx;
    row.filters = row.filters || { type: null, category: null, district: null, keywords: [] };
    const f = row.filters;
    const corpus = ctx.index("corpus", "ext_id");
    const resolve = (id) => {
      const d = corpus.get(id);
      return d ? { title: `${id} · ${d.title}`, sub: [d.type, d.category, d.district].filter(Boolean).join(" · ") }
               : { title: id, sub: "⚠ not in corpus" };
    };

    host.append(
      section(ctx, 1, "Expected extraction", "What the extractor should read from the query."),
      h("label", { class: "field" }, "Type"),
      w.select(f.type, TYPES, (v) => ctx.persist(() => (f.type = v))),
      h("label", { class: "field" }, "Category"),
      w.select(f.category, CATEGORIES, (v) => ctx.persist(() => (f.category = v))),
      h("label", { class: "field" }, "District"),
      w.line(f.district, (v) => ctx.persist(() => (f.district = v || null)), { placeholder: "np. Krzyki" }),
      h("label", { class: "field" }, "Keywords"),
      w.tags(f.keywords, (v) => ctx.persist(() => (f.keywords = v)), { placeholder: "add keyword…" }),
      section(ctx, 2, "Expected results", "Events search should return — drag from Context or use the + buttons."),
    );
    for (const b of BUCKETS) {
      host.append(w.bucket({
        title: b.label, accent: b.accent, ids: row[b.key] || [], resolve,
        onChange: (ids) => setBucket(ctx, b.key, ids),
      }));
    }
  },
};
