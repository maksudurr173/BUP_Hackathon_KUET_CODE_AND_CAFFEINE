"""Physics and constraint replay engine.

Replays the energy dispatch schedule hour by hour to verify conservation of energy,
battery dynamics, solar constraints, grid limits, and operational bounds independently
of the optimization solver.
"""

import math
from typing import List, Tuple
from gridwise.app.models import BatteryConfig, HourlyPlanEntry
from gridwise.directives.engine import ProcessedDirectives
from gridwise.app.errors import ValidationFailedException


class ScheduleReplayEngine:
    """Independent deterministic replay engine for 24-hour schedules."""

    @classmethod
    def replay(
        cls,
        demand: List[float],
        tariff: List[float],
        battery: BatteryConfig,
        processed_directives: ProcessedDirectives,
        hourly_plan: List[HourlyPlanEntry],
        tolerance: float = 0.01
    ) -> Tuple[bool, List[str]]:
        """Replays and verifies the entire 24-hour schedule.
        
        Returns:
            (is_valid, list_of_violations)
        """
        violations: List[str] = []

        # 1. Structural check: exactly 24 hours, hours 0 to 23
        if len(hourly_plan) != 24:
            violations.append(f"Hourly plan contains {len(hourly_plan)} entries, expected exactly 24")
            return False, violations

        current_battery_energy = battery.initial_energy_kwh

        for idx, entry in enumerate(hourly_plan):
            h = entry.hour
            if h != idx:
                violations.append(f"Hour order mismatch at index {idx}: entry.hour is {h}")

            # Check finiteness and non-negativity
            for field_name, val in [
                ("grid_kwh", entry.grid_kwh),
                ("solar_used_kwh", entry.solar_used_kwh),
                ("battery_kwh", entry.battery_kwh),
                ("battery_energy_after_kwh", entry.battery_energy_after_kwh),
            ]:
                if not math.isfinite(val):
                    violations.append(f"Hour {h}: {field_name} is not finite ({val})")
                if val < -tolerance:
                    violations.append(f"Hour {h}: {field_name} is negative ({val})")

            # Determine charge / discharge amounts
            charge_kwh = 0.0
            discharge_kwh = 0.0
            if entry.battery_action == "charging":
                charge_kwh = entry.battery_kwh
            elif entry.battery_action == "discharging":
                discharge_kwh = entry.battery_kwh
            elif entry.battery_action == "idle":
                if entry.battery_kwh > tolerance:
                    violations.append(
                        f"Hour {h}: battery_action is idle but battery_kwh is {entry.battery_kwh}"
                    )
            else:
                violations.append(f"Hour {h}: Unknown battery_action '{entry.battery_action}'")

            # Check Charge/Discharge rate bounds
            if charge_kwh > battery.max_charge_kwh + tolerance:
                violations.append(
                    f"Hour {h}: Charge rate {charge_kwh:.3f} exceeds max charge {battery.max_charge_kwh}"
                )
            if discharge_kwh > battery.max_discharge_kwh + tolerance:
                violations.append(
                    f"Hour {h}: Discharge rate {discharge_kwh:.3f} exceeds max discharge {battery.max_discharge_kwh}"
                )

            # Check Directive: no-charge / no-discharge windows
            if h in processed_directives.no_charge_hours and charge_kwh > tolerance:
                violations.append(f"Hour {h}: Charge violation during no_charge_window ({charge_kwh:.3f} kWh)")
            if h in processed_directives.no_discharge_hours and discharge_kwh > tolerance:
                violations.append(f"Hour {h}: Discharge violation during no_discharge_window ({discharge_kwh:.3f} kWh)")

            # Check Solar constraint: solar_used <= effective_solar
            eff_solar = processed_directives.effective_solar[h]
            if entry.solar_used_kwh > eff_solar + tolerance:
                violations.append(
                    f"Hour {h}: Solar used {entry.solar_used_kwh:.3f} exceeds effective solar {eff_solar:.3f}"
                )

            # Check Grid constraint: grid <= max_grid if limited
            if h in processed_directives.max_grid_limits:
                max_g = processed_directives.max_grid_limits[h]
                if entry.grid_kwh > max_g + tolerance:
                    violations.append(
                        f"Hour {h}: Grid import {entry.grid_kwh:.3f} exceeds limit {max_g:.3f}"
                    )

            # Check Energy Balance: Grid + Solar + Discharge = Demand + Charge
            supply = entry.grid_kwh + entry.solar_used_kwh + discharge_kwh
            demand_target = demand[h] + charge_kwh
            imbalance = abs(supply - demand_target)
            if imbalance > tolerance:
                violations.append(
                    f"Hour {h}: Energy balance violation. Supply={supply:.3f}, Demand+Charge={demand_target:.3f}, Imbalance={imbalance:.3f}"
                )

            # Check Battery state transition: E[h] = E[h-1] + Charge - Discharge
            expected_energy_after = current_battery_energy + charge_kwh - discharge_kwh
            if abs(entry.battery_energy_after_kwh - expected_energy_after) > tolerance:
                violations.append(
                    f"Hour {h}: Battery dynamics mismatch. Expected={expected_energy_after:.3f}, Reported={entry.battery_energy_after_kwh:.3f}"
                )

            # Check Battery capacity and reserve bounds
            min_reserve = processed_directives.min_battery_energy[h]
            if entry.battery_energy_after_kwh < min_reserve - tolerance:
                violations.append(
                    f"Hour {h}: Battery energy {entry.battery_energy_after_kwh:.3f} violates minimum reserve {min_reserve:.3f}"
                )
            if entry.battery_energy_after_kwh > battery.capacity_kwh + tolerance:
                violations.append(
                    f"Hour {h}: Battery energy {entry.battery_energy_after_kwh:.3f} exceeds capacity {battery.capacity_kwh:.3f}"
                )

            # Advance state
            current_battery_energy = entry.battery_energy_after_kwh

        # 2. End-of-Day Neutrality Check: E[23] == E_initial
        if abs(current_battery_energy - battery.initial_energy_kwh) > tolerance:
            violations.append(
                f"End-of-day neutrality violation: Ending energy={current_battery_energy:.3f} != Initial energy={battery.initial_energy_kwh:.3f}"
            )

        return len(violations) == 0, violations
