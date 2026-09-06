/* Annotator template for the GUARDRAILS dataset — 2-column case.

   Input   — the resident's raw message.
   Output  — the gold decision: a `reason` code, from which `allow` follows
             (ok ⇒ allow; anything else ⇒ refuse). This is exactly what
             `evaluations/topical.yaml` scores (allow-flag accuracy).

   Run:  python .annotator/annotate.py api/api/ai/guardrails_agent/datasets/annotate.template.js api/api/ai/guardrails_agent/datasets/guardrails.jsonl */

const REASONS = ["ok", "off_topic", "too_long", "blocked_content", "empty"];
const DIFFICULTY = ["easy", "medium", "hard"];

export const meta = {
  title: "Annotating the Guardrails Dataset",
  caseName: (r) => r.id || "(unnamed)",
};

export function newRow() {
  return { id: "new-case", text: "", allow: true, reason: "ok", difficulty: "medium", note: "" };
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
      h("label", { class: "field" }, "Message — the resident's raw input"),
      w.text(row.text, (v) => ctx.persist((r) => (r.text = v)), { rows: 8, placeholder: "np. Podaj przepis na naleśniki…" }),
      h("p", { class: "pane-hint" }, "The only input. The gate decides accept/refuse before any tool runs."),
    );
  },

  output(host, ctx) {
    const { row, w, h } = ctx;
    host.append(
      h("label", { class: "field" }, "Decision (reason ⇒ allow)"),
      // `allow` is derived from `reason` so the two can never disagree in the gold.
      w.select(row.reason, REASONS, (v) => ctx.mutate((r) => { r.reason = v; r.allow = v === "ok"; }), { allowEmpty: false }),
      h("p", { class: "pane-hint" }, "ok = allow · off_topic / blocked_content / too_long / empty = refuse."),
    );
  },
};
