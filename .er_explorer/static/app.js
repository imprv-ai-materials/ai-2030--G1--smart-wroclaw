/* ER Explorer front-end.
   Cytoscape.js draws the graph (built-in wheel-zoom + drag-pan + tap-select);
   cytoscape-fcose / cytoscape-dagre auto-lay it out; cytoscape-node-html-label
   renders each table as an HTML card (header + columns with PK/FK/UK badges).
   The model comes from /api/er (the .er.json produced by `pypyr render_er`). */

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
const $ = (s) => document.querySelector(s);
function esc(s) {
  return String(s).replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
}

// ── app state ────────────────────────────────────────────────────────────────
let cy = null;
let MODEL = { tables: [], relationships: [] };
const state = { layout: "fcose", compact: false, search: "", selectedId: null, on: {} };

// ── card sizing (measure text so the node box == the HTML card exactly) ──────
const _cx = document.createElement("canvas").getContext("2d");
const FONT_HEAD = "700 13px ui-sans-serif, system-ui, sans-serif";
const FONT_NAME = "600 12px ui-sans-serif, system-ui, sans-serif";
const FONT_TYPE = "10.5px ui-monospace, monospace";
const HEAD_H = 30, ROW_H = 21, COLS_PAD = 6, PADX = 10, KEY_W = 26, GAP = 10, PILL = 30;

function tw(text, font) { _cx.font = font; return _cx.measureText(String(text ?? "")).width; }

function sizeOf(t, compact) {
  let w = tw(t.name, FONT_HEAD) + PADX * 2 + PILL;
  for (const c of t.columns) {
    const cw = PADX * 2 + KEY_W + tw(c.name, FONT_NAME) + GAP + tw(c.type, FONT_TYPE);
    if (cw > w) w = cw;
  }
  w = Math.max(190, Math.min(460, Math.ceil(w)));
  const rows = t.columns.length;
  const height = compact ? HEAD_H + 4 : HEAD_H + COLS_PAD + rows * ROW_H + 4;
  return { w, h: height };
}

// ── crow's-foot cardinality → a short human label (e.g. "}o" → "0..N") ───────
function cardText(sym) {
  const s = sym || "";
  const many = s.includes("}") || s.includes("{");
  const zero = s.includes("o");
  if (many) return zero ? "0..N" : "1..N";
  return zero ? "0..1" : "1";
}

// ── the HTML table card (node-html-label template; re-runs on any data change) ─
function keyBadge(c) {
  if (c.pk) return '<span class="er-key kb-pk">PK</span>';
  if (c.fk) return '<span class="er-key kb-fk">FK</span>';
  if (c.uk) return '<span class="er-key kb-uk">UK</span>';
  return '<span class="er-keyspace"></span>';
}
function cardTpl(data) {
  if (data.hidden) return "";  // filtered out — blank the overlay (canvas node is display:none)
  const t = data.table;
  const cls = "er-card" + (data.sel ? " sel" : "") + (data._dim ? " dim" : "");
  let html = `<div class="${cls}" style="width:${data.w}px;height:${data.h}px">`;
  html += `<div class="er-head"><span class="er-tname">${esc(t.name)}</span>` +
          `<span class="er-pill">${t.columns.length}</span></div>`;
  if (!data.compact) {
    html += '<div class="er-cols">';
    for (const c of t.columns) {
      const isKey = c.pk || c.fk || c.uk;
      html += `<div class="er-col${isKey ? " is-key" : ""}">${keyBadge(c)}` +
              `<span class="er-cname">${esc(c.name)}</span>` +
              `<span class="er-ctype">${esc(c.type)}</span></div>`;
    }
    html += "</div>";
  }
  return html + "</div>";
}

