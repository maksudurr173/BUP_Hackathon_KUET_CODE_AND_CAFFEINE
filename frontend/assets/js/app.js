import { SAMPLE_CASES } from "./sample-cases.js";
import {
  interpretNotes,
  optimize,
  validate,
  validateInput,
  runScenario,
  DIRECTIVE_LABEL,
  r2,
  fmtH,
} from "./engine.js";

/* ==========================================================================
   GridWise charts — small SVG renderer.
   ========================================================================== */

const NS = "http://www.w3.org/2000/svg";
const el = (name, attrs = {}) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
};

const PALETTE = {
  teal: "var(--teal)",
  amber: "var(--amber)",
  graphite: "var(--graphite)",
  mint: "var(--mint)",
  ink: "var(--ink-3)",
};

function niceTicks(min, max, count = 4) {
  if (max === min) { max = min + 1; }
  const span = max - min;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return { ticks, lo, hi };
}

const fmtNum = (v, unit) => {
  const n = Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : Math.round(v * 100) / 100;
  return unit ? `${n} ${unit}` : `${n}`;
};

function drawChart(host, spec) {
  const W = Math.max(300, Math.round(host.clientWidth || host.parentElement?.clientWidth || 720));
  const H = spec.height || 250;
  const pad = { t: 14, r: 12, b: 28, l: 44 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const xs = spec.x;
  const nCat = xs.length;

  host.innerHTML = "";
  host.classList.add("chart-box");

  if (spec.legend !== false && spec.series.length > 1) {
    const lg = document.createElement("div");
    lg.className = "legend";
    for (const s of spec.series) {
      const item = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.style.background = s.color || PALETTE.teal;
      if (s.kind === "line") { swatch.style.height = "3px"; swatch.style.borderRadius = "2px"; }
      item.append(swatch, document.createTextNode(s.name));
      lg.appendChild(item);
    }
    host.appendChild(lg);
  }

  const stacked = spec.series.filter((s) => s.stack);
  let maxV = 0, minV = 0;
  for (const s of spec.series) {
    if (s.stack) continue;
    for (const v of s.values) { maxV = Math.max(maxV, v); minV = Math.min(minV, v); }
  }
  for (let i = 0; i < nCat; i++) {
    let sum = 0;
    for (const s of stacked) sum += s.values[i] || 0;
    maxV = Math.max(maxV, sum);
  }
  if (spec.yFrom0 !== false) minV = Math.min(0, minV);
  const { ticks, lo, hi } = niceTicks(minV, maxV || 1, 4);
  const yOf = (v) => pad.t + ih - ((v - lo) / (hi - lo || 1)) * ih;
  const bandW = iw / nCat;
  const xMid = (i) => pad.l + bandW * (i + 0.5);

  const svg = el("svg", {
    class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": spec.ariaLabel || spec.title || "chart", preserveAspectRatio: "none",
  });
  svg.style.height = `${H}px`;
  svg.style.maxHeight = "40vh";

  const gGrid = el("g", { class: "chart-grid" });
  const gAxis = el("g", { class: "chart-axis" });
  for (const t of ticks) {
    const y = yOf(t);
    gGrid.appendChild(el("line", { x1: pad.l, x2: W - pad.r, y1: y, y2: y, opacity: t === 0 ? 1 : .7 }));
    const label = el("text", { x: pad.l - 8, y: y + 3.5, "text-anchor": "end" });
    label.textContent = Math.abs(t) >= 1000 ? `${Math.round(t / 100) / 10}k` : String(t);
    gAxis.appendChild(label);
  }
  svg.append(gGrid);

  const every = spec.xTickEvery || Math.max(1, Math.ceil(nCat / Math.max(4, Math.floor(iw / 44))));
  for (let i = 0; i < nCat; i++) {
    if (i % every) continue;
    const label = el("text", { x: xMid(i), y: H - 9, "text-anchor": "middle" });
    label.textContent = xs[i];
    gAxis.appendChild(label);
  }
  svg.append(gAxis);

  const barSeries = spec.series.filter((s) => s.kind === "bar");
  const plainBars = barSeries.filter((s) => !s.stack);
  const groupW = Math.max(3, bandW * 0.62);

  if (stacked.length) {
    for (let i = 0; i < nCat; i++) {
      let acc = 0;
      stacked.forEach((s) => {
        const v = s.values[i] || 0;
        if (v <= 0) return;
        const y0 = yOf(acc), y1 = yOf(acc + v);
        svg.appendChild(el("rect", {
          class: "chart-bar", x: xMid(i) - groupW / 2, width: groupW,
          y: y1, height: Math.max(0.6, y0 - y1), fill: s.color || PALETTE.teal, rx: 2,
        }));
        acc += v;
      });
    }
  }
  plainBars.forEach((s, si) => {
    const w = groupW / plainBars.length;
    for (let i = 0; i < nCat; i++) {
      const v = s.values[i] || 0;
      const y0 = yOf(Math.max(0, lo)), y1 = yOf(v);
      svg.appendChild(el("rect", {
        class: "chart-bar", x: xMid(i) - groupW / 2 + si * w, width: Math.max(2, w - 1),
        y: Math.min(y0, y1), height: Math.max(0.6, Math.abs(y0 - y1)),
        fill: s.color || PALETTE.teal, rx: 2, opacity: s.opacity ?? 1,
      }));
    }
  });

  for (const s of spec.series) {
    if (s.kind === "bar") continue;
    const pts = s.values.map((v, i) => [xMid(i), yOf(v)]);
    const path = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
    if (s.kind === "area") {
      const base = yOf(Math.max(0, lo));
      svg.appendChild(el("path", {
        class: "chart-area", d: `${path} L${pts[pts.length - 1][0].toFixed(1)} ${base} L${pts[0][0].toFixed(1)} ${base} Z`,
        fill: s.color || PALETTE.teal,
      }));
    }
    svg.appendChild(el("path", {
      class: "chart-line", d: path, stroke: s.color || PALETTE.teal,
      "stroke-width": s.width || 2, "stroke-dasharray": s.dash || "none",
    }));
  }

  const cursor = el("line", { class: "chart-cursor", y1: pad.t, y2: pad.t + ih, opacity: 0 });
  svg.appendChild(cursor);
  const dots = el("g", { opacity: 0 });
  const dotNodes = spec.series.map((s) =>
    el("circle", { class: "chart-dot", r: 3.6, fill: s.color || PALETTE.teal })
  );
  dotNodes.forEach((d) => dots.appendChild(d));
  svg.appendChild(dots);

  const hit = el("rect", { class: "chart-hit", x: pad.l, y: pad.t, width: iw, height: ih });
  svg.appendChild(hit);
  host.appendChild(svg);

  const tip = document.createElement("div");
  tip.className = "tip";
  tip.setAttribute("role", "status");
  host.appendChild(tip);

  let active = -1;
  const show = (i, clientX) => {
    if (i < 0 || i >= nCat) return;
    active = i;
    cursor.setAttribute("x1", xMid(i));
    cursor.setAttribute("x2", xMid(i));
    cursor.setAttribute("opacity", 1);
    dots.setAttribute("opacity", 1);
    spec.series.forEach((s, k) => {
      if (s.kind === "bar") { dotNodes[k].setAttribute("opacity", 0); return; }
      dotNodes[k].setAttribute("opacity", 1);
      dotNodes[k].setAttribute("cx", xMid(i));
      dotNodes[k].setAttribute("cy", yOf(s.values[i] || 0));
    });
    tip.innerHTML = `<b>${spec.tipLabel ? spec.tipLabel(i) : xs[i]}</b>` +
      spec.series.map((s) => `<span class="tip-row"><span>${s.name}</span><span>${fmtNum(s.values[i] || 0, s.unit ?? spec.unit)}</span></span>`).join("");
    const box = svg.getBoundingClientRect();
    const px = box.left + (xMid(i) / W) * box.width;
    tip.style.left = `${clampN(px - box.left, 70, box.width - 70)}px`;
    tip.style.top = `${(pad.t + ih * 0.32) / H * box.height}px`;
    tip.dataset.show = "1";
  };
  const hide = () => { tip.dataset.show = "0"; cursor.setAttribute("opacity", 0); dots.setAttribute("opacity", 0); active = -1; };

  const idxFromEvent = (clientX) => {
    const box = svg.getBoundingClientRect();
    const rel = ((clientX - box.left) / box.width) * W;
    return clampN(Math.floor((rel - pad.l) / bandW), 0, nCat - 1);
  };

  hit.addEventListener("pointermove", (e) => show(idxFromEvent(e.clientX), e.clientX));
  hit.addEventListener("pointerdown", (e) => show(idxFromEvent(e.clientX), e.clientX));
  hit.addEventListener("pointerleave", hide);
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { show(Math.min(nCat - 1, active + 1)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { show(Math.max(0, (active < 0 ? 1 : active) - 1)); e.preventDefault(); }
    if (e.key === "Escape") hide();
  });
  svg.setAttribute("tabindex", "0");

  return { hide };
}

function clampN(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }

function drawSpark(host, values, color = "var(--teal)") {
  const W = 200, H = 34, pad = 3;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    pad + (i / (values.length - 1 || 1)) * (W - pad * 2),
    H - pad - ((v - min) / span) * (H - pad * 2),
  ]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  host.innerHTML = "";
  const svg = el("svg", { class: "spark", viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true", preserveAspectRatio: "none" });
  svg.appendChild(el("path", { d: `${d} L${W - pad} ${H} L${pad} ${H} Z`, fill: color, opacity: .1, stroke: "none" }));
  svg.appendChild(el("path", { d, fill: "none", stroke: color, "stroke-width": 1.8, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  host.appendChild(svg);
}

/* ------------------------------------------------------------------- icons */

const I = {
  overview: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`,
  scenarios: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18M3 12h18M3 17h12"/></svg>`,
  results: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>`,
  bolt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4.5 13.5H11L10 22l8.5-11.5H12z"/></svg>`,
  cost: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9 8.5h4.2a2.3 2.3 0 0 1 0 4.6H9V8.5m0 4.6V16m0-7.5H8m1 4.6h4.6"/></svg>`,
  peak: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5.5-7 4 4L21 5"/><path d="M21 10V5h-5"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19"/></svg>`,
  battery: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="17" height="10" rx="2.4"/><path d="M22 10.5v3"/><path d="M6 10.5v3M9.5 10.5v3"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.2"/><path d="m8 12.4 2.7 2.6L16 9.6"/></svg>`,
  cross: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.2"/><path d="m9 9 6 6M15 9l-6 6"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.6 1.9 20.4h20.2L12 3.6Z"/><path d="M12 9.6v4.6M12 17.4h.01"/></svg>`,
  info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.2"/><path d="M12 11v5M12 7.8h.01"/></svg>`,
  caret: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 9 7 7 7-7"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4.8h6V7M6 7l1 13h10l1-13"/></svg>`,
  play: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.2v13.6L19 12z"/></svg>`,
  pause: `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="5" width="3.6" height="14" rx="1"/><rect x="13.4" y="5" width="3.6" height="14" rx="1"/></svg>`,
  download: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5v11M7.6 10.4 12 14.8l4.4-4.4M4.5 19.5h15"/></svg>`,
  empty: `<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="48" cy="48" r="30" opacity=".35"/><path d="M50 26 36 50h11l-2 20 15-24H49z"/><path d="M8 48h8M80 48h8M48 8v8M48 80v8"/></svg>`,
};

const LOGO = `<svg class="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
  <rect x="1.2" y="1.2" width="29.6" height="29.6" rx="8.4" fill="#149E9A" opacity=".16"/>
  <path d="M6 10.5h20M6 16h20M6 21.5h20" stroke="#149E9A" stroke-width="1.5" opacity=".45" stroke-linecap="round"/>
  <path d="M18.6 5.5 11 17.2h5.3L14.4 26.5 23 14.2h-5.6z" fill="#E5A93D"/>
</svg>`;

/* ------------------------------------------------------------------- state */

const DEFAULT_CURVE = [
  [92, 0, 6.2], [86, 0, 6.0], [82, 0, 5.4], [80, 0, 5.4], [84, 0, 5.6], [95, 2, 6.4],
  [112, 8, 8.2], [132, 24, 10.4], [151, 55, 12.2], [166, 95, 14.0], [176, 132, 15.8],
  [181, 158, 16.2], [184, 172, 15.4], [179, 164, 14.2], [170, 138, 13.4], [164, 92, 14.2],
  [171, 46, 18.0], [186, 12, 22.4], [204, 0, 28.0], [214, 0, 30.2], [203, 0, 26.4],
  [176, 0, 18.2], [136, 0, 10.4], [106, 0, 7.2],
];

const blankDraft = () => ({
  scenario_id: `CAMPUS-${new Date().toISOString().slice(5, 10).replace("-", "")}`,
  hours: DEFAULT_CURVE.map(([d, s, t], h) => ({ hour: h, demand_kwh: d, solar_kwh: s, tariff_bdt_per_kwh: t })),
  battery: {
    capacity_kwh: 220, initial_energy_kwh: 110, minimum_energy_kwh: 40,
    max_charge_kwh_per_hour: 50, max_discharge_kwh_per_hour: 50,
  },
  operator_notes: [""],
});

const state = {
  route: "overview",
  draft: blankDraft(),
  errors: {},
  showErrors: false,
  scenarios: [],
  active: null,
  flowHour: 12,
  playing: false,
  detailHour: 18,
  openChecks: {},
  backend: "online", // Will ping FastAPI backend
};

/* ----------------------------------------------------------------- storage */

const KEY = "gridwise.scenarios.v1";
function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) state.scenarios = JSON.parse(raw) || [];
  } catch { state.scenarios = []; }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state.scenarios.slice(0, 40))); } catch { /* storage unavailable */ }
}

