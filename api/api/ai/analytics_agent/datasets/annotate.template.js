/* Annotator template for the ANALYTICS_AGENT dataset — 2-column case.

   Input   — the resident's "how many …" question.
   Output  — the gold reading the counter needs: the event filters (type/category/
             district/keywords) AND the geo scope (a district, or a radius in metres
             around the user's location). Scored by `evaluations/counting.yaml`.

   Run:  python .annotator/annotate.py api/api/ai/analytics_agent/datasets/annotate.template.js api/api/ai/analytics_agent/datasets/analytics.jsonl */

const TYPES = ["ISSUE", "ALARM", "VENUE", "PROMOTION", "MISSING_PET", "HAZARD", "OUTAGE", "ROADWORKS", "COMMUNITY"];
const CATEGORIES = ["WATER", "ROADS", "WASTE", "GREENERY", "LIGHTING", "PUBLIC_TRANSPORT", "OTHER"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Analytics Agent Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return {
    id: "new-case", question: "",
    filters: { type: null, category: null, district: null, keywords: [] },
    scope: null, difficulty: "medium", note: "",
  };
}

export const panes = {
  header(host, ctx) {
    const { row, w } = ctx;
    const meta = (fn) => { ctx.persist(fn); ctx.refreshShell(); };
    host.append(
      w.field("Case id", w.line(row.id, (v) => meta((r) => (r.id = v)), { placeholder: "case-id" }), { grow: 2 }),
      w.field("Difficulty", w.select(row.difficulty, DIFFICULTY, (v) => meta((r) => (r.difficulty = v)), { allowEmpty: false })),
      w.field("Note", w.line(row.note, (v) => ctx.persist((r) => (r.note = v)), { placeholder: "labelling rationale…" }), { grow: 5 }),
    );
  },

  input(host, ctx) {
    const { row, w, h } = ctx;
    host.append(
      h("label", { class: "field" }, "Question — the resident's count query"),
      w.text(row.question, (v) => ctx.persist((r) => (r.question = v)), { rows: 6, placeholder: "np. Ile latarni nie świeci w Śródmieściu?" }),
      h("p", { class: "pane-hint" }, "The only input. The right side is what the counter should resolve it to."),
    );
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    row.filters = row.filters || { type: null, category: null, district: null, keywords: [] };
    const f = row.filters;
    const scope = row.scope || {};
    const setScope = (fn) => ctx.persist((r) => {
      r.scope = r.scope || {};
      fn(r.scope);
      // drop an all-empty scope back to null so "whole city" stays explicit
      if (!r.scope.district && r.scope.radius_m == null && r.scope.lat == null) r.scope = null;
    });

    host.append(
      h("div", { class: "pane-section" }, h("span", { class: "num" }, "1"), "Event filters"),
      h("label", { class: "field" }, "Type"),
      w.select(f.type, TYPES, (v) => ctx.persist(() => (f.type = v))),
      h("label", { class: "field" }, "Category"),
      w.select(f.category, CATEGORIES, (v) => ctx.persist(() => (f.category = v))),
      h("label", { class: "field" }, "District (filter)"),
      w.line(f.district, (v) => ctx.persist(() => (f.district = v || null)), { placeholder: "np. Krzyki" }),
      h("label", { class: "field" }, "Keywords"),
      w.tags(f.keywords, (v) => ctx.persist(() => (f.keywords = v)), { placeholder: "add keyword…" }),
      h("div", { class: "pane-section" }, h("span", { class: "num" }, "2"), "Geo scope"),
      h("label", { class: "field" }, "Scope district"),
      w.line(scope.district || "", (v) => setScope((s) => (s.district = v || undefined)), { placeholder: "np. Śródmieście" }),
      h("label", { class: "field" }, "Scope radius (m)"),
      w.line(scope.radius_m == null ? "" : String(scope.radius_m),
        (v) => setScope((s) => (s.radius_m = v ? Number(v) : undefined)), { placeholder: "np. 1500 (dla „moja okolica”)" }),
      h("p", { class: "pane-hint" }, "Leave both scope fields empty for a whole-city count (scope = null)."),
    );
  },
};
