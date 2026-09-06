/* The annotator shell: load the dataset + the template module, render the
   sketch (case list · context · input · output), and autosave every edit.

   A template is an ES module with:
     export const meta   = { title, caseName(row), aux?: {name: "file"} }
     export const panes  = { context?(host, ctx), input(host, ctx), output(host, ctx) }
     export function newRow()            // a blank case for the "+ new" button
   Each pane builds DOM into `host` using the widget kit on `ctx`. Panes never
   touch the server — they call ctx.mutate() (structural change → re-render) or
   ctx.persist() (in-place field edit → save only). */

// ── module-level drag payload (context card → bucket, and within buckets) ────
let DRAG = null;

// ── tiny DOM helper ──────────────────────────────────────────────────────────
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

// ── app state ────────────────────────────────────────────────────────────────
const state = {
  meta: null, panes: null, newRow: null,
  rows: [], aux: {}, path: "", name: "",
  selected: null,          // the selected row object (survives filtering)
};

const $ = (sel) => document.querySelector(sel);

async function boot() {
  const st = await fetch("/api/state").then((r) => r.json());
  state.rows = st.rows; state.path = st.path; state.name = st.name;

  const tpl = await import("/template.js");
  state.meta = tpl.meta || {};
  state.panes = tpl.panes || {};
  state.newRow = tpl.newRow || (() => ({}));

  for (const [key, file] of Object.entries(state.meta.aux || {})) {
    state.aux[key] = await fetch(`/api/aux?name=${encodeURIComponent(file)}`).then((r) => r.json());
  }

  state.selected = state.rows[0] || null;
  $("#dataset-name").textContent = state.meta.title
    ? `${state.meta.title}  ·  ${state.name}` : state.name;

  wireChrome();
  renderSidebar();
  renderDetail();
}

// ── save (debounced, whole-file) ─────────────────────────────────────────────
let saveTimer = null;
function setStatus(text, cls = "") { const s = $("#save-status"); s.textContent = text; s.className = "save-status " + cls; }
function persist() {
  setStatus("saving…", "saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      const res = await fetch("/api/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows: state.rows }),
      }).then((r) => r.json());
      if (res.ok) setStatus(`saved · ${res.count} cases`, "saved");
      else setStatus(res.error || "save failed", "error");
    } catch (e) { setStatus("save failed", "error"); }
  }, 350);
}

// ── chrome: sidebar toggle, add case ─────────────────────────────────────────
function wireChrome() {
  $("#toggle-sidebar").onclick = () => document.body.classList.toggle("sidebar-hidden");
  $("#add-case").onclick = () => {
    const row = state.newRow();
    state.rows.push(row);
    state.selected = row;
    persist(); renderSidebar(); renderDetail();
  };
}

function visibleRows() {
  return state.rows;
}

// ── sidebar: the case list ───────────────────────────────────────────────────
function renderSidebar() {
  const rows = visibleRows();
  $("#case-count").textContent = `${rows.length} case${rows.length === 1 ? "" : "s"}`;
  const ul = $("#case-list");
  ul.replaceChildren();
  const nameOf = state.meta.caseName || ((r) => r.id || "(unnamed)");
  for (const row of rows) {
    const li = h("li", {
      class: row === state.selected ? "selected" : "",
      onclick: () => { state.selected = row; renderSidebar(); renderDetail(); },
    },
      h("span", { class: "case-name" }, String(nameOf(row))),
      row.difficulty ? h("span", { class: "chip" }, row.difficulty) : null,
    );
    ul.append(li);
  }
}

// ── detail: the context / input / output columns ─────────────────────────────
// Column bodies are kept so an edit can re-render just ONE column — e.g. adding a
// card from Context refreshes only Output, leaving the Context search box + scroll
// exactly where you left them.
state.bodies = { context: null, input: null, output: null };

function ctxFor(row, which) {
  return {
    row,
    rows: state.rows,
    aux: state.aux,
    column: which,
    h,
    index(auxName, key) {
      const m = new Map();
      for (const it of state.aux[auxName] || []) m.set(it[key], it);
      return m;
    },
    // structural change → re-render a target column ('self' by default, or
    // 'header' | 'context' | 'input' | 'output' | 'all')
    mutate(fn, target = "self") { fn(row); persist(); rerender(target === "self" ? which : target); },
    // in-place field edit (textarea/select) → save only, no re-render (keeps focus)
    persist(fn) { if (fn) fn(row); persist(); },
    // a case-meta edit changed something the chrome shows (id, difficulty)
    refreshShell() { renderSidebar(); },
    w: widgets,
  };
}

const COLS = [["context", "Context"], ["input", "Input"], ["output", "Expected output"]];