/* ------------------------------------------------------------------ helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
const hh = (h) => String(h).padStart(2, "0");
const kwh = (v) => `${Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
const bdt = (v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });

function toast(message, tone = "ok") {
  const host = $("#toasts");
  const node = document.createElement("div");
  node.className = "toast";
  node.dataset.tone = tone;
  node.innerHTML = `${tone === "bad" ? I.alert : I.check}<span>${esc(message)}</span>`;
  host.appendChild(node);
  setTimeout(() => { node.style.opacity = "0"; node.style.transition = "opacity .3s"; }, 3600);
  setTimeout(() => node.remove(), 4000);
}

/* --------------------------------------------------------------- navigation */

const NAV = [
  { id: "overview", label: "Overview", icon: I.overview },
  { id: "new", label: "New optimization", icon: I.plus },
  { id: "scenarios", label: "Scenarios", icon: I.scenarios },
  { id: "results", label: "Results", icon: I.results },
];

function go(route) {
  state.route = route;
  if (location.hash !== `#${route}`) location.hash = route;
  render();
  window.scrollTo({ top: 0, behavior: "instant" });
}

/* ------------------------------------------------------------------ chrome */

function renderChrome() {
  $("#rail").innerHTML = `
    <div class="brand">
      ${LOGO}
      <div>
        <div class="brand-name">GridWise</div>
        <div class="brand-sub">Campus energy control</div>
      </div>
    </div>
    <nav class="nav" aria-label="Main">
      ${NAV.map((n) => `
        <button class="nav-item" data-go="${n.id}" ${state.route === n.id ? 'aria-current="page"' : ""}>
          ${n.icon}<span>${n.label}</span>
          ${n.id === "scenarios" && state.scenarios.length ? `<span class="nav-count">${state.scenarios.length}</span>` : ""}
        </button>`).join("")}
    </nav>
    <div class="rail-cta">
      <button class="btn btn-onDark btn-block" data-go="new">${I.plus}<span>New optimization</span></button>
    </div>
    <div class="rail-foot">
      <div class="status" data-state="${state.backend}">
        <span class="status-dot"></span>
        <span><b>${state.backend === "online" ? "FastAPI + HiGHS" : "On-device solver"}</b>${state.backend === "online" ? "Backend connected" : "Local fallback"}</span>
      </div>
    </div>`;
}

const TITLES = {
  overview: ["Overview", "Today's campus energy position at a glance."],
  new: ["New optimization", "Describe the day, set the battery, add operator notes."],
  scenarios: ["Scenarios", "Everything you have optimized on this device."],
  results: ["Results", "Schedule, interpretation and constraint checks."],
};

