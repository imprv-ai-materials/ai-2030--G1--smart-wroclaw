/* Annotator template for the EXTRACTOR (category) dataset — the 2-column case
   from the sketch: no context pane, just the input report and the expected label.

   Input   — the resident's open-text report.
   Output  — the gold primary category (one of the closed set) + any secondary
             categories. This is exactly what `metrics.PrimaryCategoryMatchMetric`
             scores, so the labels edited here feed straight into the eval.

   Run:  python .annotator/annotate.py api/api/ai/event_extractor/datasets/annotate.template.js api/api/ai/event_extractor/datasets/dev.jsonl */

const CATEGORIES = ["WATER", "ROADS", "WASTE", "GREENERY", "LIGHTING", "PUBLIC_TRANSPORT", "OTHER"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Extractor Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return { id: "new-case", text: "", primary_category: "OTHER", secondary_categories: [], difficulty: "medium", note: "" };
}

export const panes = {
  // case bookkeeping — lives in the header strip, not in the pipeline columns
  header(host, ctx) {
    const { row, w } = ctx;
    const meta = (fn) => { ctx.persist(fn); ctx.refreshShell(); };
    host.append(
      w.field("Case id", w.line(row.id, (v) => meta((r) => (r.id = v)), { placeholder: "case-id" }), { grow: 2 }),
      w.field("Difficulty", w.select(row.difficulty, DIFFICULTY, (v) => meta((r) => (r.difficulty = v)), { allowEmpty: false })),
      w.field("Note", w.line(row.note, (v) => ctx.persist((r) => (r.note = v)), { placeholder: "labelling rationale…" }), { grow: 5 }),
    );
  },

  // PURE input — only the resident's open-text report.
  input(host, ctx) {
    const { row, w, h } = ctx;
    host.append(
      h("label", { class: "field" }, "Report — the resident's open text"),
      w.text(row.text, (v) => ctx.persist((r) => (r.text = v)), { rows: 8, placeholder: "np. Z hydrantu tryska woda…" }),
      h("p", { class: "pane-hint" }, "This is the only input. The gold category on the right is what the extractor should produce."),
    );
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    row.secondary_categories = row.secondary_categories || [];

    // secondary as toggle chips over the closed category set (minus the primary)
    const chips = h("div", { class: "tags" });
    const drawChips = () => {
      chips.replaceChildren();
      for (const c of CATEGORIES) {
        if (c === row.primary_category) continue;
        const on = row.secondary_categories.includes(c);
        chips.append(h("button", {
          class: "mini-btn" + (on ? "" : ""),
          style: on ? "border-color:var(--accent);background:var(--accent-soft)" : "",
          onclick: () => ctx.mutate((r) => {
            r.secondary_categories = on ? r.secondary_categories.filter((x) => x !== c) : [...r.secondary_categories, c];
          }),
        }, (on ? "✓ " : "") + c));
      }
    };
    drawChips();

    host.append(
      h("label", { class: "field" }, "Primary category"),
      w.select(row.primary_category, CATEGORIES,
        (v) => ctx.mutate((r) => { r.primary_category = v; r.secondary_categories = (r.secondary_categories || []).filter((x) => x !== v); }),
        { allowEmpty: false }),
      h("label", { class: "field" }, "Secondary categories"),
      chips,
    );
  },
};
