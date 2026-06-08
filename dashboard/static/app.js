"use strict";

const $ = (s) => document.querySelector(s);
const fmtRp = (v) => {
  if (v == null) return "-";
  const n = Number(v);
  if (n >= 1e12) return "Rp" + (n / 1e12).toFixed(2) + " T";
  if (n >= 1e9) return "Rp" + (n / 1e9).toFixed(2) + " M";
  if (n >= 1e6) return "Rp" + (n / 1e6).toFixed(1) + " jt";
  return "Rp" + n.toLocaleString("id-ID");
};
const fmtNum = (v) => (v == null ? "-" : Number(v).toLocaleString("id-ID"));
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function api(path, params) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  const r = await fetch("/api" + path + qs);
  if (!r.ok) throw new Error(path + " -> " + r.status);
  return r.json();
}

// ---- Tabs ----
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("#" + t.dataset.tab).classList.add("active");
  });
});

// ---- Simple table renderer ----
function renderTable(el, rows, cols) {
  if (!rows.length) { el.innerHTML = '<p class="muted" style="padding:12px">Tidak ada data.</p>'; return; }
  let h = "<table><thead><tr>";
  cols.forEach((c) => (h += `<th>${esc(c.title)}</th>`));
  h += "</tr></thead><tbody>";
  rows.forEach((row) => {
    h += "<tr>";
    cols.forEach((c) => {
      const raw = row[c.key];
      const cls = c.num ? "num" : "";
      h += `<td class="${cls}">${c.render ? c.render(raw, row) : esc(raw ?? "-")}</td>`;
    });
    h += "</tr>";
  });
  h += "</tbody></table>";
  el.innerHTML = h;
}

function badge(v, prefix) { return v ? `<span class="badge b-${esc(v)}">${esc(v)}</span>` : "-"; }