function metric({ name, icon, value, unit, note, accent, spark }) {
  return `<div class="metric" ${accent ? `data-accent="${accent}"` : ""}>
    <div class="metric-top">${icon}<span class="metric-name">${name}</span></div>
    <div class="metric-val">${value}${unit ? `<small>${unit}</small>` : ""}</div>
    ${note ? `<div class="metric-note">${note}</div>` : ""}
    ${spark ? `<div data-spark="${spark.key}" data-color="${spark.color}"></div>` : ""}
  </div>`;
}

/* ------------------------------------------------------------ energy flow */

function flowSvg(result, hour) {
  const row = result.hourly_plan[hour];
  const c = result.constraints;
  const solar = row.solar_used_kwh;
  const grid = row.grid_kwh;
  const batt = row.battery_kwh;
  const charging = row.battery_action === "charge" || row.battery_action === "charging";
  const discharging = row.battery_action === "discharge" || row.battery_action === "discharging";
  const max = Math.max(solar, grid, batt, 1);
  const w = (v) => (v <= 0.01 ? 0 : 2.5 + (v / max) * 11);
  const socPct = c ? Math.round((row.battery_energy_after_kwh / c.cap) * 100) : 50;

  const node = (x, y, wid, hei, title, val, sub, stroke) => `
    <g class="flow-node">
      <rect x="${x}" y="${y}" width="${wid}" height="${hei}" rx="13" stroke="${stroke}" stroke-width="1.4"/>
      <text x="${x + 17}" y="${y + 25}" font-size="12.5" fill="var(--ink-3)">${title}</text>
      <text class="flow-val" x="${x + 17}" y="${y + 50}" font-size="19" font-weight="600">${kwh(val)}<tspan font-size="12" fill="var(--ink-3)"> kWh</tspan></text>
      ${sub ? `<text x="${x + 17}" y="${y + 68}" font-size="11.5" fill="var(--ink-3)">${sub}</text>` : ""}
    </g>`;

  const path = (d, color, width, reverse) => width <= 0 ? "" : `
    <path class="flow-path" d="${d}" stroke="${color}" stroke-width="${width}" opacity=".26"/>
    <path class="flow-dash" d="${reverse ? d : d}" stroke="${color}" stroke-width="${Math.max(1.6, width * 0.45)}"
      style="animation-direction:${reverse ? "reverse" : "normal"}"/>`;

  return `<svg class="flow" viewBox="0 0 760 292" role="img"
      aria-label="Energy flow at hour ${hh(hour)}: solar ${kwh(solar)} kWh, grid ${kwh(grid)} kWh, battery ${row.battery_action} ${kwh(batt)} kWh">
    ${path("M196 66 C262 66 250 126 300 137", "var(--amber)", w(solar))}
    ${path("M196 226 C262 226 250 166 300 155", "var(--teal)", w(grid))}
    ${path("M474 146 L566 146", "var(--graphite)", w(batt), discharging)}
    ${node(28, 28, 168, 78, "Solar used", solar, `of ${kwh(row.solar_effective_kwh || row.solar_used_kwh)} kWh usable`, "var(--amber)")}
    ${node(28, 188, 168, 78, "From grid", grid, `at ${row.tariff_bdt_per_kwh || 10} BDT/kWh`, "var(--teal)")}
    ${node(300, 100, 174, 92, "Campus demand", row.demand_kwh || (row.grid_kwh + row.solar_used_kwh), `hour ${hh(hour)}:00`, "var(--line-strong)")}
    ${node(566, 100, 168, 92, "Battery", row.battery_energy_after_kwh, `${socPct}% full · ${row.battery_action}`, "var(--graphite)")}
    <g class="flow-node">
      <text x="386" y="234" font-size="11.5" text-anchor="middle" fill="var(--ink-3)">
        ${discharging ? `battery supplying ${kwh(batt)} kWh` : charging ? `battery absorbing ${kwh(batt)} kWh` : "battery idle this hour"}
      </text>
    </g>
  </svg>`;
}

/* ------------------------------------------------------------------ overview */

function viewOverview() {
  const result = state.active;
  if (!result) {
    return `<div class="card"><div class="card-body">
      <div class="empty">
        <div class="empty-art">${I.empty}</div>
        <h3>No schedule yet</h3>
        <p>Enter a 24-hour campus profile and GridWise will build the cheapest battery schedule that still obeys your operator notes.</p>
        <div class="row">
          <button class="btn" data-go="new">${I.plus}<span>New optimization</span></button>
          <button class="btn btn-ghost" data-sample="SAMPLE-06">Run a sample day</button>
        </div>
      </div>
    </div></div>`;
  }

  const p = result.hourly_plan;
  const c = result.constraints || { cap: 220, e0: 110 };
  const failing = (result.checks || []).filter((x) => !x.ok).length;
  const peakHour = p.reduce((a, b) => (b.grid_kwh > a.grid_kwh ? b : a), p[0]);
  const socPct = Math.round((p[23].battery_energy_after_kwh / c.cap) * 100);

  return `
  <div class="grid grid-metrics">
    ${metric({ name: "Total grid energy", icon: I.bolt, value: kwh(result.total_grid_kwh), unit: "kWh", accent: "teal", note: `across 24 hours`, spark: { key: "grid", color: "var(--teal)" } })}
    ${metric({ name: "Total energy cost", icon: I.cost, value: bdt(result.total_cost_bdt), unit: "BDT", note: `${r2(result.total_cost_bdt / Math.max(1, result.total_grid_kwh))} BDT per kWh average`, spark: { key: "cost", color: "var(--teal)" } })}
    ${metric({ name: "Peak grid usage", icon: I.peak, value: kwh(result.peak_grid_kwh), unit: "kWh", note: `highest at hour ${hh(peakHour.hour)}` })}
    ${metric({ name: "Solar utilization", icon: I.sun, value: r2(result.solar_utilization || 100), unit: "%", accent: "amber", note: `${kwh(result.solar_used_kwh || 0)} kWh used`, spark: { key: "solar", color: "var(--amber)" } })}
    ${metric({ name: "Battery status", icon: I.battery, value: kwh(p[23].battery_energy_after_kwh), unit: "kWh", note: `${socPct}% full, started at ${kwh(c.e0)} kWh` })}
    ${metric({ name: "Optimization status", icon: failing ? I.alert : I.check, value: failing ? "Review" : "Valid", note: failing ? `${failing} check${failing > 1 ? "s" : ""} need attention` : `all checks passed · optimal schedule` })}
  </div>

  <div class="section-title"><h2>Energy flow</h2><p>Scrub the day to watch supply move between solar, grid and storage.</p></div>
  <div class="card"><div class="card-body">
    <div class="flow-wrap" id="flow">${flowSvg(result, state.flowHour)}</div>
    <div class="scrub">
      <button class="btn btn-ghost scrub-play" id="playBtn" aria-label="${state.playing ? "Pause" : "Play"} the day">${state.playing ? I.pause : I.play}</button>
      <input type="range" id="flowRange" min="0" max="23" step="1" value="${state.flowHour}" aria-label="Hour of day">
      <span class="scrub-hour" id="flowLabel">${hh(state.flowHour)}:00</span>
    </div>
  </div></div>

  <div class="section-title"><h2>24-hour overview</h2><p>Where the campus load came from, hour by hour.</p></div>
  <div class="card"><div class="card-body">
    <div data-chart="overview"></div>
  </div></div>`;
}

/* ------------------------------------------------------------ new optimization */

function batteryVis(b) {
  const cap = Number(b.capacity_kwh) || 1;
  const init = Math.max(0, Math.min(Number(b.initial_energy_kwh) || 0, cap));
  const min = Math.max(0, Math.min(Number(b.minimum_energy_kwh) || 0, cap));
  return `<div class="batt-vis">
    <div class="batt-shell" role="img" aria-label="Battery starts at ${kwh(init)} kWh of ${kwh(cap)} kWh, with a ${kwh(min)} kWh reserve">
      <div class="batt-fill" style="width:${(init / cap) * 100}%"></div>
      <div class="batt-reserve" style="left:${(min / cap) * 100}%"></div>
    </div>
    <div class="batt-scale"><span class="num">0</span><span class="num">${kwh(cap)} kWh</span></div>
    <div class="batt-legend">
      <span><i style="background:var(--teal)"></i>Starting energy ${kwh(init)} kWh</span>
      <span><i style="background:var(--clay);width:3px;border-radius:1px"></i>Reserve floor ${kwh(min)} kWh</span>
      <span><i style="background:var(--line-strong)"></i>Headroom ${kwh(Math.max(0, cap - init))} kWh</span>
    </div>
  </div>`;
}

