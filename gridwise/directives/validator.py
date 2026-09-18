"""Deterministic validator for structured directives.

Performs strict schema and semantic validation of all directive interpretations
before any adjustments can reach the optimization model.
"""

import math
from typing import Any, Dict, List, Optional
from gridwise.app.models import DirectiveInterpretation, DirectiveType
from gridwise.app.errors import InvalidRequestException


SUPPORTED_DIRECTIVE_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
}


def validate_hours_list(hours: Any, context: str = "hours") -> List[int]:
    """Validates that hours is a non-empty, sorted, unique list of integers in [0, 23]."""
    if not isinstance(hours, list):
        raise InvalidRequestException(f"{context} must be a JSON array of integers")
    if len(hours) == 0:
        raise InvalidRequestException(f"{context} cannot be empty")
    
    seen = set()
    cleaned_hours = []
    for val in hours:
        if not isinstance(val, int) or isinstance(val, bool):
            raise InvalidRequestException(f"{context} entries must be integers, got {type(val).__name__}: {val}")
        if val < 0 or val > 23:
            raise InvalidRequestException(f"{context} values must be within 0 to 23 inclusive, got {val}")
        if val in seen:
            raise InvalidRequestException(f"{context} contains duplicate hour: {val}")
        seen.add(val)
        cleaned_hours.append(val)
    
    # Verify hours are sorted
    if cleaned_hours != sorted(cleaned_hours):
        # We can either normalize by sorting or enforce strict sort.
        cleaned_hours = sorted(cleaned_hours)
        
    return cleaned_hours


def validate_directive_interpretation(
    directive: DirectiveInterpretation,
    expected_note_index: int,
    battery_capacity_kwh: Optional[float] = None
) -> DirectiveInterpretation:
    """Performs deep semantic and mathematical validation on a single directive."""
    if directive.note_index != expected_note_index:
        raise InvalidRequestException(
            f"Directive note_index mismatch: expected {expected_note_index}, got {directive.note_index}"
        )

    if directive.directive_type not in SUPPORTED_DIRECTIVE_TYPES:
        raise InvalidRequestException(
            f"Unsupported directive type: '{directive.directive_type}'"
        )

    if directive.directive_type == "no_op":
        if directive.applies is not False:
            raise InvalidRequestException("Directive 'no_op' must have applies=false")
        if directive.structured_adjustment is not None:
            raise InvalidRequestException("Directive 'no_op' must have structured_adjustment=null")
        return directive

    # For all active directives
    if directive.applies is not True:
        raise InvalidRequestException(f"Directive '{directive.directive_type}' must have applies=true")
    if not isinstance(directive.structured_adjustment, dict):
        raise InvalidRequestException(f"Directive '{directive.directive_type}' requires structured_adjustment dictionary")

    adj = directive.structured_adjustment

    if directive.directive_type == "solar_reduction":
        allowed_keys = {"hours", "factor"}
        if set(adj.keys()) != allowed_keys:
            raise InvalidRequestException(f"solar_reduction adjustment keys must be exactly {allowed_keys}")
        
        hours = validate_hours_list(adj.get("hours"), "solar_reduction.hours")
        factor = adj.get("factor")
        if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not math.isfinite(factor):
            raise InvalidRequestException("solar_reduction factor must be a finite number")
        factor = float(factor)
        if factor < 0.0 or factor > 1.0:
            raise InvalidRequestException(f"solar_reduction factor must be in [0.0, 1.0], got {factor}")
        
        return DirectiveInterpretation(
            note_index=expected_note_index,
            applies=True,
            directive_type="solar_reduction",
            structured_adjustment={"hours": hours, "factor": factor}
        )

    elif directive.directive_type == "minimum_battery_reserve":
        allowed_keys = {"hours", "minimum_energy_kwh"}
        if set(adj.keys()) != allowed_keys:
            raise InvalidRequestException(f"minimum_battery_reserve adjustment keys must be exactly {allowed_keys}")
        
        hours = validate_hours_list(adj.get("hours"), "minimum_battery_reserve.hours")
        min_e = adj.get("minimum_energy_kwh")
        if not isinstance(min_e, (int, float)) or isinstance(min_e, bool) or not math.isfinite(min_e):
            raise InvalidRequestException("minimum_energy_kwh must be a finite number")
        min_e = float(min_e)
        if min_e < 0.0:
            raise InvalidRequestException(f"minimum_energy_kwh cannot be negative, got {min_e}")
        if battery_capacity_kwh is not None and min_e > battery_capacity_kwh:
            raise InvalidRequestException(
                f"minimum_energy_kwh ({min_e}) cannot exceed battery capacity ({battery_capacity_kwh})"
            )

        return DirectiveInterpretation(
            note_index=expected_note_index,
            applies=True,
            directive_type="minimum_battery_reserve",
            structured_adjustment={"hours": hours, "minimum_energy_kwh": min_e}
        )

    elif directive.directive_type == "no_charge_window":
        allowed_keys = {"hours"}
        if set(adj.keys()) != allowed_keys:
            raise InvalidRequestException(f"no_charge_window adjustment keys must be exactly {allowed_keys}")
        hours = validate_hours_list(adj.get("hours"), "no_charge_window.hours")
        return DirectiveInterpretation(
            note_index=expected_note_index,
            applies=True,
            directive_type="no_charge_window",
            structured_adjustment={"hours": hours}
        )

    elif directive.directive_type == "no_discharge_window":
        allowed_keys = {"hours"}
        if set(adj.keys()) != allowed_keys:
            raise InvalidRequestException(f"no_discharge_window adjustment keys must be exactly {allowed_keys}")
        hours = validate_hours_list(adj.get("hours"), "no_discharge_window.hours")
        return DirectiveInterpretation(
            note_index=expected_note_index,
            applies=True,
            directive_type="no_discharge_window",
            structured_adjustment={"hours": hours}
        )

    elif directive.directive_type == "max_grid_window":
        allowed_keys = {"hours", "max_grid_kwh"}
        if set(adj.keys()) != allowed_keys:
            raise InvalidRequestException(f"max_grid_window adjustment keys must be exactly {allowed_keys}")
        hours = validate_hours_list(adj.get("hours"), "max_grid_window.hours")
        max_grid = adj.get("max_grid_kwh")
        if not isinstance(max_grid, (int, float)) or isinstance(max_grid, bool) or not math.isfinite(max_grid):
            raise InvalidRequestException("max_grid_kwh must be a finite number")
        max_grid = float(max_grid)
        if max_grid < 0.0:
            raise InvalidRequestException(f"max_grid_kwh cannot be negative, got {max_grid}")

        return DirectiveInterpretation(
            note_index=expected_note_index,
            applies=True,
            directive_type="max_grid_window",
            structured_adjustment={"hours": hours, "max_grid_kwh": max_grid}
        )

    raise InvalidRequestException(f"Unrecognized directive type: {directive.directive_type}")


def validate_all_directives(
    directives: List[DirectiveInterpretation],
    expected_count: int,
    battery_capacity_kwh: Optional[float] = None
) -> List[DirectiveInterpretation]:
    """Validates full list of directives, ensuring 1-to-1 ordered correspondence."""
    if len(directives) != expected_count:
        raise InvalidRequestException(
            f"Expected exactly {expected_count} directive interpretations, but received {len(directives)}"
        )
    
    validated = []
    for idx, d in enumerate(directives):
        validated_d = validate_directive_interpretation(
            directive=d,
            expected_note_index=idx,
            battery_capacity_kwh=battery_capacity_kwh
        )
        validated.append(validated_d)
    return validated