// ---- CSV export ----
function toCSV(rows, cols) {
  const head = cols.map((c) => `"${c.title}"`).join(",");
  const body = rows.map((r) => cols.map((c) => `"${String(r[c.key] ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  return head + "\n" + body;
}
function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
}

// ---- Overview ----
async function loadOverview() {
  const s = await api("/summary");
  const valid = (s.verdicts.find((v) => v.verdict === "valid") || {});
  const fp = (s.verdicts.find((v) => v.verdict === "false_positive") || {});
  const totalAnom = s.anomaly_types.reduce((a, b) => a + b.n, 0);
  const cards = [
    { label: "Simpul Graph", value: fmtNum((s.nodes.PN || 0) + (s.nodes.PP || 0) + (s.nodes.KP || 0)),
      sub: `PN ${s.nodes.PN || 0} / PP ${s.nodes.PP || 0} / KP ${s.nodes.KP || 0}` },
    { label: "Edges", value: fmtNum(s.edges) },
    { label: "Anomali Keselarasan", value: fmtNum(totalAnom), sub: "DIPA vs RPJMN/RKP" },
    { label: "Valid (TreasurAI)", value: fmtNum(valid.n || 0), sub: fmtRp(valid.pagu || 0) },
    { label: "False Positive", value: fmtNum(fp.n || 0), sub: fmtRp(fp.pagu || 0) },
    { label: "Anomali Koherensi", value: fmtNum(s.coherence.filter((c) => c.jenis_anomaly !== "normal" && c.jenis_anomaly !== "unclassified").reduce((a, b) => a + b.n, 0)) },
    { label: "Penugasan K/L", value: fmtNum(s.kl_assignments), sub: "KP -> K/L pelaksana" },
  ];
  $("#kpi-cards").innerHTML = cards.map((c) =>
    `<div class="kpi"><div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub || ""}</div></div>`).join("");

  renderTable($("#tbl-anomaly-types"), s.anomaly_types, [
    { title: "Tipe", key: "anomaly_type" },
    { title: "Jumlah", key: "n", num: true, render: fmtNum },
    { title: "Pagu", key: "pagu", num: true, render: fmtRp },
  ]);
  renderTable($("#tbl-verdicts"), s.verdicts, [
    { title: "Verdict", key: "verdict", render: (v) => badge(v) },
    { title: "Jumlah", key: "n", num: true, render: fmtNum },
    { title: "Pagu", key: "pagu", num: true, render: fmtRp },
  ]);
  renderTable($("#tbl-coherence-sum"), s.coherence, [
    { title: "Jenis Anomali", key: "jenis_anomaly" },
    { title: "Jumlah", key: "n", num: true, render: fmtNum },
    { title: "Pagu", key: "pagu", num: true, render: fmtRp },
  ]);
  renderTable($("#tbl-nodes"), Object.entries(s.nodes).map(([k, v]) => ({ t: k, n: v })), [
    { title: "Tipe Simpul", key: "t" },
    { title: "Jumlah", key: "n", num: true, render: fmtNum },
  ]);
}

// ---- K/L dropdowns ----
async function loadKlOptions() {
  const list = await api("/kl-list");
  const opts = list.map((k) => `<option value="${esc(k.kode)}">${esc(k.kode)} - ${esc(k.nama)}</option>`).join("");
  ["#a-kl", "#c-kl", "#k-kl"].forEach((sel) => { $(sel).insertAdjacentHTML("beforeend", opts); });
}

// ---- Anomalies ----
const anomCols = [
  { title: "K/L", key: "kementerian_uraian", render: (v, r) => esc(r.kementerian_kode) + " - " + esc(v) },
  { title: "Program", key: "program_kode" },
  { title: "Pagu", key: "total_pagu", num: true, render: fmtRp },
  { title: "Skor Align", key: "alignment_score", num: true },
  { title: "Tipe", key: "anomaly_type" },
  { title: "Prioritas", key: "review_priority", num: true },
  { title: "Verdict", key: "treasurai_verdict", render: (v) => badge(v) },
  { title: "Status", key: "review_status" },
  { title: "Best Match", key: "best_match_name", render: (v, r) => esc(r.best_match_code) + " " + esc(v) },
  { title: "Alasan TreasurAI", key: "llm_reasoning", render: (v) => `<div class="reason">${esc(v)}</div>` },
];
let anomRows = [];
async function loadAnomalies() {
  $("#a-info").textContent = "memuat...";
  anomRows = await api("/anomalies", {
    kl: $("#a-kl").value, verdict: $("#a-verdict").value, status: $("#a-status").value,
    min_priority: $("#a-prio").value || 0, limit: 500,
  });
  renderTable($("#tbl-anomalies"), anomRows, anomCols);
  $("#a-info").textContent = anomRows.length + " baris";
}

// ---- Coherence ----
const cohCols = [
  { title: "K/L", key: "kementerian_uraian", render: (v, r) => esc(r.kementerian_kode) + " - " + esc(v) },
  { title: "Program", key: "program_uraian" },
  { title: "Output/KRO", key: "outputkro_uraian" },
  { title: "Komponen", key: "komponen_uraian" },
  { title: "Jenis", key: "jenis_komponen" },
  { title: "Anomali", key: "jenis_anomaly", render: (v) => badge(v) },
  { title: "Skor", key: "jenis_anomaly_score", num: true },
  { title: "Pagu", key: "total_pagu", num: true, render: fmtRp },
];
let cohRows = [];
async function loadCoherence() {
  $("#c-info").textContent = "memuat...";
  cohRows = await api("/coherence", { kl: $("#c-kl").value, jenis: $("#c-jenis").value, limit: 500 });
  renderTable($("#tbl-coherence"), cohRows, cohCols);
  $("#c-info").textContent = cohRows.length + " baris";
}

// ---- K/L assignments ----
const klCols = [
  { title: "Kode KP", key: "node_code" },
  { title: "Nama KP", key: "node_name" },
  { title: "Kode K/L", key: "kddept" },
  { title: "K/L Pelaksana", key: "nmdept_normalized" },
  { title: "Peran", key: "role" },
  { title: "Confidence", key: "confidence", num: true },
];
let klRows = [];
async function loadKl() {
  $("#k-info").textContent = "memuat...";
  klRows = await api("/kl-assignments", { kl: $("#k-kl").value, limit: 1000 });
  renderTable($("#tbl-kl"), klRows, klCols);
  $("#k-info").textContent = klRows.length + " baris";
}

// ---- Graph ----
let network = null;
const NODE_COLORS = { PN: "#4ea1ff", PP: "#3fb950", KP: "#d29922" };
async function loadGraph() {
  $("#g-info").textContent = "memuat...";
  const data = await api("/graph", {
    source_type: $("#g-source").value, include_kp: $("#g-kp").checked ? 1 : 0, pn: $("#g-pn").value.trim(),
  });
  const nodes = data.nodes.map((n) => ({
    id: n.id, label: n.node_code, title: `${n.node_type} ${n.node_code}\n${n.node_name}`,
    color: NODE_COLORS[n.node_type] || "#888",
    shape: n.node_type === "PN" ? "hexagon" : n.node_type === "PP" ? "dot" : "square",
    size: n.node_type === "PN" ? 18 : n.node_type === "PP" ? 12 : 8,
  }));
  const edges = data.edges.map((e) => ({ from: e.source, to: e.target, arrows: "to", color: { color: "#39424d" } }));
  const container = $("#network");
  network = new vis.Network(container, { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { gravitationalConstant: -8000, springLength: 120 } },
    nodes: { font: { color: "#cfd8e0", size: 11 } },
    interaction: { hover: true, tooltipDelay: 120 },
  });
  $("#g-info").textContent = `${nodes.length} simpul, ${edges.length} edges`;
}

// ---- Wire up ----
$("#a-load").addEventListener("click", loadAnomalies);
$("#a-export").addEventListener("click", () => download("anomali_keselarasan.csv", toCSV(anomRows, anomCols)));
$("#c-load").addEventListener("click", loadCoherence);
$("#c-export").addEventListener("click", () => download("anomali_koherensi.csv", toCSV(cohRows, cohCols)));
$("#k-load").addEventListener("click", loadKl);
$("#k-export").addEventListener("click", () => download("penugasan_kl.csv", toCSV(klRows, klCols)));
$("#g-load").addEventListener("click", loadGraph);

(async function init() {
  try {
    await loadOverview();
    await loadKlOptions();
    await loadAnomalies();
    await loadCoherence();
    await loadKl();
  } catch (e) {
    console.error(e);
    $("#kpi-cards").innerHTML = `<div class="kpi"><div class="label">Error</div><div class="value">!</div><div class="sub">${esc(e.message)}</div></div>`;
  }
})();
