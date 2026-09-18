"""Data validation models and schemas for GridWise.

Uses strict Pydantic v2 validation to guarantee mathematical and schema
integrity before any processing occurs.
"""

import math
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ==============================================================================
# Battery & Request Models
# ==============================================================================

class BatteryConfig(BaseModel):
    """Battery configuration parameters."""
    capacity_kwh: float = Field(..., gt=0.0, description="Total battery capacity in kWh")
    max_charge_kwh: float = Field(..., ge=0.0, description="Max charging rate in kWh per hour")
    max_discharge_kwh: float = Field(..., ge=0.0, description="Max discharging rate in kWh per hour")
    initial_energy_kwh: float = Field(..., ge=0.0, description="Initial energy in battery at start of day")
    min_energy_kwh: float = Field(default=0.0, ge=0.0, description="Minimum allowable energy reserve in battery")

    @model_validator(mode="after")
    def validate_battery_bounds(self) -> "BatteryConfig":
        if not math.isfinite(self.capacity_kwh):
            raise ValueError("capacity_kwh must be a finite number")
        if not math.isfinite(self.max_charge_kwh):
            raise ValueError("max_charge_kwh must be a finite number")
        if not math.isfinite(self.max_discharge_kwh):
            raise ValueError("max_discharge_kwh must be a finite number")
        if not math.isfinite(self.initial_energy_kwh):
            raise ValueError("initial_energy_kwh must be a finite number")
        if not math.isfinite(self.min_energy_kwh):
            raise ValueError("min_energy_kwh must be a finite number")

        if self.min_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"min_energy_kwh ({self.min_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.initial_energy_kwh < self.min_energy_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot be less than min_energy_kwh ({self.min_energy_kwh})"
            )
        return self


class OptimizeEnergyRequest(BaseModel):
    """Complete 24-hour campus energy optimization request."""
    scenario_id: str = Field(..., min_length=1, max_length=100, description="Unique scenario identifier")
    demand: List[float] = Field(..., description="24 hourly electricity demand values in kWh")
    solar: List[float] = Field(..., description="24 hourly solar availability values in kWh")
    tariff: List[float] = Field(..., description="24 hourly grid tariff values in BDT/kWh")
    battery: BatteryConfig = Field(..., description="Battery configuration parameters")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 natural language operator notes")

    @field_validator("demand", "solar", "tariff", mode="after")
    @classmethod
    def validate_24_hours_and_values(cls, values: List[float], info) -> List[float]:
        field_name = info.field_name
        if len(values) != 24:
            raise ValueError(f"'{field_name}' must contain exactly 24 hourly values. Received: {len(values)}")
        for idx, val in enumerate(values):
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"'{field_name}[{idx}]' must be a finite numeric value. Received: {val}")
            if val < 0:
                raise ValueError(f"'{field_name}[{idx}]' must be non-negative. Received: {val}")
        return [float(v) for v in values]

    @field_validator("operator_notes", mode="after")
    @classmethod
    def validate_notes(cls, notes: List[str]) -> List[str]:
        if not (1 <= len(notes) <= 3):
            raise ValueError(f"operator_notes must contain between 1 and 3 items. Received: {len(notes)}")
        sanitized_notes = []
        for idx, note in enumerate(notes):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"operator_notes[{idx}] must be a non-empty string")
            trimmed = note.strip()
            if len(trimmed) > 500:
                raise ValueError(f"operator_notes[{idx}] exceeds maximum character length of 500")
            sanitized_notes.append(trimmed)
        return sanitized_notes


# ==============================================================================
# Directive Interpretation Models
# ==============================================================================

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op"
]

class SolarReductionAdjustment(BaseModel):
    hours: List[int] = Field(..., min_length=1, description="Sorted unique list of start-inclusive, end-exclusive hours")
    factor: float = Field(..., ge=0.0, le=1.0, description="Remaining usable solar multiplier (0.0 to 1.0)")


