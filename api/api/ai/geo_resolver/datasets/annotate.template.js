/* Annotator template for the GEO_RESOLVER dataset — 2-column case.

   Input   — the location mention as it appears in a message.
   Output  — the gold scope: a district, or "near me" (needs_user_location) + a
             radius, or "not resolvable" (expected = null). Scored by
             `evaluations/geocoding.yaml`.

   Run:  python .annotator/annotate.py api/api/ai/geo_resolver/datasets/annotate.template.js api/api/ai/geo_resolver/datasets/geo.jsonl */

const RESOLVABLE = ["yes", "no"];
const NEEDS_LOC = ["false", "true"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Geo Resolver Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return { id: "new-case", text: "", expected: { district: null, needs_user_location: false, radius_m: null }, difficulty: "medium", note: "" };
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
      h("label", { class: "field" }, "Location mention"),
      w.line(row.text, (v) => ctx.persist((r) => (r.text = v)), { placeholder: "np. na Krzykach / w mojej okolicy / ul. Legnicka 58" }),
      h("p", { class: "pane-hint" }, "The raw location phrase the resolver must turn into a scope."),
    );
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    const e = row.expected || {};
    const resolvable = row.expected != null;

    host.append(
      h("label", { class: "field" }, "Resolvable?"),
      w.select(resolvable ? "yes" : "no", RESOLVABLE, (v) => ctx.mutate((r) => {
        r.expected = v === "yes" ? { district: null, needs_user_location: false, radius_m: null } : null;
      }), { allowEmpty: false }),
    );
    if (!resolvable) {
      host.append(h("p", { class: "pane-hint" }, "expected = null — the tool should return no scope."));
      return;
    }
    host.append(
      h("label", { class: "field" }, "District"),
      w.line(e.district || "", (v) => ctx.persist(() => (e.district = v || null)), { placeholder: "np. Krzyki (puste dla adresu / „near me”)" }),
      h("label", { class: "field" }, "Needs user location? („near me”)"),
      w.select(String(!!e.needs_user_location), NEEDS_LOC, (v) => ctx.persist(() => (e.needs_user_location = v === "true")), { allowEmpty: false }),
      h("label", { class: "field" }, "Radius (m)"),
      w.line(e.radius_m == null ? "" : String(e.radius_m), (v) => ctx.persist(() => (e.radius_m = v ? Number(v) : null)), { placeholder: "np. 1500" }),
    );
  },
};
