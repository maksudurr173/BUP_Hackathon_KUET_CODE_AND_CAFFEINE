"""Independent Schedule Validator and Metrics Calculator.

Never blindly trusts optimizer outputs. Re-verifies every constraint and
calculates all top-level summary metrics directly from the verified hourly plan.
"""

import logging
from typing import Dict, List, Tuple
from config import settings
from gridwise.app.models import BatteryConfig, HourlyPlanEntry, DirectiveInterpretation
from gridwise.directives.engine import ProcessedDirectives
from gridwise.validation.replay import ScheduleReplayEngine
from gridwise.app.errors import ValidationFailedException

logger = logging.getLogger("gridwise.validation")


class ScheduleValidator:
    """Independent validator and metrics calculator for the candidate energy schedule."""

    @classmethod
    def validate_and_compute_metrics(
        cls,
        demand: List[float],
        tariff: List[float],
        battery: BatteryConfig,
        processed_directives: ProcessedDirectives,
        hourly_plan: List[HourlyPlanEntry],
        tolerance: float = 0.01
    ) -> Tuple[float, float, float]:
        """Validates the schedule and returns (total_grid_kwh, total_cost_bdt, peak_grid_kwh).
        
        Raises ValidationFailedException if any constraint is violated.
        """
        is_valid, violations = ScheduleReplayEngine.replay(
            demand=demand,
            tariff=tariff,
            battery=battery,
            processed_directives=processed_directives,
            hourly_plan=hourly_plan,
            tolerance=tolerance
        )

        if not is_valid:
            error_details = "; ".join(violations[:5])
            if len(violations) > 5:
                error_details += f" (and {len(violations) - 5} more violations)"
            logger.error(f"Schedule validation failed: {error_details}")
            raise ValidationFailedException(
                f"Candidate schedule failed independent physical validation: {error_details}"
            )

        # Compute totals strictly from the verified hourly plan
        total_grid_kwh = sum(entry.grid_kwh for entry in hourly_plan)
        total_cost_bdt = sum(entry.grid_kwh * tariff[entry.hour] for entry in hourly_plan)
        peak_grid_kwh = max(entry.grid_kwh for entry in hourly_plan)

        return (
            round(total_grid_kwh, 4),
            round(total_cost_bdt, 4),
            round(peak_grid_kwh, 4)
        )

    @classmethod
    def generate_plan_summary(
        cls,
        scenario_id: str,
        directives: List[DirectiveInterpretation],
        hourly_plan: List[HourlyPlanEntry],
        total_grid_kwh: float,
        total_cost_bdt: float,
        peak_grid_kwh: float,
        applied_directives_summary: List[str]
    ) -> str:
        """Generates a concise, fact-checked human-readable summary of the validated plan."""
        total_solar_used = sum(entry.solar_used_kwh for entry in hourly_plan)
        total_charged = sum(entry.battery_kwh for entry in hourly_plan if entry.battery_action == "charging")
        total_discharged = sum(entry.battery_kwh for entry in hourly_plan if entry.battery_action == "discharging")

        constraints_text = (
            f" Applied constraints: {'; '.join(applied_directives_summary)}."
            if applied_directives_summary
            else " No active operator constraints were applied."
        )

        summary = (
            f"Schedule for scenario '{scenario_id}' optimized with total grid consumption of {total_grid_kwh:.2f} kWh "
            f"at an aggregate cost of {total_cost_bdt:.2f} BDT (peak grid import: {peak_grid_kwh:.2f} kWh). "
            f"Utilized {total_solar_used:.2f} kWh of solar generation. "
            f"Battery dispatched {total_discharged:.2f} kWh across high-tariff periods while storing {total_charged:.2f} kWh during low-cost or surplus solar hours with verified end-of-day energy balance neutrality."
            f"{constraints_text}"
        )
        return summary
