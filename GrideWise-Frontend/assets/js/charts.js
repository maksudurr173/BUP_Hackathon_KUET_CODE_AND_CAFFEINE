/* ==========================================================================
   GridWise charts — small SVG renderer. Line, area, bar, stacked bar and
   grouped series, with a shared hover cursor and tooltip. No dependencies.
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

/**
 * spec = {
 *   x: string[], series: [{ name, values, color, kind: 'line'|'area'|'bar', stack?:bool }],
 *   unit, height, yFrom0, xTickEvery, legend: bool
 * }
 */
export function drawChart(host, spec) {
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

  /* gridlines + y axis */
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

  /* x axis */
  const every = spec.xTickEvery || Math.max(1, Math.ceil(nCat / Math.max(4, Math.floor(iw / 44))));
  for (let i = 0; i < nCat; i++) {
    if (i % every) continue;
    const label = el("text", { x: xMid(i), y: H - 9, "text-anchor": "middle" });
    label.textContent = xs[i];
    gAxis.appendChild(label);
  }
  svg.append(gAxis);

  /* bars (stacked first, then plain bars share the remaining band) */
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

  /* areas and lines */
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

  /* hover layer */
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

/** Tiny inline trend line for metric cards. */
export function drawSpark(host, values, color = "var(--teal)") {
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

export { PALETTE };
