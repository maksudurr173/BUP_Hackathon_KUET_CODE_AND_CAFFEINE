"""Tests for the mathematical optimization engine."""

import pytest
from gridwise.app.models import BatteryConfig, DirectiveInterpretation
from gridwise.directives.engine import DirectiveEngine
from gridwise.optimization.solver import EnergyOptimizer


def get_base_scenario():
    # 24-hour typical demand, solar curve, and TOU tariff
    demand = [
        15, 12, 10, 10, 12, 18, 30, 45, 60, 70, 75, 80,
        85, 80, 75, 70, 65, 80, 95, 90, 70, 50, 35, 20
    ]
    solar = [
        0, 0, 0, 0, 0, 5, 20, 40, 60, 80, 90, 95,
        90, 85, 70, 50, 25, 10, 0, 0, 0, 0, 0, 0
    ]
    # Cheap night (5 BDT), expensive peak 17-21 (15 BDT), normal day (10 BDT)
    tariff = [
        5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0,
        10.0, 10.0, 10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 15.0, 10.0, 5.0, 5.0
    ]
    battery = BatteryConfig(
        capacity_kwh=100.0,
        max_charge_kwh=25.0,
        max_discharge_kwh=25.0,
        initial_energy_kwh=40.0,
        min_energy_kwh=10.0
    )
    return demand, solar, tariff, battery


def test_basic_optimization_and_neutrality():
    demand, solar, tariff, battery = get_base_scenario()
    processed = DirectiveEngine.apply_directives(solar, battery, [])
    
    plan = EnergyOptimizer.solve(
        demand=demand,
        solar=solar,
        tariff=tariff,
        battery=battery,
        processed_directives=processed
    )

    assert len(plan) == 24
    # Verify end-of-day battery neutrality
    assert abs(plan[23].battery_energy_after_kwh - battery.initial_energy_kwh) < 1e-2


def test_no_charge_window_enforcement():
    demand, solar, tariff, battery = get_base_scenario()
    no_charge_directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="no_charge_window",
        structured_adjustment={"hours": [2, 3, 4]}
    )
    processed = DirectiveEngine.apply_directives(solar, battery, [no_charge_directive])
    plan = EnergyOptimizer.solve(demand, solar, tariff, battery, processed)

    for h in [2, 3, 4]:
        entry = plan[h]
        assert entry.battery_action != "charging"
        if entry.battery_action == "discharging":
            assert entry.battery_kwh > 0
        else:
            assert entry.battery_kwh == 0.0


def test_no_discharge_window_enforcement():
    demand, solar, tariff, battery = get_base_scenario()
    no_discharge_directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="no_discharge_window",
        structured_adjustment={"hours": [18, 19]}
    )
    processed = DirectiveEngine.apply_directives(solar, battery, [no_discharge_directive])
    plan = EnergyOptimizer.solve(demand, solar, tariff, battery, processed)

    for h in [18, 19]:
        entry = plan[h]
        assert entry.battery_action != "discharging"


def test_minimum_reserve_enforcement():
    demand, solar, tariff, battery = get_base_scenario()
    reserve_directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="minimum_battery_reserve",
        structured_adjustment={"hours": [17, 18, 19], "minimum_energy_kwh": 75.0}
    )
    processed = DirectiveEngine.apply_directives(solar, battery, [reserve_directive])
    plan = EnergyOptimizer.solve(demand, solar, tariff, battery, processed)

    for h in [17, 18, 19]:
        assert plan[h].battery_energy_after_kwh >= 75.0 - 1e-2


def test_max_grid_window_enforcement():
    demand, solar, tariff, battery = get_base_scenario()
    grid_cap_directive = DirectiveInterpretation(
        note_index=0,
        applies=True,
        directive_type="max_grid_window",
        structured_adjustment={"hours": [21, 22], "max_grid_kwh": 30.0}
    )
    processed = DirectiveEngine.apply_directives(solar, battery, [grid_cap_directive])
    plan = EnergyOptimizer.solve(demand, solar, tariff, battery, processed)

    for h in [21, 22]:
        assert plan[h].grid_kwh <= 30.0 + 1e-2