class MinimumBatteryReserveAdjustment(BaseModel):
    hours: List[int] = Field(..., min_length=1, description="Sorted unique list of hours")
    minimum_energy_kwh: float = Field(..., ge=0.0, description="Minimum battery energy required in kWh")


class WindowHoursAdjustment(BaseModel):
    hours: List[int] = Field(..., min_length=1, description="Sorted unique list of hours")


class MaxGridWindowAdjustment(BaseModel):
    hours: List[int] = Field(..., min_length=1, description="Sorted unique list of hours")
    max_grid_kwh: float = Field(..., ge=0.0, description="Maximum allowable grid import in kWh")


StructuredAdjustmentType = Optional[
    Union[
        SolarReductionAdjustment,
        MinimumBatteryReserveAdjustment,
        WindowHoursAdjustment,
        MaxGridWindowAdjustment,
        Dict[str, Any]
    ]
]


class DirectiveInterpretation(BaseModel):
    """Structured directive interpretation corresponding to one operator note."""
    note_index: int = Field(..., ge=0, description="Zero-based index of corresponding operator note")
    applies: bool = Field(..., description="True if directive applies active constraints, False for no_op")
    directive_type: DirectiveType = Field(..., description="Directive classification name")
    structured_adjustment: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured directive adjustment parameters, or null for no_op"
    )

    @model_validator(mode="after")
    def validate_directive_consistency(self) -> "DirectiveInterpretation":
        if self.directive_type == "no_op":
            if self.applies is not False:
                raise ValueError("no_op directive must have applies = false")
            if self.structured_adjustment is not None:
                raise ValueError("no_op directive must have structured_adjustment = null")
        else:
            if self.applies is not True:
                raise ValueError(f"{self.directive_type} directive must have applies = true")
            if self.structured_adjustment is None:
                raise ValueError(f"{self.directive_type} directive requires non-null structured_adjustment")
        return self


# ==============================================================================
# Hourly Plan and Complete Response Models
# ==============================================================================

BatteryActionType = Literal["charging", "discharging", "idle"]

class HourlyPlanEntry(BaseModel):
    """Hourly energy schedule entry."""
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    grid_kwh: float = Field(..., ge=0.0, description="Electricity imported from the grid in kWh")
    solar_used_kwh: float = Field(..., ge=0.0, description="Solar energy consumed or stored in kWh")
    battery_action: BatteryActionType = Field(..., description="Action taken by battery: charging, discharging, or idle")
    battery_kwh: float = Field(..., ge=0.0, description="Energy charged or discharged during hour in kWh")
    battery_energy_after_kwh: float = Field(..., ge=0.0, description="Battery energy state of charge at end of hour in kWh")


class OptimizeEnergyResponse(BaseModel):
    """Complete response payload for GridWise energy optimization."""
    scenario_id: str = Field(..., description="Matching scenario identifier")
    directive_interpretation: List[DirectiveInterpretation] = Field(
        ...,
        description="Ordered directive interpretation for each operator note"
    )
    hourly_plan: List[HourlyPlanEntry] = Field(..., min_length=24, max_length=24, description="24-hour optimal schedule")
    total_grid_kwh: float = Field(..., ge=0.0, description="Total grid energy imported across 24h in kWh")
    total_cost_bdt: float = Field(..., ge=0.0, description="Total cost of electricity in BDT")
    peak_grid_kwh: float = Field(..., ge=0.0, description="Peak hourly grid import across 24h in kWh")
    plan_summary: str = Field(..., min_length=1, description="Concise human-readable explanation of the plan")


# ==============================================================================
# Error Response Models
# ==============================================================================

class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error category code")
    message: str = Field(..., description="Human-readable safe error message")
    request_id: Optional[str] = Field(default=None, description="Correlation tracking ID")


class ErrorResponse(BaseModel):
    error: ErrorDetail