function renderColumn(which) {
  const body = state.bodies[which];
  const pane = state.panes[which];
  if (!body || !pane || !state.selected) return;
  body.replaceChildren();
  try { pane(body, ctxFor(state.selected, which)); }
  catch (e) { body.append(h("div", { class: "empty" }, "template error: " + e.message)); console.error(e); }
}

function rerender(target) {
  if (target === "all") renderDetail();
  else if (target === "header") renderCaseBar();
  else renderColumn(target);
}

// The case-meta strip (id / difficulty / split / note) — the template's `header`
// pane. Horizontal, above the pipeline columns; re-renders only on selection.
function renderCaseBar() {
  const bar = $("#casebar");
  bar.replaceChildren();
  const pane = state.panes.header;
  if (!pane || !state.selected) { bar.style.display = "none"; return; }
  bar.style.display = "flex";
  try { pane(bar, ctxFor(state.selected, "header")); }
  catch (e) { bar.append(h("div", { class: "empty" }, "template error: " + e.message)); console.error(e); }
}

function renderDetail() {
  renderCaseBar();
  const cols = $("#columns");
  const footer = $("#detail-footer");
  cols.replaceChildren();
  footer.replaceChildren();
  state.bodies = { context: null, input: null, output: null };
  if (!state.selected) { cols.append(h("div", { class: "empty" }, "No cases yet — click “+ new”.")); return; }

  for (const [key, title] of COLS) {
    if (!state.panes[key]) continue;
    const body = h("div", { class: "column-body" });
    state.bodies[key] = body;
    cols.append(h("section", { class: "column" }, h("h2", {}, title), body));
    renderColumn(key);
  }

  const row = state.selected;
  footer.append(h("button", { class: "danger-link", onclick: () => {
    if (!confirm("Delete this case?")) return;
    state.rows.splice(state.rows.indexOf(row), 1);
    state.selected = visibleRows()[0] || state.rows[0] || null;
    persist(); renderSidebar(); renderDetail();
  } }, "Delete this case"));
}

