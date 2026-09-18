"""Tests for request and battery input validation."""

import pytest
from pydantic import ValidationError
from gridwise.app.models import BatteryConfig, OptimizeEnergyRequest


def create_valid_payload_data():
    return {
        "scenario_id": "test_scenario_01",
        "demand": [10.0] * 24,
        "solar": [5.0] * 24,
        "tariff": [8.5] * 24,
        "battery": {
            "capacity_kwh": 100.0,
            "max_charge_kwh": 25.0,
            "max_discharge_kwh": 25.0,
            "initial_energy_kwh": 50.0,
            "min_energy_kwh": 10.0
        },
        "operator_notes": ["PV production will drop to 20% between 13:00 and 15:00."]
    }


def test_valid_request_payload():
    data = create_valid_payload_data()
    req = OptimizeEnergyRequest.model_validate(data)
    assert req.scenario_id == "test_scenario_01"
    assert len(req.demand) == 24
    assert len(req.operator_notes) == 1


def test_invalid_demand_length():
    data = create_valid_payload_data()
    data["demand"] = [10.0] * 23  # Only 23 values
    with pytest.raises(ValidationError) as exc:
        OptimizeEnergyRequest.model_validate(data)
    assert "must contain exactly 24 hourly values" in str(exc.value)


def test_negative_tariff_value():
    data = create_valid_payload_data()
    data["tariff"][5] = -1.0
    with pytest.raises(ValidationError) as exc:
        OptimizeEnergyRequest.model_validate(data)
    assert "must be non-negative" in str(exc.value)


def test_nan_or_inf_value():
    data = create_valid_payload_data()
    data["solar"][10] = float("inf")
    with pytest.raises(ValidationError) as exc:
        OptimizeEnergyRequest.model_validate(data)
    assert "must be a finite numeric value" in str(exc.value)


def test_battery_bounds_min_greater_than_capacity():
    with pytest.raises(ValidationError) as exc:
        BatteryConfig(
            capacity_kwh=100.0,
            max_charge_kwh=20.0,
            max_discharge_kwh=20.0,
            initial_energy_kwh=50.0,
            min_energy_kwh=110.0  # min > capacity
        )
    assert "cannot exceed capacity_kwh" in str(exc.value)


def test_battery_bounds_initial_less_than_min():
    with pytest.raises(ValidationError) as exc:
        BatteryConfig(
            capacity_kwh=100.0,
            max_charge_kwh=20.0,
            max_discharge_kwh=20.0,
            initial_energy_kwh=15.0,
            min_energy_kwh=20.0  # initial < min
        )
    assert "cannot be less than min_energy_kwh" in str(exc.value)


def test_invalid_operator_notes_count():
    data = create_valid_payload_data()
    data["operator_notes"] = []  # Empty notes
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest.model_validate(data)

    data["operator_notes"] = ["Note 1", "Note 2", "Note 3", "Note 4"]  # 4 notes
    with pytest.raises(ValidationError):
        OptimizeEnergyRequest.model_validate(data)


def test_oversized_operator_note():
    data = create_valid_payload_data()
    data["operator_notes"] = ["A" * 600]
    with pytest.raises(ValidationError) as exc:
        OptimizeEnergyRequest.model_validate(data)
    assert "exceeds maximum character length" in str(exc.value)