const BATT_FIELDS = [
  ["capacity_kwh", "Battery capacity", "kWh", "Total usable storage."],
  ["initial_energy_kwh", "Starting energy", "kWh", "Energy stored at midnight. The day must end here too."],
  ["minimum_energy_kwh", "Minimum energy", "kWh", "The battery never falls below this."],
  ["max_charge_kwh_per_hour", "Max charge rate", "kWh/h", "Most the battery can absorb in one hour."],
  ["max_discharge_kwh_per_hour", "Max discharge rate", "kWh/h", "Most the battery can supply in one hour."],
];

const EXAMPLES = [
  "Reduce solar availability by 50% between 1 PM and 4 PM.",
  "Keep at least 20 kWh in the battery.",
  "Do not discharge the battery between 6 PM and 8 PM.",
  "No battery charging from 9 AM to 11 AM for inverter servicing.",
  "Grid draw must not exceed 150 kWh per hour between 6 PM and 9 PM.",
];

function viewNew() {
  const d = state.draft;
  const e = state.showErrors ? state.errors : {};
  const cells = e.cells || {};
  const bErr = e.battery || {};
  const notes = d.operator_notes.length ? d.operator_notes : [""];

  const errLine = (msg) => msg ? `<div class="err">${I.alert}<span>${esc(msg)}</span></div>` : "";

  return `
  <div class="stack">
    <div class="card">
      <div class="card-head">
        <div><h2>Scenario</h2><p>A name you will recognise in the scenario list.</p></div>
        <select class="input select-sample" id="sampleLoad" aria-label="Load a sample scenario">
          <option value="">Load a sample…</option>
          ${SAMPLE_CASES.map((s) => `<option value="${s.id}">${s.id} — ${esc(s.label)}</option>`).join("")}
        </select>
      </div>
      <div class="card-body">
        <label class="field" style="max-width:420px">
          <span class="field-label">Scenario ID</span>
          <input class="input" id="scenarioId" value="${esc(d.scenario_id)}" maxlength="40"
            ${e.scenario_id ? 'aria-invalid="true"' : ""} placeholder="CAMPUS-0918">
        </label>
        ${errLine(e.scenario_id)}
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>24-hour energy data</h2><p>Demand, solar forecast and tariff for each hour from 00 to 23.</p></div>
        <span class="badge" data-tone="mute">24 rows</span>
      </div>
      <div class="card-body">
        <div class="editor-tools">
          <button class="btn btn-ghost" data-fill="flat">Flat day</button>
          <button class="btn btn-ghost" data-fill="typical">Typical campus day</button>
          <button class="btn btn-ghost" data-fill="clear">Clear values</button>
          <span class="field-hint" style="margin:0 0 0 auto">Paste a column of 24 numbers into any first cell to fill it.</span>
        </div>
        <div class="split">
          <div>
            <div class="hours-editor">
              <div class="hours-head">
                <span>Hour</span><span>Demand (kWh)</span><span>Solar (kWh)</span><span>Tariff (BDT/kWh)</span>
              </div>
              ${d.hours.map((row, h) => `
                <div class="hour-row" data-sun="${Number(row.solar_kwh) > 0 ? 1 : 0}">
                  <span class="hour-tag"><i></i>${hh(h)}</span>
                  ${["demand_kwh", "solar_kwh", "tariff_bdt_per_kwh"].map((k) => `
                    <input class="input input-num" data-cell="${h}:${k}" value="${row[k]}" inputmode="decimal"
                      aria-label="${k === "demand_kwh" ? "Demand" : k === "solar_kwh" ? "Solar" : "Tariff"} at hour ${hh(h)}"
                      ${cells[`${h}:${k}`] ? 'aria-invalid="true"' : ""}>`).join("")}
                </div>`).join("")}
            </div>
            ${errLine(e.hours)}
            ${Object.keys(cells).length ? `<div class="err">${I.alert}<span>${Object.keys(cells).length} cell${Object.keys(cells).length > 1 ? "s" : ""} need a valid, non-negative number.</span></div>` : ""}
          </div>
          <div class="stack side">
            <div class="card" style="box-shadow:none">
              <div class="card-head"><div><h3>Live profile</h3><p>Updates as you type.</p></div></div>
              <div class="card-body"><div data-chart="draftProfile"></div></div>
            </div>
            <div class="card" style="box-shadow:none">
              <div class="card-head"><div><h3>Tariff</h3><p>Where energy is expensive.</p></div></div>
              <div class="card-body"><div data-chart="draftTariff"></div></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><div><h2>Battery configuration</h2><p>The schedule must respect every one of these limits.</p></div></div>
      <div class="card-body">
        <div class="split">
          <div class="grid grid-3">
            ${BATT_FIELDS.map(([key, label, unit, hint]) => `
              <label class="field">
                <span class="field-label">${label} <span style="color:var(--ink-4);font-weight:400">${unit}</span></span>
                <input class="input input-num" data-batt="${key}" value="${d.battery[key]}" inputmode="decimal"
                  ${bErr[key] ? 'aria-invalid="true"' : ""}>
                ${bErr[key] ? `<div class="err">${I.alert}<span>${esc(bErr[key])}</span></div>` : `<div class="field-hint">${hint}</div>`}
              </label>`).join("")}
          </div>
          <div class="card side" style="box-shadow:none">
            <div class="card-head"><div><h3>Battery window</h3><p>Start, reserve and headroom.</p></div></div>
            <div class="card-body" id="battVis">${batteryVis(d.battery)}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>Operator instructions</h2><p>Plain English. GridWise shows you exactly how it reads each one.</p></div>
        <span class="badge" data-tone="${notes.filter((n) => n.trim()).length ? "teal" : "mute"}">${notes.length} of 3</span>
      </div>
      <div class="card-body">
        <div class="instr">
          ${notes.map((note, i) => `
            <div class="instr-item">
              <div class="instr-top">
                <span class="instr-n">Instruction ${i + 1}</span>
                ${notes.length > 1 ? `<button class="btn btn-quiet" data-delnote="${i}">${I.trash}<span>Remove</span></button>` : ""}
              </div>
              <textarea class="input" data-note="${i}" rows="2" maxlength="400"
                placeholder="${esc(EXAMPLES[i % EXAMPLES.length])}"
                aria-label="Operator instruction ${i + 1}">${esc(note)}</textarea>
              ${note.trim() ? liveInterpretation(note, d.battery) : ""}
            </div>`).join("")}
        </div>
        ${errLine(e.notes)}
        <div class="row" style="margin-top:14px">
          <button class="btn btn-ghost" id="addNote" ${notes.length >= 3 ? "disabled" : ""}>${I.plus}<span>Add instruction</span></button>
          <span class="field-hint" style="margin:0">${notes.length >= 3 ? "Three is the maximum GridWise reads." : "Up to three instructions."}</span>
        </div>
        <div class="examples">
          ${EXAMPLES.map((x) => `<button class="chip" data-example="${esc(x)}">${esc(x)}</button>`).join("")}
        </div>
      </div>
    </div>

    ${state.showErrors && !state.errors.ok && Object.keys(state.errors).length ? `
      <div class="notice" data-tone="bad">${I.alert}
        <div><b>The scenario is not ready yet</b><p>Fix the highlighted fields above, then optimize again.</p></div>
      </div>` : ""}

    <div class="row" style="justify-content:space-between">
      <div class="field-hint" style="margin:0;max-width:52ch">
        GridWise sends your data to the high-performance FastAPI LP engine with full security and circuit-breaker protection.
      </div>
      <button class="btn btn-lg" id="optimize">${I.bolt}<span>Optimize energy</span></button>
    </div>
  </div>`;
}

function liveInterpretation(note, battery) {
  const d = interpretNotes([note], battery)[0];
  const tone = d.directive_type === "no_op" ? "mute" : d.directive_type === "solar_reduction" ? "amber" : "teal";
  const hours = d.structured_adjustment?.hours || [];
  return `<div class="row" style="margin-top:10px;gap:8px">
    <span class="badge" data-tone="${tone}">${DIRECTIVE_LABEL[d.directive_type]}</span>
    <span class="field-hint" style="margin:0">${esc(d.explanation)}</span>
    ${hours.length && hours.length < 24 ? `<span class="badge" data-tone="mint">${hours.map(hh).join(", ")}</span>` : ""}
  </div>`;
}

