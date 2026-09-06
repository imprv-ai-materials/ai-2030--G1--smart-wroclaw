/* Annotator template for the REPORT_AGENT dataset — 2-column case.

   Input   — the resident's message this turn (prior draft / form answers, when the
             case has them, are shown read-only beneath it — they set up the turn).
   Output  — the gold outcome of plan_turn: which required fields are still missing,
             and whether the draft is ready to confirm. Scored by
             `evaluations/completion.yaml`.

   Run:  python .annotator/annotate.py api/api/ai/report_agent/datasets/annotate.template.js api/api/ai/report_agent/datasets/report.jsonl */

const FIELDS = ["type", "title", "description", "location", "category", "subtype", "starts_at"];
const READY = ["false", "true"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Report Agent Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return { id: "new-case", text: "", prior_draft: null, fields: null, expected_missing: [], expected_ready: false, difficulty: "medium", note: "" };
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
      h("label", { class: "field" }, "Message — the resident's turn"),
      w.text(row.text, (v) => ctx.persist((r) => (r.text = v)), { rows: 6, placeholder: "np. Zgłaszam awarię oświetlenia…" }),
    );
    // Turn setup (read-only): the draft accumulated so far + this turn's form answers.
    if (row.prior_draft || row.fields) {
      host.append(
        h("label", { class: "field" }, "Turn setup (read-only)"),
        h("pre", { class: "pane-hint", style: "white-space:pre-wrap" },
          "prior_draft = " + JSON.stringify(row.prior_draft) + "\nfields = " + JSON.stringify(row.fields)),
      );
    }
    host.append(h("p", { class: "pane-hint" }, "plan_turn merges: prior_draft ⊕ extraction(message) ⊕ fields."));
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    row.expected_missing = row.expected_missing || [];
    host.append(
      h("label", { class: "field" }, "Expected missing fields"),
      w.tags(row.expected_missing, (v) => ctx.persist((r) => (r.expected_missing = v)), { placeholder: "add field…" }),
      h("p", { class: "pane-hint" }, "One of: " + FIELDS.join(" · ")),
      h("label", { class: "field" }, "Ready to confirm?"),
      w.select(String(row.expected_ready), READY, (v) => ctx.mutate((r) => (r.expected_ready = v === "true")), { allowEmpty: false }),
    );
  },
};
