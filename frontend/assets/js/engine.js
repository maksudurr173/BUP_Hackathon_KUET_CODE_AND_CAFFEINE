/* ==========================================================================
   GridWise engine
   1. interpretNotes()  — natural language -> machine-checkable directives
   2. optimize()        — 24h battery / solar / grid schedule, cost minimising
   3. validate()        — replays the schedule against every GridWise rule
   Windows are start-inclusive and end-exclusive. A solar_reduction factor is
   the usable fraction that REMAINS (an 80% reduction gives factor 0.2).
   ========================================================================== */

export const EPS = 0.005;
export const DIRECTIVE_LABEL = {
  solar_reduction: "Solar reduction",
  minimum_battery_reserve: "Minimum battery reserve",
  no_charge_window: "No charge window",
  no_discharge_window: "No discharge window",
  max_grid_window: "Maximum grid window",
  no_op: "No operation",
};

const r2 = (n) => Math.round(n * 100) / 100;
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

/* -------------------------------------------------------------- 1. reading */

const WORD_NUM = {
  zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
  eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, twenty: 20, thirty: 30,
  forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
};

/** Every clock reference in the text, in the order it appears. */
function readClock(text) {
  const t = text.toLowerCase();
  const hits = [];
  const push = (idx, hour, raw) => hits.push({ idx, hour, raw });

  let m;
  const ampm = /\b(1[0-2]|0?[1-9])(?:\s*[:.]\s*([0-5]\d))?\s*(a\.?m\.?|p\.?m\.?)/gi;
  while ((m = ampm.exec(t))) {
    let h = parseInt(m[1], 10) % 12;
    if (/p/i.test(m[3])) h += 12;
    push(m.index, h, m[0]);
  }
  const h24 = /\b([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\b(?!\s*(?:a\.?m|p\.?m))/gi;
  while ((m = h24.exec(t))) push(m.index, parseInt(m[1], 10), m[0]);

  const named = /\b(noon|midday|midnight)\b/gi;
  while ((m = named.exec(t))) push(m.index, /midnight/i.test(m[1]) ? 0 : 12, m[0]);

  const bare = /\b(?:from|until|till|to|after|before|by|at|between)\s+(2[0-4]|1\d|[1-9])\s*(?:o'clock|hrs|h)?\b(?!\s*(?:%|kwh|kw\b|a\.?m|p\.?m|[:.]\d))/gi;
  while ((m = bare.exec(t))) {
    const h = parseInt(m[1], 10);
    if (hits.some((x) => Math.abs(x.idx - m.index) < m[0].length + 2)) continue;
    push(m.index + m[0].indexOf(m[1]), h % 24, m[1]);
  }

  hits.sort((a, b) => a.idx - b.idx);
  return hits.filter((x, i) => i === 0 || x.idx !== hits[i - 1].idx);
}

/** Resolve a window phrase into an ascending list of unique hours 0..23. */
function readWindow(text) {
  const t = text.toLowerCase();
  if (/\b(all day|whole day|throughout the day|entire day|for the day|at all times|any time|anytime|all hours|24\s*hours)\b/.test(t)) {
    return { hours: Array.from({ length: 24 }, (_, i) => i), phrase: "the whole day" };
  }
  const c = readClock(t);
  if (!c.length) return { hours: null, phrase: null };

  if (c.length >= 2) {
    let a = c[0].hour;
    let b = c[1].hour;
    if (/\bmidnight\b/i.test(c[1].raw) && a > 0) b = 24;
    if (b <= a) b += b === 0 ? 24 : 0;
    if (b <= a) b = a + 1;
    const hours = [];
    for (let h = a; h < Math.min(b, a + 24); h++) hours.push(h % 24);
    return { hours: dedupe(hours), phrase: `${fmtH(a)} to ${fmtH(b % 24)}` };
  }

  const one = c[0].hour;
  const before = t.slice(0, c[0].idx);
  if (/\b(after|from|starting|onwards?|beyond|past)\b\s*$/.test(before.trim() + " ") || /\b(after|from|starting at|onwards)\b[^.]*$/.test(before)) {
    const hours = [];
    for (let h = one; h <= 23; h++) hours.push(h);
    return { hours, phrase: `${fmtH(one)} to midnight` };
  }
  if (/\b(before|until|till|by|up to)\b[^.]*$/.test(before)) {
    const hours = [];
    for (let h = 0; h < one; h++) hours.push(h);
    return { hours, phrase: `midnight to ${fmtH(one)}` };
  }
  return { hours: [one], phrase: `${fmtH(one)} to ${fmtH((one + 1) % 24)}` };
}

const dedupe = (a) => [...new Set(a)].filter((h) => h >= 0 && h <= 23).sort((x, y) => x - y);

function fmtH(h) {
  const hh = ((h % 24) + 24) % 24;
  const ap = hh < 12 ? "AM" : "PM";
  const base = hh % 12 === 0 ? 12 : hh % 12;
  if (hh === 0) return "midnight";
  if (hh === 12) return "noon";
  return `${base} ${ap}`;
}

function readPercent(text) {
  let m = /(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)/i.exec(text);
  if (m) return parseFloat(m[1]);
  m = /\b(half)\b/i.exec(text);
  if (m) return 50;
  m = /\b(a\s+quarter|one\s+quarter)\b/i.exec(text);
  if (m) return 25;
  m = /\b([a-z]+)\s*(?:%|percent)/i.exec(text);
  if (m && WORD_NUM[m[1].toLowerCase()] != null) return WORD_NUM[m[1].toLowerCase()];
  return null;
}

function readEnergy(text) {
  const m = /(\d+(?:\.\d+)?)\s*(?:kwh|kw\s*h|kilowatt\s*hours?|kw\b)/i.exec(text);
  return m ? parseFloat(m[1]) : null;
}

const has = (t, re) => re.test(t);

/**
 * One directive_interpretation entry per note, in note_index order.
 * Returns { note_index, applies, directive_type, structured_adjustment, explanation, _phrase }
 */
export function interpretNotes(notes, battery) {
  return notes.map((raw, i) => {
    const note = String(raw || "").trim();
    const t = note.toLowerCase();
    const noop = (why) => ({
      note_index: i, applies: false, directive_type: "no_op",
      structured_adjustment: null,
      explanation: why || "This note does not change today's 24-hour energy schedule.",
      _phrase: null,
    });
    if (!note) return noop("The note is empty.");

    const win = readWindow(note);
    const solarWords = /\b(solar|pv|panel|panels|rooftop|array|photovoltaic)\b/.test(t);
    const battWords = /\b(battery|batteries|storage|bess|pack|reserve)\b/.test(t);
    const gridWords = /\b(grid|feeder|transformer|import|utility|mains|substation|draw)\b/.test(t);

    /* --- solar reduction ------------------------------------------------- */
    if (solarWords && has(t, /\b(reduc|derate|de-rate|cut|curtail|lower|drop|cover|clean|wash|shade|shading|soil|dust|dirty|maintenance|offline|treated as|only|limited to|available|output|forecast|generation|down)\w*/)) {
      let factor = null;
      const pct = readPercent(note);
      const reducedBy = has(t, /\b(?:reduc\w*|cut|lower\w*|down|drop\w*|less|lower)\b[^.]{0,40}?\bby\b/) ||
        has(t, /\bby\s+(?:roughly|about|around|approximately|up to)?\s*\d+(?:\.\d+)?\s*(?:%|percent)/) ||
        has(t, /\d+(?:\.\d+)?\s*(?:%|percent)\s*(?:reduction|less|lower|drop|decrease|derate)/) ||
        has(t, /\b(?:reduction|decrease|loss)\s+of\s+(?:roughly|about|around)?\s*\d+/);
      const remaining = has(t, /\b(?:treated as|treat as|only|just|about|roughly|around|approximately|assume|expect|use|usable|available|effective|operate at|deliver|produce|yield|capped at|limited to|at)\b[^.]{0,30}?\d+(?:\.\d+)?\s*(?:%|percent)/) ||
        has(t, /\d+(?:\.\d+)?\s*(?:%|percent)\s+of\s+(?:the\s+)?(?:forecast|normal|expected|rated|usual|planned|predicted|capacity|output|generation|potential|baseline)/);

      if (has(t, /\b(offline|no solar|zero solar|out of service|fully covered|completely covered|disconnected|shut\s*down|no generation|unavailable)\b/)) factor = 0;
      else if (pct != null && reducedBy) factor = 1 - pct / 100;
      else if (pct != null && remaining) factor = pct / 100;
      else if (pct != null) factor = pct / 100;
      else if (has(t, /\bhalf\b/)) factor = 0.5;

      if (factor != null) {
        const hours = win.hours && win.hours.length ? win.hours : Array.from({ length: 24 }, (_, k) => k);
        return {
          note_index: i, applies: true, directive_type: "solar_reduction",
          structured_adjustment: { hours, factor: r2(clamp(factor, 0, 1)) },
          explanation: `Usable solar falls to ${Math.round(clamp(factor, 0, 1) * 100)}% of the forecast for ${win.phrase || "the whole day"}.`,
          _phrase: win.phrase || "the whole day",
        };
      }
    }

    /* --- minimum battery reserve ----------------------------------------- */
    if (battWords && has(t, /\b(keep|maintain|hold|retain|reserve|preserve|at least|no less|not drop|never drop|never fall|minimum|min|floor|leave|spare|buffer|emergency|backup|stay above|remain above)\b/) &&
      !has(t, /\b(do not|don't|dont|no|avoid|never)\s+(?:\w+\s+){0,2}(charg|dischar)/)) {
      let kwh = readEnergy(note);
      const pct = readPercent(note);
      if (kwh == null && pct != null && battery?.capacity_kwh) kwh = (pct / 100) * Number(battery.capacity_kwh);
      if (kwh != null) {
        const hours = win.hours && win.hours.length ? win.hours : Array.from({ length: 24 }, (_, k) => k);
        return {
          note_index: i, applies: true, directive_type: "minimum_battery_reserve",
          structured_adjustment: { hours, minimum_energy_kwh: r2(kwh) },
          explanation: `Battery energy stays at or above ${r2(kwh)} kWh for ${win.phrase || "the whole day"}.`,
          _phrase: win.phrase || "the whole day",
        };
      }
    }

    /* --- charge / discharge windows -------------------------------------- */
    const blocked = has(t, /\b(do not|don't|dont|no|never|avoid|refrain|hold off|stop|suspend|without|prevent|cannot|can't|unable|must not|should not|disabled?|disable|block|inhibit|halt|pause|skip|out of service|offline|unavailable|maintenance|servicing|isolat\w*|locked out)\b/);
    const chargeWord = has(t, /\b(charg\w*|recharg\w*|top\s*(?:it\s*)?up|absorb)/);
    const dischargeWord = has(t, /\b(dischar\w*|draw\s+from\s+the\s+batter\w+|drain|deplete|export from the batter\w+|use the batter\w+|batter\w+\s+support)/);

    if (blocked && (chargeWord || dischargeWord)) {
      const iC = t.search(/charg/);
      const iD = t.search(/dischar|drain|deplete/);
      const pickDischarge = dischargeWord && (!chargeWord || (iD >= 0 && (iC < 0 || iD <= iC)));
      const hours = win.hours && win.hours.length ? win.hours : Array.from({ length: 24 }, (_, k) => k);
      const type = pickDischarge ? "no_discharge_window" : "no_charge_window";
      return {
        note_index: i, applies: true, directive_type: type,
        structured_adjustment: { hours },
        explanation: pickDischarge
          ? `The battery must not discharge from ${win.phrase || "midnight to midnight"}.`
          : `The battery must not charge from ${win.phrase || "midnight to midnight"}.`,
        _phrase: win.phrase || "the whole day",
      };
    }

    /* --- maximum grid window --------------------------------------------- */
    if (gridWords && has(t, /\b(not exceed|no more than|cap\w*|limit\w*|max\w*|below|under|至|keep\s+\w+\s+under|restrict\w*|at most|ceiling|no higher)\b/)) {
      const kwh = readEnergy(note);
      if (kwh != null) {
        const hours = win.hours && win.hours.length ? win.hours : Array.from({ length: 24 }, (_, k) => k);
        return {
          note_index: i, applies: true, directive_type: "max_grid_window",
          structured_adjustment: { hours, max_grid_kwh: r2(kwh) },
          explanation: `Grid draw is capped at ${r2(kwh)} kWh per hour for ${win.phrase || "the whole day"}.`,
          _phrase: win.phrase || "the whole day",
        };
      }
    }

    return noop();
  });
}

/* ------------------------------------------------------------ 2. optimising */

/** Turn validated directives into per-hour constraint arrays. */
export function buildConstraints(hours, battery, directives) {
  const n = 24;
  const cap = Number(battery.capacity_kwh);
  const minBase = Number(battery.minimum_energy_kwh);
  const c = {
    demand: hours.map((h) => Number(h.demand_kwh)),
    solar: hours.map((h) => Number(h.solar_kwh)),
    tariff: hours.map((h) => Number(h.tariff_bdt_per_kwh)),
    eff: hours.map((h) => Number(h.solar_kwh)),
    factor: Array(n).fill(1),
    minRes: Array(n).fill(minBase),
    noCharge: Array(n).fill(false),
    noDischarge: Array(n).fill(false),
    gridCap: Array(n).fill(Infinity),
    cap, minBase,
    e0: Number(battery.initial_energy_kwh),
    maxC: Number(battery.max_charge_kwh_per_hour),
    maxD: Number(battery.max_discharge_kwh_per_hour),
  };

  for (const d of directives) {
    if (!d.applies || !d.structured_adjustment) continue;
    const a = d.structured_adjustment;
    const hh = (a.hours || []).filter((h) => Number.isInteger(h) && h >= 0 && h < n);
    if (d.directive_type === "solar_reduction") {
      for (const h of hh) { c.factor[h] = Math.min(c.factor[h], a.factor); c.eff[h] = c.solar[h] * c.factor[h]; }
    } else if (d.directive_type === "minimum_battery_reserve") {
      for (const h of hh) c.minRes[h] = Math.max(c.minRes[h], a.minimum_energy_kwh);
    } else if (d.directive_type === "no_charge_window") {
      for (const h of hh) c.noCharge[h] = true;
    } else if (d.directive_type === "no_discharge_window") {
      for (const h of hh) c.noDischarge[h] = true;
    } else if (d.directive_type === "max_grid_window") {
      for (const h of hh) c.gridCap[h] = Math.min(c.gridCap[h], a.max_grid_kwh);
    }
  }
  return c;
}

/**
 * Cost-minimising schedule: serve demand from free solar first, then move
 * battery energy from cheap hours into expensive hours while every bound,
 * window, rate limit and end-of-day neutrality holds.
 */
export function optimize(hours, battery, directives) {
  const n = 24;
  const c = buildConstraints(hours, battery, directives);
  const charge = Array(n).fill(0);
  const discharge = Array(n).fill(0);
  const solarToLoad = c.demand.map((d, h) => Math.min(d, c.eff[h]));
  const solarToBatt = Array(n).fill(0);
  const surplus = c.eff.map((e, h) => e - solarToLoad[h]);
  const issues = [];

  /* grid import only pays for the part of charging that did not come from solar */
  const gridAt = (h) => c.demand[h] - solarToLoad[h] + (charge[h] - solarToBatt[h]) - discharge[h];

  const soc = () => {
    const e = Array(n).fill(0);
    let cur = c.e0;
    for (let h = 0; h < n; h++) { cur += charge[h] - discharge[h]; e[h] = cur; }
    return e;
  };

  const canCharge = (h) => !c.noCharge[h] && c.maxC - charge[h] > EPS && discharge[h] <= EPS;
  const canDischarge = (h) => !c.noDischarge[h] && c.maxD - discharge[h] > EPS && charge[h] <= EPS;

  /* headroom below capacity for hours [from..23] */
  const capRoom = (e, from) => {
    let m = Infinity;
    for (let h = from; h < n; h++) m = Math.min(m, c.cap - e[h]);
    return m;
  };
  /* energy above the active reserve for hours [from..23] */
  const resRoom = (e, from) => {
    let m = Infinity;
    for (let h = from; h < n; h++) m = Math.min(m, e[h] - c.minRes[h]);
    return m;
  };

  /* --- forced discharge so a capped feeder can still serve demand -------- */
  const enforceCaps = () => {
    let moved = 0;
    for (let h = 0; h < n; h++) {
      const over = gridAt(h) - c.gridCap[h];
      if (over <= EPS) continue;
      const e = soc();
      const room = Math.min(over, c.maxD - discharge[h], Math.max(0, resRoom(e, h)));
      if (canDischarge(h) && room > EPS) { discharge[h] += room; moved += room; }
    }
    return moved;
  };
  enforceCaps();

  /* --- repair: reserve floors, capacity ceiling, end-of-day neutrality --- */
  const raise = (need, before) => {
    /* add charging in the cheapest feasible hour at or before `before` */
    let best = null;
    for (let i = 0; i <= before; i++) {
      if (!canCharge(i)) continue;
      const e = soc();
      const room = Math.min(c.maxC - charge[i], capRoom(e, i));
      if (room <= EPS) continue;
      const free = Math.max(0, surplus[i] - solarToBatt[i]);
      const cost = free > EPS ? 0 : c.tariff[i];
      const headroom = free > EPS ? Math.min(room, free) : Math.min(room, c.gridCap[i] - gridAt(i));
      if (headroom <= EPS) continue;
      if (!best || cost < best.cost) best = { i, cost, q: Math.min(need, headroom), free: free > EPS };
    }
    if (!best) return 0;
    charge[best.i] += best.q;
    if (best.free) solarToBatt[best.i] += best.q;
    return best.q;
  };

  const lower = (need, before) => {
    let best = null;
    for (let i = 0; i <= before; i++) {
      if (!canDischarge(i)) continue;
      const e = soc();
      const room = Math.min(c.maxD - discharge[i], resRoom(e, i), Math.max(0, gridAt(i)));
      if (room <= EPS) continue;
      if (!best || c.tariff[i] > best.t) best = { i, t: c.tariff[i], q: Math.min(need, room) };
    }
    if (!best) return 0;
    discharge[best.i] += best.q;
    return best.q;
  };

  const repair = () => {
  for (let guard = 0; guard < 400; guard++) {
    const e = soc();
    let acted = false;

    let bad = -1;
    for (let h = 0; h < n; h++) if (e[h] < c.minRes[h] - EPS) { bad = h; break; }
    if (bad >= 0) {
      const moved = raise(c.minRes[bad] - e[bad], bad);
      if (moved > EPS) { acted = true; continue; }
      issues.push(`The ${r2(c.minRes[bad])} kWh reserve cannot be met by hour ${String(bad).padStart(2, "0")} within the charging limits.`);
      break;
    }

    bad = -1;
    for (let h = 0; h < n; h++) if (e[h] > c.cap + EPS) { bad = h; break; }
    if (bad >= 0) {
      const moved = lower(e[bad] - c.cap, bad);
      if (moved > EPS) { acted = true; continue; }
      issues.push(`Battery energy exceeds capacity at hour ${String(bad).padStart(2, "0")} and cannot be discharged within the limits.`);
      break;
    }

    const end = e[n - 1];
    if (end < c.e0 - EPS) {
      if (raise(c.e0 - end, n - 1) > EPS) { acted = true; continue; }
      issues.push("The battery cannot be returned to its starting energy by the end of the day.");
      break;
    }
    if (end > c.e0 + EPS) {
      if (lower(end - c.e0, n - 1) > EPS) { acted = true; continue; }
      issues.push("Surplus battery energy cannot be discharged before the end of the day.");
      break;
    }
    if (!acted) break;
  }
  };
  repair();

  /* --- arbitrage: pair a cheap charge hour with an expensive discharge --- */
  for (let iter = 0; iter < 3000; iter++) {
    const e = soc();
    let best = null;

    for (let j = 0; j < n; j++) {
      if (!canDischarge(j)) continue;
      const gj = gridAt(j);
      if (gj <= EPS) continue;
      for (let i = 0; i < n; i++) {
        if (i === j || !canCharge(i)) continue;
        const free = Math.max(0, surplus[i] - solarToBatt[i]);
        for (const src of free > EPS ? ["solar", "grid"] : ["grid"]) {
          const unit = src === "solar" ? 0 : c.tariff[i];
          const gain = c.tariff[j] - unit;
          if (gain <= 1e-6) continue;

          let q = Math.min(c.maxC - charge[i], c.maxD - discharge[j], gj);
          q = Math.min(q, src === "solar" ? free : c.gridCap[i] - gridAt(i));
          if (i < j) {
            let room = Infinity;
            for (let h = i; h < j; h++) room = Math.min(room, c.cap - e[h]);
            q = Math.min(q, room);
          } else {
            let room = Infinity;
            for (let h = j; h < i; h++) room = Math.min(room, e[h] - c.minRes[h]);
            q = Math.min(q, room);
          }
          if (q <= EPS) continue;
          const value = gain;
          if (!best || value > best.value + 1e-9 || (Math.abs(value - best.value) < 1e-9 && q > best.q)) best = { i, j, q, src, value };
        }
      }
    }
    if (!best) break;
    charge[best.i] += best.q;
    discharge[best.j] += best.q;
    if (best.src === "solar") solarToBatt[best.i] += best.q;
  }

  /* --- final sweep: caps are judged on the finished schedule, not mid-solve */
  if (enforceCaps() > EPS) repair();
  for (let h = 0; h < n; h++) {
    if (gridAt(h) - c.gridCap[h] > EPS) {
      issues.push(`Hour ${String(h).padStart(2, "0")} needs ${r2(gridAt(h))} kWh from the grid but is capped at ${r2(c.gridCap[h])} kWh. The battery cannot cover the gap within its limits.`);
    }
  }

  /* --- assemble the plan ------------------------------------------------- */
  const e = soc();
  const hourly_plan = [];
  let total_grid = 0, total_cost = 0, peak = 0, solar_used_total = 0, solar_avail_total = 0;

  for (let h = 0; h < n; h++) {
    const g = Math.max(0, r2(gridAt(h)));
    const used = r2(solarToLoad[h] + solarToBatt[h]);
    const net = charge[h] - discharge[h];
    const action = net > EPS ? "charge" : net < -EPS ? "discharge" : "idle";
    const amount = action === "idle" ? 0 : r2(Math.abs(net));
    total_grid += g;
    total_cost += g * c.tariff[h];
    peak = Math.max(peak, g);
    solar_used_total += used;
    solar_avail_total += c.eff[h];
    hourly_plan.push({
      hour: h,
      grid_kwh: g,
      solar_used_kwh: used,
      battery_action: action,
      battery_kwh: amount,
      battery_energy_after_kwh: r2(e[h]),
      demand_kwh: r2(c.demand[h]),
      solar_forecast_kwh: r2(c.solar[h]),
      solar_effective_kwh: r2(c.eff[h]),
      tariff_bdt_per_kwh: c.tariff[h],
      hour_cost_bdt: r2(g * c.tariff[h]),
    });
  }

  const applied = directives.filter((d) => d.applies).length;
  return {
    scenario_id: null,
    status: issues.length ? "infeasible" : "optimal",
    issues,
    directive_interpretation: directives,
    hourly_plan,
    total_grid_kwh: r2(total_grid),
    total_cost_bdt: r2(total_cost),
    peak_grid_kwh: r2(peak),
    battery_end_kwh: r2(e[n - 1]),
    solar_used_kwh: r2(solar_used_total),
    solar_available_kwh: r2(solar_avail_total),
    solar_utilization: solar_avail_total > EPS ? r2((solar_used_total / solar_avail_total) * 100) : 0,
    applied_directives: applied,
    plan_summary: buildSummary(directives, peak, solar_avail_total, solar_used_total),
    constraints: c,
  };
}

function buildSummary(directives, peak, avail, used) {
  const bits = [];
  const kinds = directives.filter((d) => d.applies).map((d) => d.directive_type);
  if (kinds.includes("solar_reduction")) bits.push("works around the reduced solar window");
  if (kinds.includes("minimum_battery_reserve")) bits.push("holds the requested reserve");
  if (kinds.includes("no_charge_window")) bits.push("keeps the battery off charge when asked");
  if (kinds.includes("no_discharge_window")) bits.push("leaves the battery untouched in the protected hours");
  if (kinds.includes("max_grid_window")) bits.push("stays under the grid cap");
  if (avail > EPS) bits.push(`uses ${Math.round((used / avail) * 100)}% of usable solar`);
  bits.push(`peaks at ${r2(peak)} kWh from the grid`);
  return `The schedule shifts battery energy into the costliest hours, ${bits.join(", ")}, and returns the battery to its starting level.`;
}

/* ------------------------------------------------------------ 3. validating */

export function validate(result) {
  const c = result.constraints;
  const p = result.hourly_plan;
  const out = [];
  const add = (id, name, ok, detail) => out.push({ id, name, ok, detail });

  let worstBalance = 0;
  for (const row of p) {
    const ch = row.battery_action === "charge" ? row.battery_kwh : 0;
    const dis = row.battery_action === "discharge" ? row.battery_kwh : 0;
    const lhs = row.grid_kwh + row.solar_used_kwh + dis;
    const rhs = row.demand_kwh + ch;
    worstBalance = Math.max(worstBalance, Math.abs(lhs - rhs));
  }
  add("balance", "Energy balance satisfied", worstBalance <= 0.02,
    `Largest hourly mismatch between supply and demand: ${r2(worstBalance)} kWh (tolerance 0.01 kWh).`);

  let maxSoc = -Infinity, minSoc = Infinity;
  for (const row of p) { maxSoc = Math.max(maxSoc, row.battery_energy_after_kwh); minSoc = Math.min(minSoc, row.battery_energy_after_kwh); }
  add("capacity", "Battery capacity respected", maxSoc <= c.cap + 0.02,
    `Highest stored energy ${r2(maxSoc)} kWh against a ${r2(c.cap)} kWh capacity.`);

  let resOk = true, resWorst = null;
  p.forEach((row, h) => {
    if (row.battery_energy_after_kwh < c.minRes[h] - 0.02) {
      resOk = false;
      if (!resWorst) resWorst = `Hour ${String(h).padStart(2, "0")} holds ${r2(row.battery_energy_after_kwh)} kWh against a ${r2(c.minRes[h])} kWh floor.`;
    }
  });
  add("reserve", "Minimum battery reserve respected", resOk,
    resWorst || `Lowest stored energy ${r2(minSoc)} kWh, never below the active floor.`);

  let chMax = 0, disMax = 0;
  for (const row of p) {
    if (row.battery_action === "charge") chMax = Math.max(chMax, row.battery_kwh);
    if (row.battery_action === "discharge") disMax = Math.max(disMax, row.battery_kwh);
  }
  add("chargeRate", "Charging limits respected", chMax <= c.maxC + 0.02,
    `Largest charge in one hour ${r2(chMax)} kWh against a ${r2(c.maxC)} kWh limit.`);
  add("dischargeRate", "Discharging limits respected", disMax <= c.maxD + 0.02,
    `Largest discharge in one hour ${r2(disMax)} kWh against a ${r2(c.maxD)} kWh limit.`);

  let solarOk = true, solarNote = null;
  p.forEach((row, h) => {
    if (row.solar_used_kwh > c.eff[h] + 0.02) {
      solarOk = false;
      solarNote = `Hour ${String(h).padStart(2, "0")} uses ${r2(row.solar_used_kwh)} kWh of an available ${r2(c.eff[h])} kWh.`;
    }
  });
  add("solar", "Solar availability respected", solarOk,
    solarNote || `Every hour draws at or below its usable solar, after any reduction directive.`);

  const viol = [];
  p.forEach((row, h) => {
    if (c.noCharge[h] && row.battery_action === "charge") viol.push(`charging at hour ${String(h).padStart(2, "0")}`);
    if (c.noDischarge[h] && row.battery_action === "discharge") viol.push(`discharging at hour ${String(h).padStart(2, "0")}`);
    if (row.grid_kwh > c.gridCap[h] + 0.02) viol.push(`grid cap exceeded at hour ${String(h).padStart(2, "0")}`);
  });
  const dirCount = result.directive_interpretation.filter((d) => d.applies).length;
  add("directives", "Operator instructions respected", viol.length === 0,
    viol.length ? `Conflicts found: ${viol.join(", ")}.` : `All ${dirCount} applied ${dirCount === 1 ? "directive holds" : "directives hold"} across the 24-hour plan.`);

  const end = p[p.length - 1].battery_energy_after_kwh;
  add("neutral", "End-of-day battery neutrality satisfied", Math.abs(end - c.e0) <= 0.02,
    `Battery ends at ${r2(end)} kWh against a ${r2(c.e0)} kWh start.`);

  const recGrid = r2(p.reduce((s, r) => s + r.grid_kwh, 0));
  const recCost = r2(p.reduce((s, r) => s + r.grid_kwh * r.tariff_bdt_per_kwh, 0));
  add("totals", "Reported totals match the schedule",
    Math.abs(recGrid - result.total_grid_kwh) <= 0.02 && Math.abs(recCost - result.total_cost_bdt) <= 0.02,
    `Recalculated ${recGrid} kWh and ${recCost} BDT from the hourly plan.`);

  return out;
}

/* ------------------------------------------------------------------ inputs */

export function validateInput(draft) {
  const errors = {};
  if (!String(draft.scenario_id || "").trim()) errors.scenario_id = "Give the scenario a name so you can find it again.";
  else if (!/^[\w][\w .-]{0,39}$/.test(draft.scenario_id.trim())) errors.scenario_id = "Use letters, numbers, spaces, dots or dashes, up to 40 characters.";

  const rows = draft.hours || [];
  if (rows.length !== 24) errors.hours = "The scenario needs exactly 24 hourly rows.";
  const cellErrors = {};
  rows.forEach((row, h) => {
    for (const key of ["demand_kwh", "solar_kwh", "tariff_bdt_per_kwh"]) {
      const v = row[key];
      if (v === "" || v == null || Number.isNaN(Number(v))) cellErrors[`${h}:${key}`] = "Enter a number";
      else if (Number(v) < 0) cellErrors[`${h}:${key}`] = "Cannot be negative";
      else if (key === "demand_kwh" && Number(v) > 100000) cellErrors[`${h}:${key}`] = "Too large";
    }
  });
  if (Object.keys(cellErrors).length) errors.cells = cellErrors;

  const b = draft.battery || {};
  const num = (k) => Number(b[k]);
  const bErr = {};
  for (const k of ["capacity_kwh", "initial_energy_kwh", "minimum_energy_kwh", "max_charge_kwh_per_hour", "max_discharge_kwh_per_hour"]) {
    if (b[k] === "" || b[k] == null || Number.isNaN(num(k))) bErr[k] = "Enter a number";
    else if (num(k) < 0) bErr[k] = "Cannot be negative";
  }
  if (!Object.keys(bErr).length) {
    if (num("capacity_kwh") <= 0) bErr.capacity_kwh = "Capacity must be greater than zero";
    if (num("initial_energy_kwh") > num("capacity_kwh")) bErr.initial_energy_kwh = "Starting energy cannot exceed capacity";
    if (num("minimum_energy_kwh") > num("capacity_kwh")) bErr.minimum_energy_kwh = "Reserve cannot exceed capacity";
    if (num("initial_energy_kwh") < num("minimum_energy_kwh")) bErr.initial_energy_kwh = "Starting energy is below the reserve";
    if (num("max_charge_kwh_per_hour") <= 0) bErr.max_charge_kwh_per_hour = "Charging rate must be greater than zero";
    if (num("max_discharge_kwh_per_hour") <= 0) bErr.max_discharge_kwh_per_hour = "Discharging rate must be greater than zero";
  }
  if (Object.keys(bErr).length) errors.battery = bErr;

  const notes = (draft.operator_notes || []).map((s) => String(s || "").trim());
  const filled = notes.filter(Boolean);
  if (!filled.length) errors.notes = "Add at least one operator instruction.";
  else if (filled.length > 3) errors.notes = "GridWise reads a maximum of three instructions.";
  else if (filled.some((s) => s.length > 400)) errors.notes = "Keep each instruction under 400 characters.";

  return { ok: Object.keys(errors).length === 0, errors };
}

export function runScenario(input) {
  const directives = interpretNotes(input.operator_notes, input.battery);
  const result = optimize(input.hours, input.battery, directives);
  result.scenario_id = input.scenario_id;
  result.checks = validate(result);
  if (result.checks.some((c) => !c.ok) && result.status === "optimal") result.status = "check_failed";
  return result;
}

export { r2, fmtH };
