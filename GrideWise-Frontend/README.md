# GridWise

A campus energy optimization console. Enter a 24-hour demand, solar and tariff
profile, configure the battery, add up to three plain-English operator notes, and
GridWise produces the cheapest battery schedule that still satisfies every
constraint — then shows its work.

Built for the BUP CSE Fest 2026 preliminary (GridWise LLM problem statement).

---

## Running it

**Standalone (easiest).** Open `gridwise-standalone.html` by double-clicking it.
Everything is inlined — no server, no build step, no dependencies.

**Multi-file version.** `index.html` uses ES modules, so it must be served over
HTTP. Opening it directly from disk will be blocked by the browser's CORS policy.

```bash
cd gridwise
python3 -m http.server 8000
# then open http://localhost:8000
```

To rebuild the standalone file after editing the sources:

```bash
python3 build.py
```

---

## Files

```
index.html                  application shell
assets/css/styles.css       design tokens, layout, components, responsive rules
assets/js/app.js            state, routing, all four views, interactions
assets/js/charts.js         dependency-free SVG chart renderer
assets/js/engine.js         interpreter + optimizer + validator
assets/js/samples.js        the 10 public sample scenario inputs
gridwise-standalone.html    single-file build of everything above
build.py                    regenerates the standalone build
```

No frameworks, no npm install, no bundler. The only network request is the
Google Fonts stylesheet, and the design degrades cleanly to system fonts if it
fails.

---

## The engine

Everything on screen is computed. Nothing is hard-coded against the public cases.

### 1. Interpreting notes

`interpretNotes()` turns each operator note into one machine-checkable directive,
returning exactly one entry per note in `note_index` order. Supported types:

| Type | Example phrasing |
| --- | --- |
| `solar_reduction` | "treat usable solar as 25% of the forecast from noon to 2 PM" |
| `minimum_battery_reserve` | "keep at least 50% of capacity from 6 PM until 9 PM" |
| `no_charge_window` | "the charging circuit will be unavailable from 2 PM until 4 PM" |
| `no_discharge_window` | "do not discharge the battery between 6 PM and 8 PM" |
| `max_grid_window` | "grid draw must not exceed 155 kWh between 7 PM and 9 PM" |
| `no_op` | anything that does not affect today's schedule |

Semantics it handles correctly:

- **Windows are start-inclusive, end-exclusive.** 1 PM to 3 PM maps to `[13, 14]`.
- **Factor is the fraction that remains.** An 80% reduction gives `factor: 0.2`,
  while "treated as 25% of the forecast" gives `factor: 0.25`. Reduction wording
  takes priority over remaining-fraction wording when a note contains both.
- Clock forms: `6 PM`, `18:00`, `noon`, `midnight`, `from 9`, bare hours.
- Percentage reserves are resolved against battery capacity.
- Distractor notes ("the library is extending book-return hours") become `no_op`
  with `applies: false` and a null adjustment.

### 2. Optimizing

`optimize()` serves demand from free solar first, then runs greedy tariff
arbitrage: it repeatedly pairs the cheapest feasible charging hour with the most
expensive feasible discharging hour, selecting by unit gain, until no profitable
pair remains. Before that, a repair pass forces feasibility for grid caps,
reserve floors and the capacity ceiling, and restores end-of-day neutrality.

Respected throughout: hourly charge/discharge rate limits, capacity and active
reserve bounds, no-charge and no-discharge windows, per-hour grid ceilings,
effective solar after any reduction, and `battery_energy_after_kwh` at hour 23
returning to `initial_energy_kwh`.

### 3. Validating

`validate()` replays the finished schedule against nine checks and reports each
one honestly, including failures — the UI never hides a failed check:

energy balance · capacity · minimum reserve · charge rate · discharge rate ·
solar availability · operator instructions · end-of-day neutrality ·
reported totals match the hourly plan

### Verification

Tested against the 10 public sample cases in the participant pack:

- **10/10** scenarios match the reference optimal `total_cost_bdt` exactly
- **18/18** directive interpretations match the expected ground truth
- **All checks pass** on every case

Only the sample *inputs* are bundled in `samples.js`. No reference schedules,
note wording or expected values are baked into the solver.

---

## Connecting a real backend

The app runs the solver on-device by default (the sidebar shows "On-device
solver"). To call a server instead, replace the `runScenario(input)` call inside
`optimizeNow()` in `app.js` with a fetch to your endpoint:

```js
const res = await fetch("/optimize-energy", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(input),
});
const result = await res.json();
```

The request body already matches the required input schema:

```json
{
  "scenario_id": "SAMPLE-01",
  "operator_notes": ["..."],
  "hours": [{ "hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6 }],
  "battery": {
    "capacity_kwh": 220,
    "initial_energy_kwh": 110,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
```

The response is expected in the official output shape (`scenario_id`,
`directive_interpretation`, `hourly_plan`, `total_grid_kwh`, `total_cost_bdt`,
`peak_grid_kwh`, `plan_summary`). The results view reads a few extra derived
fields — `constraints`, `checks`, `solar_utilization` — so keep the local
`validate()` and `buildConstraints()` call on the response to populate them.

**Export JSON** on the results screen emits exactly the official output shape,
which is useful for diffing against a backend under development.

---

## Design

Four brief-locked colors: Deep Graphite `#172126`, Electric Teal `#149E9A`,
Solar Amber `#E5A93D`, Soft Mint `#DCEFE8`. A muted clay `#A8443B` is reserved
strictly for validation failures, so status never rides on the palette colors.

Space Grotesk carries headings and all numerals — tabular figures mean schedule
columns align without resorting to a monospace face. Instrument Sans handles UI
and body text.

Boldness is spent in one place: the energy-flow diagram, where stroke weight and
flow direction track the scrubbed hour. Everything around it stays quiet —
hairline borders, one shadow tier, no gradients.

### Quality floor

- No horizontal overflow at 390px, 834px or 1440px
- Light and dark themes, following the system setting
- Visible keyboard focus; charts are focusable and arrow-key navigable
- `prefers-reduced-motion` respected (flow animation off, transitions collapsed)
- Status communicated by icon and text, never color alone
- Semantic HTML with labelled inputs and `aria-live` toasts
- Saved scenarios use `localStorage` in a try/catch, and the app renders
  correctly when storage is empty or unavailable

### Handled states

Loading (staged optimizer overlay), empty data, invalid input, invalid battery
configuration, unsupported instruction (`no_op`), impossible optimization
(infeasible, with the reason in plain language), solver error, and success.
Raw errors and stack traces are never shown.

---

## Notes

- Instructions are capped at three, matching the problem statement.
- Paste a column of 24 numbers into any hour cell to fill that column.
- Scenario history is per-device and holds the 40 most recent runs.