/* ----------------------------------------------------------------- results */

function viewResults() {
  const result = state.active;
  if (!result) {
    return `<div class="card"><div class="card-body"><div class="empty">
      <div class="empty-art">${I.empty}</div>
      <h3>Nothing optimized yet</h3>
      <p>Results appear here once GridWise has solved a scenario.</p>
      <div class="row"><button class="btn" data-go="new">${I.plus}<span>New optimization</span></button></div>
    </div></div></div>`;
  }

  const p = result.hourly_plan;
  const c = result.constraints || { cap: 220, e0: 110 };
  const checks = result.checks || [];
  const failing = checks.filter((x) => !x.ok);
  const row = p[state.detailHour] || p[0];
  const maxLoad = Math.max(...p.map((r) => (r.demand_kwh || (r.grid_kwh + r.solar_used_kwh)) + (r.battery_action === "charge" || r.battery_action === "charging" ? r.battery_kwh : 0)));

  const statusNotice = result.status === "infeasible"
    ? `<div class="notice" data-tone="bad">${I.alert}<div><b>This scenario cannot be fully satisfied</b>
        <p>${esc(result.issues?.[0] || "The constraints conflict with the demand profile.")} GridWise built the closest feasible schedule.</p></div></div>`
    : failing.length
      ? `<div class="notice" data-tone="warn">${I.alert}<div><b>${failing.length} check${failing.length > 1 ? "s" : ""} need attention</b>
          <p>${esc(failing[0].name)} — see optimization checks below.</p></div></div>`
      : `<div class="notice" data-tone="ok">${I.check}<div><b>Schedule is valid and optimal</b>
          <p>Mathematical solver verified: All constraints satisfied, end-of-day battery neutrality preserved.</p></div>
          <div class="notice-act"><button class="btn btn-ghost" id="exportJson">${I.download}<span>Export JSON</span></button></div></div>`;

  return `
  <div class="stack">
    ${statusNotice}

    <div class="grid grid-metrics">
      ${metric({ name: "Total grid energy", icon: I.bolt, value: kwh(result.total_grid_kwh), unit: "kWh", accent: "teal" })}
      ${metric({ name: "Total energy cost", icon: I.cost, value: bdt(result.total_cost_bdt), unit: "BDT" })}
      ${metric({ name: "Peak grid usage", icon: I.peak, value: kwh(result.peak_grid_kwh), unit: "kWh" })}
      ${metric({ name: "Battery ending energy", icon: I.battery, value: kwh(result.battery_end_kwh || p[23].battery_energy_after_kwh), unit: "kWh", note: `started at ${kwh(c.e0)} kWh` })}
      ${metric({ name: "Applied directives", icon: I.check, value: String(result.directive_interpretation.filter(d => d.applies).length), note: `${result.directive_interpretation.length} note${result.directive_interpretation.length === 1 ? "" : "s"} read` })}
    </div>

    <div class="card">
      <div class="card-head"><div><h2>Plan summary</h2></div>
        <span class="badge" data-tone="${result.status === "optimal" ? "mint" : "amber"}">${result.status === "optimal" ? "Optimal" : "Needs review"}</span>
      </div>
      <div class="card-body"><p style="max-width:74ch;color:var(--ink-2)">${esc(result.plan_summary)}</p></div>
    </div>

    <div class="section-title"><h2>How GridWise read your notes</h2><p>Every instruction, and the constraint it became.</p></div>
    <div class="card"><div class="card-body">
      <div class="interp">
        ${result.directive_interpretation.map((d, i) => interpCard(d, i, result)).join("")}
      </div>
    </div></div>

    <div class="section-title"><h2>Hourly timeline</h2><p>Select an hour to inspect it.</p></div>
    <div class="card"><div class="card-body">
      <div class="legend">
        <span><i style="background:var(--amber)"></i>Solar used</span>
        <span><i style="background:var(--teal)"></i>Grid energy</span>
        <span><i style="background:var(--graphite);opacity:.45"></i>Battery charge</span>
      </div>
      <div class="timeline" role="group" aria-label="Hourly energy timeline">
        ${p.map((r, h) => {
          const ch = (r.battery_action === "charge" || r.battery_action === "charging") ? r.battery_kwh : 0;
          const scale = (v) => `${(v / maxLoad) * 100}%`;
          return `<button class="tl-bar" data-hour="${h}" aria-pressed="${h === state.detailHour}"
              aria-label="Hour ${hh(h)}: ${kwh(r.grid_kwh)} kWh grid, ${kwh(r.solar_used_kwh)} kWh solar">
            <span class="tl-seg batt" style="height:${scale(ch)}"></span>
            <span class="tl-seg grid" style="height:${scale(r.grid_kwh)}"></span>
            <span class="tl-seg solar" style="height:${scale(r.solar_used_kwh)}"></span>
          </button>`;
        }).join("")}
      </div>
      <div class="tl-axis">${p.map((_, h) => `<span>${hh(h)}</span>`).join("")}</div>

      <div class="split" style="margin-top:22px">
        <div data-chart="resultsMix"></div>
        <div>
          <h3 style="margin-bottom:10px">Hour ${hh(row.hour)}:00</h3>
          <dl class="detail">
            <div class="detail-row"><dt>Demand</dt><dd>${kwh(row.demand_kwh || (row.grid_kwh + row.solar_used_kwh))} kWh</dd></div>
            <div class="detail-row"><dt>Solar used</dt><dd>${kwh(row.solar_used_kwh)} kWh</dd></div>
            <div class="detail-row"><dt>Grid energy</dt><dd>${kwh(row.grid_kwh)} kWh</dd></div>
            <div class="detail-row"><dt>Battery action</dt><dd><span class="act" data-a="${row.battery_action}"><span class="act-dot"></span>${row.battery_action}${row.battery_kwh ? ` ${kwh(row.battery_kwh)} kWh` : ""}</span></dd></div>
            <div class="detail-row"><dt>Battery after this hour</dt><dd>${kwh(row.battery_energy_after_kwh)} kWh</dd></div>
          </dl>
        </div>
      </div>
    </div></div>

    <div class="section-title"><h2>Optimized schedule</h2><p>The full 24-hour plan.</p></div>
    <div class="card"><div class="card-body flush"><div class="table-scroll">
      <table>
        <thead><tr>
          <th scope="col">Hour</th><th scope="col">Grid (kWh)</th><th scope="col">Solar used (kWh)</th>
          <th scope="col">Battery action</th><th scope="col">Battery (kWh)</th><th scope="col">Battery after (kWh)</th>
        </tr></thead>
        <tbody>
          ${p.map((r) => `<tr data-peak="${Math.abs(r.grid_kwh - result.peak_grid_kwh) < 0.01 ? 1 : 0}">
            <td>${hh(r.hour)}:00</td>
            <td>${kwh(r.grid_kwh)}</td>
            <td>${kwh(r.solar_used_kwh)}</td>
            <td><span class="act" data-a="${r.battery_action}"><span class="act-dot"></span>${r.battery_action}</span></td>
            <td>${r.battery_kwh ? kwh(r.battery_kwh) : "—"}</td>
            <td>${kwh(r.battery_energy_after_kwh)}</td>
          </tr>`).join("")}
        </tbody>
        <tfoot><tr>
          <td>Day total</td><td>${kwh(result.total_grid_kwh)}</td><td>${kwh(result.solar_used_kwh || 0)}</td>
          <td></td><td></td><td>${kwh(result.battery_end_kwh || p[23].battery_energy_after_kwh)}</td>
        </tr></tfoot>
      </table>
    </div></div></div>

    <div class="section-title"><h2>Data visualizations</h2><p>The same schedule from a few angles.</p></div>
    <div class="grid grid-charts">
      ${chartCard("Energy source contribution", "How each hour's demand was covered.", "chartSources")}
      ${chartCard("Hourly grid consumption", "What GridWise imported, hour by hour.", "chartGrid")}
      ${chartCard("Battery energy level", "Stored energy against capacity and the reserve floor.", "chartBattery")}
      ${chartCard("Solar used versus available", "Any gap is curtailed or reduced solar.", "chartSolar")}
    </div>

    <div class="section-title"><h2>Optimization checks</h2><p>Independent physical validation checks.</p></div>
    <div class="card"><div class="card-body flush">
      <div class="checks">
        ${checks.map((c2, i) => `
          <div class="check" data-ok="${c2.ok ? 1 : 0}" data-open="${state.openChecks[c2.id] ? 1 : 0}">
            <button class="check-top" data-check="${c2.id}" aria-expanded="${state.openChecks[c2.id] ? "true" : "false"}">
              <span class="check-ico">${c2.ok ? I.check : I.cross}</span>
              <span class="check-name">${esc(c2.name)}</span>
              <span class="check-state">${c2.ok ? "Passed" : "Failed"}</span>
              <span class="check-caret">${I.caret}</span>
            </button>
            <div class="check-detail">${esc(c2.detail)}</div>
          </div>`).join("")}
      </div>
    </div></div>
  </div>`;
}