// ── cytoscape style ──────────────────────────────────────────────────────────
const STYLE = [
  { selector: "node", style: {
      width: "data(w)", height: "data(h)", shape: "round-rectangle",
      "background-opacity": 0, "border-width": 0, label: "" } },
  { selector: "node.hidden", style: { display: "none" } },
  { selector: "edge", style: {
      width: 1.4, "line-color": "#9aa0aa", "curve-style": "bezier",
      "target-arrow-shape": "triangle", "target-arrow-color": "#9aa0aa", "arrow-scale": 0.9,
      label: "data(label)", "font-size": 9, color: "#5b6270", "text-rotation": "autorotate",
      "text-background-color": "#ffffff", "text-background-opacity": 0.85,
      "text-background-shape": "roundrectangle", "text-background-padding": 2,
      "font-family": "ui-sans-serif, system-ui, sans-serif" } },
  { selector: "edge.hidden", style: { display: "none" } },
  { selector: "edge.fuzzy", style: {
      "line-style": "dashed", "line-color": "#b06bd6",
      "target-arrow-color": "#b06bd6", "target-arrow-shape": "vee" } },
  { selector: "edge.dim", style: { opacity: 0.1 } },
  { selector: "edge.hl", style: {
      "line-color": "#2b6cff", "target-arrow-color": "#2b6cff", width: 2.4, "z-index": 999,
      color: "#2b6cff", "font-size": 10,
      "source-label": "data(srcCard)", "target-label": "data(tgtCard)",
      "source-text-offset": 16, "target-text-offset": 22 } },
];

// ── autolayouts ──────────────────────────────────────────────────────────────
const LAYOUTS = {
  fcose: { name: "fcose", quality: "proof", randomize: true, animate: false, fit: true, padding: 46,
           nodeSeparation: 130, idealEdgeLength: 150, nodeRepulsion: 9000, packComponents: true,
           nodeDimensionsIncludeLabels: false },
  "dagre-lr": { name: "dagre", rankDir: "LR", nodeSep: 45, rankSep: 95, edgeSep: 22, ranker: "network-simplex",
                animate: false, fit: true, padding: 46 },
  "dagre-tb": { name: "dagre", rankDir: "TB", nodeSep: 45, rankSep: 95, edgeSep: 22, ranker: "network-simplex",
                animate: false, fit: true, padding: 46 },
  concentric: { name: "concentric", animate: false, fit: true, padding: 46, minNodeSpacing: 45,
                concentric: (n) => n.degree(), levelWidth: () => 2 },
  grid: { name: "grid", animate: false, fit: true, padding: 46, avoidOverlap: true, avoidOverlapPadding: 30 },
};
function runLayout() {
  const opts = LAYOUTS[state.layout] || LAYOUTS.fcose;
  try {
    cy.elements(":visible").layout(opts).run();
  } catch (e) {
    console.error("layout failed, falling back to grid", e);
    cy.elements(":visible").layout(LAYOUTS.grid).run();
  }
}

// ── build cy elements from the model ─────────────────────────────────────────
function buildElements(model) {
  const names = new Set(model.tables.map((t) => t.name));
  const nodes = model.tables.map((t) => {
    const { w, h: hgt } = sizeOf(t, false);
    return { data: { id: t.name, table: t, w, h: hgt, compact: false, hidden: false, _dim: false, sel: false } };
  });
  const edges = [];
  model.relationships.forEach((r, i) => {
    if (!names.has(r.from) || !names.has(r.to)) return;  // skip dangling refs
    edges.push({
      data: { id: "e" + i, source: r.from, target: r.to, label: r.label,
              srcCard: cardText(r.left), tgtCard: cardText(r.right) },
      classes: r.constraint ? "" : "fuzzy",
    });
  });
  return { nodes, edges };
}

