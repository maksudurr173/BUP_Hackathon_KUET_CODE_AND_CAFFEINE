"""Tests for directive validation and the directive engine."""

import pytest
from gridwise.app.models import DirectiveInterpretation, BatteryConfig
from gridwise.directives.validator import (
    validate_directive_interpretation,
    validate_all_directives,
    validate_hours_list,
)
from gridwise.directives.engine import DirectiveEngine
from gridwise.app.errors import InvalidRequestException


def test_validate_hours_normalization():
    assert validate_hours_list([13, 14]) == [13, 14]
    assert validate_hours_list([15, 14]) == [14, 15]  # Auto-sorts
    with pytest.raises(InvalidRequestException):
        validate_hours_list([])
    with pytest.raises(InvalidRequestException):
        validate_hours_list([24])  # >23
    with pytest.raises(InvalidRequestException):
        validate_hours_list([-1])  # <0
    with pytest.raises(InvalidRequestException):
        validate_hours_list([10, 10])  # Duplicate


def test_validate_solar_reduction():
    d = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="solar_reduction",
        structured_adjustment={"hours": [13, 14], "factor": 0.2}
    )
    validated = validate_directive_interpretation(d, expected_note_index=0)
    assert validated.directive_type == "solar_reduction"
    assert validated.structured_adjustment["factor"] == 0.2


def test_validate_solar_reduction_invalid_factor():
    d = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="solar_reduction",
        structured_adjustment={"hours": [13, 14], "factor": 1.5}
    )
    with pytest.raises(InvalidRequestException):
        validate_directive_interpretation(d, expected_note_index=0)


def test_validate_minimum_battery_reserve():
    d = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="minimum_battery_reserve",
        structured_adjustment={"hours": [18, 19, 20], "minimum_energy_kwh": 120.0}
    )
    validated = validate_directive_interpretation(d, expected_note_index=0, battery_capacity_kwh=150.0)
    assert validated.structured_adjustment["minimum_energy_kwh"] == 120.0

    # Exceeds capacity check
    with pytest.raises(InvalidRequestException):
        validate_directive_interpretation(d, expected_note_index=0, battery_capacity_kwh=100.0)


def test_validate_no_op():
    d = DirectiveInterpretation(
        note_index=1,
        applies=False,
        directive_type="no_op",
        structured_adjustment=None
    )
    validated = validate_directive_interpretation(d, expected_note_index=1)
    assert validated.applies is False
    assert validated.structured_adjustment is None


def test_directive_engine_multiple_directives():
    base_solar = [10.0] * 24
    battery = BatteryConfig(
        capacity_kwh=100.0,
        max_charge_kwh=20.0,
        max_discharge_kwh=20.0,
        initial_energy_kwh=50.0,
        min_energy_kwh=10.0
    )

    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type="solar_reduction",
            structured_adjustment={"hours": [13, 14], "factor": 0.2}
        ),
        DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type="no_charge_window",
            structured_adjustment={"hours": [14, 15]}
        ),
        DirectiveInterpretation(
            note_index=2,
            applies=True,
            directive_type="max_grid_window",
            structured_adjustment={"hours": [18, 19], "max_grid_kwh": 40.0}
        )
    ]

    processed = DirectiveEngine.apply_directives(base_solar, battery, directives)
    
    # Solar reduced at 13 and 14
    assert processed.effective_solar[13] == 2.0
    assert processed.effective_solar[14] == 2.0
    assert processed.effective_solar[12] == 10.0

    # No charge at 14 and 15
    assert 14 in processed.no_charge_hours
    assert 15 in processed.no_charge_hours
    assert 13 not in processed.no_charge_hours

    # Max grid at 18 and 19
    assert processed.max_grid_limits[18] == 40.0
    assert processed.max_grid_limits[19] == 40.0