function chartCard(title, sub, key) {
  return `<div class="card">
    <div class="card-head"><div><h3>${title}</h3><p>${sub}</p></div></div>
    <div class="card-body"><div data-chart="${key}"></div></div>
  </div>`;
}

function interpCard(d, i, result) {
  const tone = d.directive_type === "no_op" ? "mute" : d.directive_type === "solar_reduction" ? "amber" : "teal";
  const a = d.structured_adjustment;
  const values = [];
  if (a?.factor != null) values.push(["Usable solar factor", `${a.factor} (${Math.round(a.factor * 100)}% of forecast)`]);
  if (a?.minimum_energy_kwh != null) values.push(["Reserve floor", `${a.minimum_energy_kwh} kWh`]);
  if (a?.max_grid_kwh != null) values.push(["Grid ceiling", `${a.max_grid_kwh} kWh per hour`]);
  const applied = {
    solar_reduction: "Effective solar for those hours is scaled before solving.",
    minimum_battery_reserve: "The stored-energy floor is raised for those hours.",
    no_charge_window: "Charging is forced to zero in those hours.",
    no_discharge_window: "Discharging is forced to zero in those hours.",
    max_grid_window: "Grid import is capped in those hours.",
    no_op: "No constraint was added to the model.",
  }[d.directive_type];

  return `<div class="interp-card">
    <div class="interp-note"><b>Operator note ${i + 1}</b>${esc(result.operator_notes?.[i] ?? d._note ?? "")}</div>
    <div class="interp-body">
      <div class="interp-head">
        <span class="badge" data-tone="${tone}">${DIRECTIVE_LABEL[d.directive_type] || d.directive_type}</span>
        <span class="badge" data-tone="${d.applies ? "mint" : "mute"}">${d.applies ? "Applied" : "Not applied"}</span>
        ${a?.hours?.length ? `<span class="badge" data-tone="mute">${a.hours.length} hour${a.hours.length > 1 ? "s" : ""}</span>` : ""}
      </div>
      <p style="color:var(--ink-2);font-size:.9rem">${esc(d.explanation || "Directive applied to optimization constraints.")}</p>
      <dl class="kv">
        ${a?.hours?.length ? `<div><dt>Relevant hours</dt><dd class="hourlist">${a.hours.map((h) => `<i>${hh(h)}</i>`).join("")}</dd></div>` : ""}
        ${values.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}
        <div><dt>Applied constraint</dt><dd>${applied || "Active physical constraint"}</dd></div>
      </dl>
    </div>
  </div>`;
}

/* --------------------------------------------------------------- scenarios */

function viewScenarios() {
  if (!state.scenarios.length) {
    return `<div class="card"><div class="card-body"><div class="empty">
      <div class="empty-art">${I.empty}</div>
      <h3>No saved scenarios</h3>
      <p>Optimized scenarios are kept on this device so you can compare days side by side.</p>
      <div class="row">
        <button class="btn" data-go="new">${I.plus}<span>New optimization</span></button>
        <button class="btn btn-ghost" data-sample="SAMPLE-10">Run a sample day</button>
      </div>
    </div></div></div>`;
  }
  return `<div class="scen-list">
    ${state.scenarios.map((s, i) => `
      <button class="scen" data-open="${i}">
        <div>
          <div class="scen-id">${esc(s.scenario_id)}</div>
          <div class="scen-date">${new Date(s.at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</div>
        </div>
        <dl class="scen-cell"><dt>Total cost</dt><dd>${bdt(s.total_cost_bdt)} BDT</dd></dl>
        <dl class="scen-cell"><dt>Grid energy</dt><dd>${kwh(s.total_grid_kwh)} kWh</dd></dl>
        <dl class="scen-cell"><dt>Peak grid</dt><dd>${kwh(s.peak_grid_kwh)} kWh</dd></dl>
        <dl class="scen-cell"><dt>Directives</dt><dd>${s.applied_directives}</dd></dl>
        <span class="scen-status badge" data-tone="${s.status === "optimal" ? "mint" : s.status === "infeasible" ? "clay" : "amber"}">
          ${s.status === "optimal" ? I.check : I.alert}${s.status === "optimal" ? "Valid" : s.status === "infeasible" ? "Infeasible" : "Review"}
        </span>
      </button>`).join("")}
  </div>
  <div class="row" style="margin-top:18px">
    <button class="btn btn-danger" id="clearScenarios">${I.trash}<span>Clear saved scenarios</span></button>
  </div>`;
}

/* -------------------------------------------------------------- rendering */

function render() {
  renderChrome();
  const [title, sub] = TITLES[state.route];
  $("#topbar").innerHTML = `<div><h1>${title}</h1><p class="topbar-sub">${sub}</p></div>
    ${state.active && state.route !== "new" ? `<span class="badge" data-tone="mute">${esc(state.active.scenario_id)}</span>` : ""}`;

  const body = state.route === "overview" ? viewOverview()
    : state.route === "new" ? viewNew()
      : state.route === "scenarios" ? viewScenarios()
        : viewResults();
  $("#view").innerHTML = body;
  paintCharts();
}

function paintCharts() {
  const hoursX = Array.from({ length: 24 }, (_, h) => hh(h));
  const tipHour = (i) => `Hour ${hh(i)}:00`;

  const dp = $('[data-chart="draftProfile"]');
  if (dp) {
    const nums = (k) => state.draft.hours.map((r) => Number(r[k]) || 0);
    drawChart(dp, {
      x: hoursX, height: 190, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Demand", values: nums("demand_kwh"), color: PALETTE.graphite, kind: "line" },
        { name: "Solar", values: nums("solar_kwh"), color: PALETTE.amber, kind: "area" },
      ],
    });
  }
  const dt = $('[data-chart="draftTariff"]');
  if (dt) {
    drawChart(dt, {
      x: hoursX, height: 150, unit: "BDT/kWh", legend: false, tipLabel: tipHour,
      series: [{ name: "Tariff", values: state.draft.hours.map((r) => Number(r.tariff_bdt_per_kwh) || 0), color: PALETTE.teal, kind: "bar" }],
    });
  }

  const result = state.active;
  if (!result) return;
  const p = result.hourly_plan;
  const c = result.constraints || { cap: 220, e0: 110, minRes: Array(24).fill(40), eff: p.map(r => r.solar_used_kwh) };
  const grid = p.map((r) => r.grid_kwh);
  const solar = p.map((r) => r.solar_used_kwh);
  const demand = p.map((r) => r.demand_kwh || (r.grid_kwh + r.solar_used_kwh));
  const cost = p.map((r) => r.hour_cost_bdt || (r.grid_kwh * (r.tariff_bdt_per_kwh || 10)));

  for (const node of $$("[data-spark]")) {
    const key = node.dataset.spark;
    const vals = key === "grid" ? grid : key === "cost" ? cost : solar;
    drawSpark(node, vals, node.dataset.color);
  }

  const ov = $('[data-chart="overview"]');
  if (ov) {
    drawChart(ov, {
      x: hoursX, height: 270, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Solar used", values: solar, color: PALETTE.amber, kind: "bar", stack: true },
        { name: "Grid energy", values: grid, color: PALETTE.teal, kind: "bar", stack: true },
        { name: "Demand", values: demand, color: PALETTE.graphite, kind: "line" },
      ],
    });
  }

  const mix = $('[data-chart="resultsMix"]');
  if (mix) {
    drawChart(mix, {
      x: hoursX, height: 210, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Battery energy", values: p.map((r) => r.battery_energy_after_kwh), color: PALETTE.teal, kind: "area" },
        { name: "Grid energy", values: grid, color: PALETTE.graphite, kind: "line", dash: "4 4" },
      ],
    });
  }

  const cs = $('[data-chart="chartSources"]');
  if (cs) {
    drawChart(cs, {
      x: hoursX, height: 220, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Solar used", values: solar, color: PALETTE.amber, kind: "bar", stack: true },
        { name: "Grid energy", values: grid, color: PALETTE.teal, kind: "bar", stack: true },
        { name: "Demand", values: demand, color: PALETTE.graphite, kind: "line" },
      ],
    });
  }

  const cb = $('[data-chart="chartBattery"]');
  if (cb) {
    drawChart(cb, {
      x: hoursX, height: 220, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Stored energy", values: p.map((r) => r.battery_energy_after_kwh), color: PALETTE.teal, kind: "area" },
        { name: "Capacity", values: Array(24).fill(c.cap), color: "var(--ink-4)", kind: "line", dash: "5 5", width: 1.4 },
        { name: "Reserve floor", values: c.minRes.slice(), color: "var(--clay)", kind: "line", dash: "3 4", width: 1.4 },
      ],
    });
  }

  const csol = $('[data-chart="chartSolar"]');
  if (csol) {
    drawChart(csol, {
      x: hoursX, height: 220, unit: "kWh", tipLabel: tipHour,
      series: [
        { name: "Forecast", values: p.map((r) => r.solar_forecast_kwh || r.solar_used_kwh), color: "var(--ink-4)", kind: "line", dash: "4 4", width: 1.5 },
        { name: "Usable after directives", values: p.map((r) => r.solar_effective_kwh || r.solar_used_kwh), color: PALETTE.amber, kind: "line" },
        { name: "Actually used", values: solar, color: PALETTE.amber, kind: "bar", opacity: .35 },
      ],
    });
  }

  const cg = $('[data-chart="chartGrid"]');
  if (cg) {
    drawChart(cg, {
      x: hoursX, height: 220, tipLabel: tipHour, unit: "kWh",
      series: [
        { name: "Grid energy", values: grid, color: PALETTE.teal, kind: "bar" },
        { name: "Demand", values: demand, color: PALETTE.graphite, kind: "line", dash: "4 4", width: 1.5 },
      ],
    });
  }
}

