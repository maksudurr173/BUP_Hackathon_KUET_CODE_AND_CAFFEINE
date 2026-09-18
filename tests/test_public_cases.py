"""Integration tests covering diverse 24-hour campus energy challenge cases."""

import pytest
from httpx import AsyncClient, ASGITransport
from gridwise.app.api import app


@pytest.mark.asyncio
async def test_high_solar_surplus_scenario():
    """Campus scenario with high solar generation exceeding midday demand."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "scenario_id": "campus_high_solar_summer",
            "demand": [
                20, 20, 20, 20, 25, 30, 40, 50, 60, 65, 70, 75,
                75, 70, 65, 60, 55, 60, 80, 85, 70, 50, 30, 25
            ],
            "solar": [
                0, 0, 0, 0, 0, 10, 35, 70, 110, 140, 160, 170,
                165, 150, 120, 85, 45, 15, 0, 0, 0, 0, 0, 0
            ],
            "tariff": [
                6.0, 6.0, 6.0, 6.0, 6.0, 6.0, 10.0, 10.0, 12.0, 12.0, 12.0, 12.0,
                12.0, 12.0, 12.0, 12.0, 12.0, 18.0, 18.0, 18.0, 18.0, 12.0, 6.0, 6.0
            ],
            "battery": {
                "capacity_kwh": 200.0,
                "max_charge_kwh": 50.0,
                "max_discharge_kwh": 50.0,
                "initial_energy_kwh": 50.0,
                "min_energy_kwh": 20.0
            },
            "operator_notes": [
                "Expect a 50% solar reduction between 11:00 and 13:00 due to dust storm.",
                "Maintain at least 80 kWh battery reserve between 18:00 and 22:00."
            ]
        }
        resp = await client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["scenario_id"] == "campus_high_solar_summer"
        assert len(data["directive_interpretation"]) == 2
        
        # Check solar reduction directive was correctly parsed: hours 11, 12 and factor 0.5
        d0 = data["directive_interpretation"][0]
        assert d0["directive_type"] == "solar_reduction"
        assert d0["structured_adjustment"]["hours"] == [11, 12]
        assert d0["structured_adjustment"]["factor"] == 0.5

        # Check reserve directive was correctly parsed: hours 18, 19, 20, 21
        d1 = data["directive_interpretation"][1]
        assert d1["directive_type"] == "minimum_battery_reserve"
        assert d1["structured_adjustment"]["hours"] == [18, 19, 20, 21]
        assert d1["structured_adjustment"]["minimum_energy_kwh"] == 80.0

        # Check ending battery energy is equal to initial (50.0 kWh)
        plan = data["hourly_plan"]
        assert abs(plan[23]["battery_energy_after_kwh"] - 50.0) < 0.05

        # Check battery reserve held between 18 and 21
        for h in [18, 19, 20, 21]:
            assert plan[h]["battery_energy_after_kwh"] >= 80.0 - 0.01


@pytest.mark.asyncio
async def test_triple_notes_complex_scenario():
    """Scenario combining three simultaneous operator directives."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "scenario_id": "complex_triple_notes_case",
            "demand": [
                10, 10, 10, 10, 15, 20, 30, 40, 50, 60, 60, 65,
                65, 60, 55, 50, 45, 55, 70, 75, 60, 40, 25, 15
            ],
            "solar": [
                0, 0, 0, 0, 0, 5, 15, 30, 50, 70, 80, 85,
                80, 75, 60, 40, 20, 5, 0, 0, 0, 0, 0, 0
            ],
            "tariff": [
                5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0,
                9.0, 9.0, 9.0, 9.0, 9.0, 16.0, 16.0, 16.0, 16.0, 9.0, 5.0, 5.0
            ],
            "battery": {
                "capacity_kwh": 120.0,
                "max_charge_kwh": 30.0,
                "max_discharge_kwh": 30.0,
                "initial_energy_kwh": 40.0,
                "min_energy_kwh": 10.0
            },
            "operator_notes": [
                "PV output drops to 30% from 12:00 to 14:00.",
                "Do not charge battery between 14:00 and 16:00.",
                "Avoid discharging battery between 6 PM and 8 PM."
            ]
        }
        resp = await client.post("/optimize-energy", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["directive_interpretation"]) == 3
        # Directives order check
        assert data["directive_interpretation"][0]["directive_type"] == "solar_reduction"
        assert data["directive_interpretation"][1]["directive_type"] == "no_charge_window"
        assert data["directive_interpretation"][2]["directive_type"] == "no_discharge_window"

        plan = data["hourly_plan"]
        # Check no charge at 14 and 15
        for h in [14, 15]:
            assert plan[h]["battery_action"] != "charging"

        # Check no discharge at 18 and 19 (6 PM to 8 PM)
        for h in [18, 19]:
            assert plan[h]["battery_action"] != "discharging"
