"""Directives processing engine.

Applies validated structured directives to baseline scenario parameters,
generating effective solar availability, battery reserves, charge/discharge
block windows, and grid import caps for every hour of the 24-hour horizon.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from gridwise.app.models import DirectiveInterpretation, BatteryConfig


@dataclass
class ProcessedDirectives:
    """Consolidated constraint parameters after applying all directives."""
    effective_solar: List[float]
    min_battery_energy: List[float]
    no_charge_hours: Set[int] = field(default_factory=set)
    no_discharge_hours: Set[int] = field(default_factory=set)
    max_grid_limits: Dict[int, float] = field(default_factory=dict)
    applied_directives_summary: List[str] = field(default_factory=list)


class DirectiveEngine:
    """Engine responsible for compiling directives into optimization parameters."""

    @classmethod
    def apply_directives(
        cls,
        base_solar: List[float],
        battery_config: BatteryConfig,
        directives: List[DirectiveInterpretation]
    ) -> ProcessedDirectives:
        """Applies all directives simultaneously without overwriting or ignoring any."""
        effective_solar = list(base_solar)
        min_battery_energy = [battery_config.min_energy_kwh] * 24
        no_charge_hours: Set[int] = set()
        no_discharge_hours: Set[int] = set()
        max_grid_limits: Dict[int, float] = {}
        applied_summary: List[str] = []

        for directive in directives:
            if not directive.applies or directive.directive_type == "no_op":
                continue

            adj = directive.structured_adjustment or {}

            if directive.directive_type == "solar_reduction":
                hours = adj.get("hours", [])
                factor = float(adj.get("factor", 1.0))
                for h in hours:
                    if 0 <= h < 24:
                        effective_solar[h] = effective_solar[h] * factor
                applied_summary.append(
                    f"Solar reduction factor {factor:.2f} applied to hours {hours}"
                )

            elif directive.directive_type == "minimum_battery_reserve":
                hours = adj.get("hours", [])
                min_reserve = float(adj.get("minimum_energy_kwh", 0.0))
                for h in hours:
                    if 0 <= h < 24:
                        # Enforce higher reserve if multiple constraints apply
                        min_battery_energy[h] = max(min_battery_energy[h], min_reserve)
                applied_summary.append(
                    f"Minimum battery reserve {min_reserve:.1f} kWh applied to hours {hours}"
                )

            elif directive.directive_type == "no_charge_window":
                hours = adj.get("hours", [])
                for h in hours:
                    if 0 <= h < 24:
                        no_charge_hours.add(h)
                applied_summary.append(f"No-charge restriction applied to hours {hours}")

            elif directive.directive_type == "no_discharge_window":
                hours = adj.get("hours", [])
                for h in hours:
                    if 0 <= h < 24:
                        no_discharge_hours.add(h)
                applied_summary.append(f"No-discharge restriction applied to hours {hours}")

            elif directive.directive_type == "max_grid_window":
                hours = adj.get("hours", [])
                max_grid = float(adj.get("max_grid_kwh", 0.0))
                for h in hours:
                    if 0 <= h < 24:
                        if h in max_grid_limits:
                            max_grid_limits[h] = min(max_grid_limits[h], max_grid)
                        else:
                            max_grid_limits[h] = max_grid
                applied_summary.append(
                    f"Max grid import limit {max_grid:.1f} kWh applied to hours {hours}"
                )

        return ProcessedDirectives(
            effective_solar=effective_solar,
            min_battery_energy=min_battery_energy,
            no_charge_hours=no_charge_hours,
            no_discharge_hours=no_discharge_hours,
            max_grid_limits=max_grid_limits,
            applied_directives_summary=applied_summary
        )