// ── filtering (search box + per-table checkboxes) ────────────────────────────
function matches(t, term) {
  if (!term) return true;
  return t.name.toLowerCase().includes(term) || t.columns.some((c) => c.name.toLowerCase().includes(term));
}
function applyVisibility() {
  const term = state.search.trim().toLowerCase();
  let vis = 0;
  cy.batch(() => {
    for (const t of MODEL.tables) {
      const show = state.on[t.name] !== false && matches(t, term);
      if (show) vis++;
      const n = cy.getElementById(t.name);
      n.data("hidden", !show);
      n.toggleClass("hidden", !show);
    }
  });
  $("#visible-count").textContent = `${vis} / ${MODEL.tables.length} tables`;
}

// ── focus a table's neighbourhood (dim the rest) ─────────────────────────────
function focusNode(node) {
  state.selectedId = node.id();
  const hood = node.closedNeighborhood();
  cy.batch(() => {
    cy.nodes().forEach((n) => {
      n.data("_dim", !hood.contains(n));
      n.data("sel", n.id() === node.id());
    });
    cy.edges().removeClass("hl").addClass("dim");
    node.connectedEdges().removeClass("dim").addClass("hl");
  });
  renderList();
  openInspector(node);
}
function clearFocus() {
  state.selectedId = null;
  cy.batch(() => {
    cy.nodes().forEach((n) => { n.data("_dim", false); n.data("sel", false); });
    cy.edges().removeClass("hl dim");
  });
  renderList();
  $("#inspector").classList.add("hidden");
}
function centerOn(node) {
  cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 0.9) }, { duration: 300 });
}

// ── inspector (right panel) ──────────────────────────────────────────────────
function keyBadgeEl(c) {
  const k = c.pk ? ["PK", "kb-pk"] : c.fk ? ["FK", "kb-fk"] : c.uk ? ["UK", "kb-uk"] : null;
  return k ? h("span", { class: "kbadge " + k[1] }, k[0])
           : h("span", { class: "kbadge", style: "visibility:hidden" }, "··");
}
function relEl(r, dir) {
  const other = dir === "out" ? r.to : r.from;
  const el = h("div", { class: "insp-rel" + (r.constraint ? "" : " fuzzy") },
    h("span", { class: "arrow" }, dir === "out" ? "→ " : "← "),
    h("span", {}, other),
    h("span", { class: "via" }, "  · " + r.label + (r.constraint ? "" : " (fuzzy)")));
  el.addEventListener("click", () => {
    const n = cy.getElementById(other);
    if (n.nonempty() && !n.hasClass("hidden")) { focusNode(n); centerOn(n); }
  });
  return el;
}
function openInspector(node) {
  const t = node.data("table");
  $("#insp-title").textContent = t.name;
  const body = $("#insp-body");
  body.replaceChildren();
  body.append(h("div", { class: "insp-section" }, `Columns · ${t.columns.length}`));
  for (const c of t.columns) {
    body.append(h("div", { class: "insp-col" + (c.pk || c.fk || c.uk ? " is-key" : "") },
      keyBadgeEl(c),
      h("span", { class: "cname" }, c.name + (c.comment ? "  — " + c.comment : "")),
      h("span", { class: "ctype" }, c.type)));
  }
  const outs = MODEL.relationships.filter((r) => r.from === t.name);
  const ins = MODEL.relationships.filter((r) => r.to === t.name);
  if (outs.length) {
    body.append(h("div", { class: "insp-section" }, `References · ${outs.length}`));
    outs.forEach((r) => body.append(relEl(r, "out")));
  }
  if (ins.length) {
    body.append(h("div", { class: "insp-section" }, `Referenced by · ${ins.length}`));
    ins.forEach((r) => body.append(relEl(r, "in")));
  }
  if (!outs.length && !ins.length) body.append(h("div", { class: "insp-empty" }, "No relationships."));
  $("#inspector").classList.remove("hidden");
}