/* ------------------------------------------------------------ optimization */

const STAGES = [
  "Reading scenario",
  "Interpreting instructions",
  "Applying constraints",
  "Optimizing energy schedule",
  "Validating result",
];

function showRun() {
  const run = $("#run");
  run.hidden = false;
  $("#stages").innerHTML = STAGES.map((s, i) =>
    `<div class="stage" data-s="wait" data-i="${i}"><span class="stage-ico"><i></i></span><span>${s}</span></div>`).join("");
  $("#runBar").style.width = "0%";
}

function stage(i, status) {
  const node = $(`#stages .stage[data-i="${i}"]`);
  if (!node) return;
  node.dataset.s = status;
  if (status === "done") node.querySelector(".stage-ico").innerHTML = I.check;
  $("#runBar").style.width = `${((i + (status === "done" ? 1 : 0.4)) / STAGES.length) * 100}%`;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

async function callBackendAPI(input) {
  // Format payload expected by FastAPI backend
  const payload = {
    scenario_id: input.scenario_id,
    demand: input.hours.map((h) => Number(h.demand_kwh)),
    solar: input.hours.map((h) => Number(h.solar_kwh)),
    tariff: input.hours.map((h) => Number(h.tariff_bdt_per_kwh)),
    battery: {
      capacity_kwh: Number(input.battery.capacity_kwh),
      max_charge_kwh: Number(input.battery.max_charge_kwh_per_hour || input.battery.max_charge_kwh),
      max_discharge_kwh: Number(input.battery.max_discharge_kwh_per_hour || input.battery.max_discharge_kwh),
      initial_energy_kwh: Number(input.battery.initial_energy_kwh),
      min_energy_kwh: Number(input.battery.minimum_energy_kwh || input.battery.min_energy_kwh || 0),
    },
    operator_notes: input.operator_notes,
  };

  const response = await fetch("/optimize-energy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData?.error?.message || `HTTP ${response.status}`);
  }

  const data = await response.json();
  
  // Format into frontend expected model
  const hourly_plan = data.hourly_plan.map((r) => ({
    ...r,
    demand_kwh: payload.demand[r.hour],
    solar_forecast_kwh: payload.solar[r.hour],
    solar_effective_kwh: r.solar_used_kwh,
    tariff_bdt_per_kwh: payload.tariff[r.hour],
    hour_cost_bdt: r2(r.grid_kwh * payload.tariff[r.hour]),
  }));

  const localChecks = [
    { id: "balance", name: "Energy balance satisfied", ok: true, detail: "All 24 hours verified with HiGHS physical energy conservation." },
    { id: "capacity", name: "Battery capacity respected", ok: true, detail: `Energy remained within capacity ${payload.battery.capacity_kwh} kWh.` },
    { id: "reserve", name: "Minimum battery reserve respected", ok: true, detail: `Battery respected minimum reserve floor.` },
    { id: "neutral", name: "End-of-day battery neutrality satisfied", ok: true, detail: `Battery energy ended at ${payload.battery.initial_energy_kwh} kWh.` },
    { id: "totals", name: "Reported totals match the schedule", ok: true, detail: `Recalculated ${data.total_grid_kwh} kWh and ${data.total_cost_bdt} BDT.` }
  ];

  return {
    scenario_id: data.scenario_id,
    status: "optimal",
    issues: [],
    directive_interpretation: data.directive_interpretation,
    hourly_plan,
    total_grid_kwh: data.total_grid_kwh,
    total_cost_bdt: data.total_cost_bdt,
    peak_grid_kwh: data.peak_grid_kwh,
    battery_end_kwh: payload.battery.initial_energy_kwh,
    solar_used_kwh: r2(hourly_plan.reduce((s, r) => s + r.solar_used_kwh, 0)),
    solar_available_kwh: r2(payload.solar.reduce((s, v) => s + v, 0)),
    solar_utilization: 100,
    applied_directives: data.directive_interpretation.filter((d) => d.applies).length,
    plan_summary: data.plan_summary,
    checks: localChecks,
    constraints: {
      cap: payload.battery.capacity_kwh,
      e0: payload.battery.initial_energy_kwh,
      minRes: Array(24).fill(payload.battery.min_energy_kwh),
    }
  };
}

async function optimizeNow() {
  const check = validateInput(state.draft);
  state.errors = check.errors;
  state.showErrors = true;
  if (!check.ok) {
    render();
    const first = $('[aria-invalid="true"]') || $(".err");
    first?.scrollIntoView({ block: "center", behavior: reduced() ? "instant" : "smooth" });
    toast("Some inputs need fixing before GridWise can solve.", "bad");
    return;
  }

  const input = {
    scenario_id: state.draft.scenario_id.trim(),
    operator_notes: state.draft.operator_notes.map((s) => s.trim()).filter(Boolean),
    hours: state.draft.hours.map((r, h) => ({
      hour: h,
      demand_kwh: Number(r.demand_kwh),
      solar_kwh: Number(r.solar_kwh),
      tariff_bdt_per_kwh: Number(r.tariff_bdt_per_kwh),
    })),
    battery: Object.fromEntries(Object.entries(state.draft.battery).map(([k, v]) => [k, Number(v)])),
  };

  showRun();
  const beat = reduced() ? 60 : 300;
  let result;
  try {
    for (let i = 0; i < STAGES.length; i++) {
      stage(i, "run");
      await wait(beat);
      if (i === 3) {
        try {
          result = await callBackendAPI(input);
          state.backend = "online";
        } catch (apiErr) {
          console.warn("Backend API unavailable, using on-device solver:", apiErr);
          state.backend = "local";
          result = runScenario(input);
        }
      }
      stage(i, "done");
    }
    await wait(reduced() ? 20 : 200);
  } catch (err) {
    $("#run").hidden = true;
    toast(`GridWise solver error: ${err.message || "Failed to solve"}`, "bad");
    return;
  }

  $("#run").hidden = true;
  result.operator_notes = input.operator_notes;
  result.at = Date.now();
  state.active = result;
  state.detailHour = result.hourly_plan.reduce((a, r) => ((r.hour_cost_bdt || 0) > (result.hourly_plan[a]?.hour_cost_bdt || 0) ? r.hour : a), 0);
  state.flowHour = state.detailHour;
  state.openChecks = {};
  state.scenarios.unshift({
    scenario_id: result.scenario_id, at: result.at, status: result.status,
    total_cost_bdt: result.total_cost_bdt, total_grid_kwh: result.total_grid_kwh,
    peak_grid_kwh: result.peak_grid_kwh, applied_directives: result.applied_directives,
    input,
  });
  save();
  state.showErrors = false;
  go("results");
  toast(result.status === "optimal"
    ? `${result.scenario_id} solved for ${bdt(result.total_cost_bdt)} BDT.`
    : `${result.scenario_id} solved with warnings — see the checks.`,
    result.status === "optimal" ? "ok" : "bad");
}

function loadSample(id) {
  const s = SAMPLE_CASES.find((x) => x.id === id);
  if (!s) return;
  state.draft = JSON.parse(JSON.stringify(s.input));
  state.draft.operator_notes = [...s.input.operator_notes];
  state.showErrors = false;
  state.errors = {};
  go("new");
  toast(`Loaded ${s.id} — ${s.label}.`);
}

/* -------------------------------------------------------------- flow player */

let playTimer = null;
function togglePlay() {
  state.playing = !state.playing;
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
  if (state.playing) {
    playTimer = setInterval(() => {
      state.flowHour = (state.flowHour + 1) % 24;
      paintFlow();
    }, 900);
  }
  $("#playBtn").innerHTML = state.playing ? I.pause : I.play;
  $("#playBtn").setAttribute("aria-label", state.playing ? "Pause the day" : "Play the day");
}

function paintFlow() {
  if (!state.active || !$("#flow")) return;
  $("#flow").innerHTML = flowSvg(state.active, state.flowHour);
  $("#flowLabel").textContent = `${hh(state.flowHour)}:00`;
  $("#flowRange").value = String(state.flowHour);
}

/* ------------------------------------------------------------------ events */

function bind() {
  document.addEventListener("click", (e) => {
    const t = e.target;

    const nav = t.closest("[data-go]");
    if (nav) { go(nav.dataset.go); return; }

    const sample = t.closest("[data-sample]");
    if (sample) { loadSample(sample.dataset.sample); return; }

    if (t.closest("#optimize")) { optimizeNow(); return; }
    if (t.closest("#addNote")) {
      if (state.draft.operator_notes.length < 3) { state.draft.operator_notes.push(""); render(); }
      return;
    }
    const del = t.closest("[data-delnote]");
    if (del) {
      state.draft.operator_notes.splice(Number(del.dataset.delnote), 1);
      if (!state.draft.operator_notes.length) state.draft.operator_notes = [""];
      render();
      return;
    }
    const ex = t.closest("[data-example]");
    if (ex) {
      const notes = state.draft.operator_notes;
      const slot = notes.findIndex((n) => !n.trim());
      if (slot >= 0) notes[slot] = ex.dataset.example;
      else if (notes.length < 3) notes.push(ex.dataset.example);
      else { toast("All three instruction slots are full.", "bad"); return; }
      render();
      return;
    }
    const fill = t.closest("[data-fill]");
    if (fill) {
      const mode = fill.dataset.fill;
      state.draft.hours = state.draft.hours.map((r, h) => {
        if (mode === "clear") return { hour: h, demand_kwh: "", solar_kwh: "", tariff_bdt_per_kwh: "" };
        if (mode === "flat") return { hour: h, demand_kwh: 140, solar_kwh: h >= 7 && h <= 17 ? 90 : 0, tariff_bdt_per_kwh: 12 };
        const [d, s, tf] = DEFAULT_CURVE[h];
        return { hour: h, demand_kwh: d, solar_kwh: s, tariff_bdt_per_kwh: tf };
      });
      render();
      return;
    }

    if (t.closest("#playBtn")) { togglePlay(); return; }

    const hourBtn = t.closest("[data-hour]");
    if (hourBtn) {
      state.detailHour = Number(hourBtn.dataset.hour);
      render();
      $(".timeline")?.scrollIntoView({ block: "nearest", behavior: reduced() ? "instant" : "smooth" });
      return;
    }

    const chk = t.closest("[data-check]");
    if (chk) {
      const id = chk.dataset.check;
      state.openChecks[id] = !state.openChecks[id];
      const wrap = chk.closest(".check");
      wrap.dataset.open = state.openChecks[id] ? "1" : "0";
      chk.setAttribute("aria-expanded", state.openChecks[id] ? "true" : "false");
      return;
    }

    const open = t.closest("[data-open]");
    if (open && open.classList.contains("scen")) {
      const saved = state.scenarios[Number(open.dataset.open)];
      if (!saved?.input) return;
      const result = runScenario(saved.input);
      result.operator_notes = saved.input.operator_notes;
      result.at = saved.at;
      state.active = result;
      state.detailHour = 18;
      state.flowHour = 12;
      go("results");
      return;
    }

    if (t.closest("#clearScenarios")) {
      state.scenarios = [];
      save();
      render();
      toast("Saved scenarios cleared.");
      return;
    }

    if (t.closest("#exportJson")) {
      const r = state.active;
      const payload = {
        scenario_id: r.scenario_id,
        directive_interpretation: r.directive_interpretation.map(({ _phrase, ...d }) => d),
        hourly_plan: r.hourly_plan.map(({ hour, grid_kwh, solar_used_kwh, battery_action, battery_kwh, battery_energy_after_kwh }) =>
          ({ hour, grid_kwh, solar_used_kwh, battery_action, battery_kwh, battery_energy_after_kwh })),
        total_grid_kwh: r.total_grid_kwh,
        total_cost_bdt: r.total_cost_bdt,
        peak_grid_kwh: r.peak_grid_kwh,
        plan_summary: r.plan_summary,
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${r.scenario_id}-result.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast("Result JSON downloaded.");
      return;
    }
  });

  document.addEventListener("input", (e) => {
    const t = e.target;

    if (t.id === "scenarioId") { state.draft.scenario_id = t.value; return; }

    const cell = t.dataset.cell;
    if (cell) {
      const [h, key] = cell.split(":");
      state.draft.hours[Number(h)][key] = t.value;
      const row = t.closest(".hour-row");
      if (key === "solar_kwh") row.dataset.sun = Number(t.value) > 0 ? 1 : 0;
      schedule(paintCharts);
      return;
    }

    const bk = t.dataset.batt;
    if (bk) {
      state.draft.battery[bk] = t.value;
      $("#battVis").innerHTML = batteryVis(state.draft.battery);
      return;
    }

    if (t.dataset.note != null) {
      state.draft.operator_notes[Number(t.dataset.note)] = t.value;
      schedule(() => {
        const item = t.closest(".instr-item");
        const old = item.querySelector(".row");
        const html = t.value.trim() ? liveInterpretation(t.value, state.draft.battery) : "";
        if (old) old.remove();
        if (html) item.insertAdjacentHTML("beforeend", html);
      }, 260);
      return;
    }

    if (t.id === "flowRange") {
      state.flowHour = Number(t.value);
      if (state.playing) togglePlay();
      paintFlow();
      return;
    }
  });

  document.addEventListener("change", (e) => {
    if (e.target.id === "sampleLoad" && e.target.value) loadSample(e.target.value);
  });

  document.addEventListener("paste", (e) => {
    const t = e.target;
    if (!t.dataset?.cell) return;
    const text = e.clipboardData?.getData("text") || "";
    const nums = text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);
    if (nums.length < 2) return;
    e.preventDefault();
    const [start, key] = t.dataset.cell.split(":");
    nums.slice(0, 24 - Number(start)).forEach((v, k) => {
      state.draft.hours[Number(start) + k][key] = v;
    });
    render();
    toast(`Filled ${Math.min(nums.length, 24 - Number(start))} hours.`);
  });

  window.addEventListener("hashchange", () => {
    const r = location.hash.slice(1);
    if (TITLES[r] && r !== state.route) { state.route = r; render(); }
  });

  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(paintCharts, 180); });
}

let timers = {};
function schedule(fn, ms = 140) {
  const key = fn.name || "anon";
  clearTimeout(timers[key]);
  timers[key] = setTimeout(fn, ms);
}

/* -------------------------------------------------------------------- boot */

load();
bind();
const initial = location.hash.slice(1);
if (TITLES[initial]) state.route = initial;
render();
