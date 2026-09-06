/* Annotator template for the ROUTER dataset — 2-column case.

   Input   — the resident's message (already past guardrails).
   Output  — the gold intent: search | report | analytics. Scored by
             `evaluations/routing.yaml` (intent accuracy).

   Run:  python .annotator/annotate.py api/api/ai/router_agent/datasets/annotate.template.js api/api/ai/router_agent/datasets/router.jsonl */

const INTENTS = ["search", "report", "analytics"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Router Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return { id: "new-case", text: "", intent: "search", difficulty: "medium", note: "" };
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
      h("label", { class: "field" }, "Message — the resident's input"),
      w.text(row.text, (v) => ctx.persist((r) => (r.text = v)), { rows: 8, placeholder: "np. Ile latarni nie świeci w Śródmieściu?" }),
      h("p", { class: "pane-hint" }, "The only input. The router picks exactly one task lane from it."),
    );
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    host.append(
      h("label", { class: "field" }, "Intent"),
      w.select(row.intent, INTENTS, (v) => ctx.mutate((r) => (r.intent = v)), { allowEmpty: false }),
      h("p", { class: "pane-hint" }, "search = find events · report = file a new one · analytics = count / aggregate."),
    );
  },
};