// ── sidebar table list ───────────────────────────────────────────────────────
function renderList() {
  const term = state.search.trim().toLowerCase();
  const ul = $("#table-list");
  ul.replaceChildren();
  for (const t of MODEL.tables) {
    if (!matches(t, term)) continue;
    const on = state.on[t.name] !== false;
    const li = h("li", { class: (t.name === state.selectedId ? "selected " : "") + (on ? "" : "off") });
    const cb = h("input", { type: "checkbox" });
    cb.checked = on;
    cb.addEventListener("click", (e) => e.stopPropagation());
    cb.addEventListener("change", () => { state.on[t.name] = cb.checked; li.classList.toggle("off", !cb.checked); applyVisibility(); });
    li.append(cb, h("span", { class: "tbl-name" }, t.name), h("span", { class: "tbl-cols" }, t.columns.length));
    li.addEventListener("click", () => {
      const n = cy.getElementById(t.name);
      if (n.hasClass("hidden")) return;
      focusNode(n);
      centerOn(n);
    });
    ul.append(li);
  }
}

// ── toolbar / chrome wiring ──────────────────────────────────────────────────
function zoomBy(factor) {
  cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
}
function fitAll() {
  const eles = cy.elements(":visible");
  if (eles.nonempty()) cy.animate({ fit: { eles, padding: 46 } }, { duration: 300 });
}
function wireChrome() {
  $("#toggle-sidebar").onclick = () => document.body.classList.toggle("sidebar-hidden");
  $("#layout-select").onchange = (e) => { state.layout = e.target.value; runLayout(); };
  $("#relayout").onclick = () => runLayout();
  $("#zoom-in").onclick = () => zoomBy(1.25);
  $("#zoom-out").onclick = () => zoomBy(1 / 1.25);
  $("#fit").onclick = fitAll;

  $("#search").addEventListener("input", (e) => { state.search = e.target.value; renderList(); applyVisibility(); });
  $("#show-all").onclick = () => { MODEL.tables.forEach((t) => (state.on[t.name] = true)); renderList(); applyVisibility(); };
  $("#hide-all").onclick = () => { MODEL.tables.forEach((t) => (state.on[t.name] = false)); renderList(); applyVisibility(); };

  $("#compact").onchange = (e) => {
    state.compact = e.target.checked;
    cy.batch(() => cy.nodes().forEach((n) => {
      const { w, h: hgt } = sizeOf(n.data("table"), state.compact);
      n.data({ w, h: hgt, compact: state.compact });
    }));
    runLayout();
  };
  $("#show-fuzzy").onchange = (e) => cy.edges(".fuzzy").toggleClass("hidden", !e.target.checked);

  $("#insp-close").onclick = clearFocus;

  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.key === "f" || e.key === "F") fitAll();
    else if (e.key === "Escape") clearFocus();
  });
}

// ── boot ─────────────────────────────────────────────────────────────────────
async function boot() {
  const st = await fetch("/api/er").then((r) => r.json());
  MODEL = st.diagram || { tables: [], relationships: [] };
  $("#source-name").textContent = st.name || "er diagram";
  $("#counts").textContent = `${MODEL.tables.length} tables · ${MODEL.relationships.length} relationships`;

  const { nodes, edges } = buildElements(MODEL);
  cy = cytoscape({
    container: $("#cy"),
    elements: [...nodes, ...edges],
    style: STYLE,
    layout: { name: "preset" },
    wheelSensitivity: 0.22,
    minZoom: 0.08,
    maxZoom: 3,
    boxSelectionEnabled: false,
  });
  window.cy = cy;  // handy for poking at the graph from the devtools console

  cy.nodeHtmlLabel([{ query: "node", valign: "center", halign: "center", valignBox: "center", halignBox: "center", tpl: cardTpl }]);

  cy.on("tap", "node", (e) => focusNode(e.target));
  cy.on("tap", (e) => { if (e.target === cy) clearFocus(); });

  wireChrome();
  renderList();
  applyVisibility();
  runLayout();
}

boot().catch((e) => {
  document.body.append(h("pre", { style: "padding:20px;color:#c8402f;white-space:pre-wrap" }, "Failed to start: " + e.message));
  console.error(e);
});