// ── widget kit (what templates build panes from) ─────────────────────────────
const widgets = {
  // a compact labelled group — used to lay controls out in the horizontal case bar
  field(label, control, { grow = 0 } = {}) {
    const el = h("div", { class: "cbar-item" }, h("label", {}, label), control);
    if (grow) el.style.flex = String(grow);
    return el;
  },

  text(value, onChange, { placeholder = "", rows = 4 } = {}) {
    const ta = h("textarea", { rows, placeholder });
    ta.value = value ?? "";
    ta.addEventListener("input", () => onChange(ta.value));
    return ta;
  },

  line(value, onChange, { placeholder = "" } = {}) {
    const inp = h("input", { type: "text", placeholder });
    inp.value = value ?? "";
    inp.addEventListener("input", () => onChange(inp.value));
    return inp;
  },

  select(value, options, onChange, { allowEmpty = true, emptyLabel = "— none —" } = {}) {
    const opts = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
    const sel = h("select");
    if (allowEmpty) sel.append(h("option", { value: "" }, emptyLabel));
    for (const o of opts) {
      const opt = h("option", { value: o.value }, o.label);
      if ((value ?? "") === o.value) opt.selected = true;
      sel.append(opt);
    }
    sel.addEventListener("change", () => onChange(sel.value || null));
    return sel;
  },

  tags(values, onChange, { placeholder = "add…" } = {}) {
    const list = Array.isArray(values) ? [...values] : [];
    const box = h("div", { class: "tags" });
    const commit = () => onChange([...list]);
    const draw = () => {
      box.replaceChildren();
      list.forEach((t, i) => box.append(h("span", { class: "tag" }, t,
        h("button", { title: "remove", onclick: () => { list.splice(i, 1); draw(); commit(); } }, "×"))));
      const inp = h("input", { class: "tag-input", placeholder });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && inp.value.trim()) {
          e.preventDefault(); list.push(inp.value.trim()); draw(); commit();
          box.querySelector(".tag-input").focus();
        } else if (e.key === "Backspace" && !inp.value && list.length) {
          list.pop(); draw(); commit(); box.querySelector(".tag-input").focus();
        }
      });
      box.append(inp);
    };
    draw();
    return box;
  },

  /* Searchable card list — the CONTEXT corpus. `card(item) -> {id,title,sub,badges}`.
     `actions: [{label,title,on(item)}]` render as buttons; cards are draggable so
     they can also be dropped into an output bucket. */
  searchCards({ items, card, actions = [], placeholder = "search…" }) {
    const wrap = h("div");
    const search = h("input", { type: "text", placeholder });
    const listEl = h("div");
    wrap.append(h("div", { class: "search-box" }, search), listEl);

    const render = (term) => {
      listEl.replaceChildren();
      const t = term.trim().toLowerCase();
      const shown = items.filter((it) => {
        if (!t) return true;
        const c = card(it);
        return `${c.title} ${c.sub || ""} ${(c.badges || []).join(" ")} ${c.id}`.toLowerCase().includes(t);
      });
      if (!shown.length) { listEl.append(h("div", { class: "empty" }, "no matches")); return; }
      for (const it of shown) {
        const c = card(it);
        const el = h("div", { class: "card", draggable: "true" },
          h("div", { class: "card-title" }, c.title),
          c.sub ? h("div", { class: "card-sub" }, c.sub) : null,
          c.badges && c.badges.length ? h("div", { class: "badges" }, c.badges.map((b) => h("span", { class: "chip" }, b))) : null,
          actions.length ? h("div", { class: "card-actions" },
            actions.map((a) => h("button", { class: "mini-btn", title: a.title || "", onclick: () => a.on(it) }, a.label))) : null,
        );
        el.addEventListener("dragstart", () => { DRAG = { id: c.id, from: "context" }; });
        el.addEventListener("dragend", () => { DRAG = null; });
        listEl.append(el);
      }
    };
    search.addEventListener("input", () => render(search.value));
    render("");
    return wrap;
  },

  /* A reorderable card list — one EXPECTED-OUTPUT bucket. `ids` is the current
     list; `resolve(id) -> {title,sub}`; `onChange(newIds)` fires on any edit.
     Supports remove, up/down, drag-reorder, and accepting a drop from context. */
  bucket({ title, ids, resolve, onChange, accent }) {
    const cur = [...ids];
    const head = h("div", { class: "bucket-head" },
      h("span", { class: "bucket-title" }, title),
      h("span", { class: "count" }, `${cur.length}`));
    const listEl = h("div");
    const box = h("div", { class: "bucket" }, head, listEl);
    if (accent) box.style.borderColor = accent;

    const commit = () => { head.querySelector(".count").textContent = String(cur.length); onChange([...cur]); };

    const insertIndexFor = (y) => {
      const cards = [...listEl.querySelectorAll(".card")];
      for (let i = 0; i < cards.length; i++) {
        const r = cards[i].getBoundingClientRect();
        if (y < r.top + r.height / 2) return i;
      }
      return cards.length;
    };

    box.addEventListener("dragover", (e) => { e.preventDefault(); box.classList.add("drop-hot"); });
    box.addEventListener("dragleave", () => box.classList.remove("drop-hot"));
    box.addEventListener("drop", (e) => {
      e.preventDefault(); box.classList.remove("drop-hot");
      if (!DRAG) return;
      const at = insertIndexFor(e.clientY);
      const existing = cur.indexOf(DRAG.id);
      if (existing !== -1) cur.splice(existing, 1);            // reorder within
      const idx = existing !== -1 && existing < at ? at - 1 : at;
      cur.splice(idx, 0, DRAG.id);
      // de-dupe (a drop may re-add)
      const seen = new Set(); for (let i = cur.length - 1; i >= 0; i--) { if (seen.has(cur[i])) cur.splice(i, 1); else seen.add(cur[i]); }
      draw(); commit();
    });

    const draw = () => {
      listEl.replaceChildren();
      if (!cur.length) { listEl.append(h("div", { class: "bucket-empty" }, "drag cards here, or use the + buttons")); return; }
      cur.forEach((id, i) => {
        const info = resolve(id) || { title: id, sub: "" };
        const el = h("div", { class: "card", draggable: "true" },
          h("span", { class: "grip", title: "drag to reorder" }, "⠿"),
          h("div", { class: "grow" },
            h("div", { class: "card-title" }, info.title),
            info.sub ? h("div", { class: "card-sub" }, info.sub) : null),
          h("div", { class: "row-actions" },
            h("button", { title: "up", onclick: () => { if (i > 0) { [cur[i - 1], cur[i]] = [cur[i], cur[i - 1]]; draw(); commit(); } } }, "↑"),
            h("button", { title: "down", onclick: () => { if (i < cur.length - 1) { [cur[i + 1], cur[i]] = [cur[i], cur[i + 1]]; draw(); commit(); } } }, "↓"),
            h("button", { title: "remove", onclick: () => { cur.splice(i, 1); draw(); commit(); } }, "×")),
        );
        el.addEventListener("dragstart", () => { DRAG = { id, from: "bucket" }; el.classList.add("dragging"); });
        el.addEventListener("dragend", () => { DRAG = null; el.classList.remove("dragging"); });
        listEl.append(el);
      });
    };
    draw();
    return box;
  },
};

boot().catch((e) => { document.body.append(h("pre", { style: "padding:20px;color:#c8402f" }, "Failed to start: " + e.message)); console.error(e); });
