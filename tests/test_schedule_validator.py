"""Tests for independent schedule replay and validation."""

import pytest
from gridwise.app.models import BatteryConfig, HourlyPlanEntry
from gridwise.directives.engine import DirectiveEngine
from gridwise.validation.replay import ScheduleReplayEngine
from gridwise.validation.schedule_validator import ScheduleValidator
from gridwise.optimization.solver import EnergyOptimizer
from gridwise.app.errors import ValidationFailedException


def get_base_data():
    demand = [10.0] * 24
    solar = [5.0] * 24
    tariff = [10.0] * 24
    battery = BatteryConfig(
        capacity_kwh=100.0,
        max_charge_kwh=20.0,
        max_discharge_kwh=20.0,
        initial_energy_kwh=40.0,
        min_energy_kwh=10.0
    )
    processed = DirectiveEngine.apply_directives(solar, battery, [])
    plan = EnergyOptimizer.solve(demand, solar, tariff, battery, processed)
    return demand, tariff, battery, processed, plan


def test_validator_passes_on_optimal_plan():
    demand, tariff, battery, processed, plan = get_base_data()
    total_grid, total_cost, peak_grid = ScheduleValidator.validate_and_compute_metrics(
        demand, tariff, battery, processed, plan
    )
    assert total_grid > 0
    assert total_cost > 0
    assert peak_grid > 0


def test_validator_detects_broken_energy_balance():
    demand, tariff, battery, processed, plan = get_base_data()
    # Corrupt grid_kwh at hour 5
    corrupted_plan = [entry.model_copy() for entry in plan]
    corrupted_plan[5].grid_kwh -= 5.0

    with pytest.raises(ValidationFailedException) as exc:
        ScheduleValidator.validate_and_compute_metrics(
            demand, tariff, battery, processed, corrupted_plan
        )
    assert "Energy balance violation" in str(exc.value)


def test_validator_detects_neutrality_violation():
    demand, tariff, battery, processed, plan = get_base_data()
    # Tamper with hour 23 ending battery energy
    corrupted_plan = [entry.model_copy() for entry in plan]
    corrupted_plan[23].battery_energy_after_kwh += 10.0

    with pytest.raises(ValidationFailedException) as exc:
        ScheduleValidator.validate_and_compute_metrics(
            demand, tariff, battery, processed, corrupted_plan
        )
    assert "End-of-day neutrality violation" in str(exc.value) or "Battery dynamics mismatch" in str(exc.value)


def test_validator_detects_solar_overuse():
    demand, tariff, battery, processed, plan = get_base_data()
    corrupted_plan = [entry.model_copy() for entry in plan]
    corrupted_plan[12].solar_used_kwh += 20.0  # Exceeds available solar

    with pytest.raises(ValidationFailedException) as exc:
        ScheduleValidator.validate_and_compute_metrics(
            demand, tariff, battery, processed, corrupted_plan
        )
    assert "exceeds effective solar" in str(exc.value)
