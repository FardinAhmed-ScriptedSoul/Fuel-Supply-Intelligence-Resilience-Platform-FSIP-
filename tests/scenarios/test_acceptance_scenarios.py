"""Acceptance scenario test suite: tests all 6 crisis scenarios and compares policy vs do-nothing."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from scenario_runner import NonePolicy, load_scenario_events  # noqa: E402
from core.models import FuelType, RiskLevel, RouteStatus, StationStatus  # noqa: E402
from core.policies.heuristic import HeuristicPolicy  # noqa: E402


@pytest.mark.parametrize(
    "scenario_name",
    ["baseline", "spike", "route", "delay", "depot", "outage", "combined"],
)
def test_all_scenarios_load_and_have_events(scenario_name: str):
    """Every documented acceptance scenario YAML exists and parses with valid events."""
    events = load_scenario_events(scenario_name)
    assert isinstance(events, list)
    if scenario_name != "baseline":
        assert len(events) >= 1
        assert "type" in events[0]
        assert "start_tick" in events[0]
        assert "end_tick" in events[0]


def test_heuristic_vs_none_policy_on_demand_spike():
    """Under demand spike, heuristic policy produces proactive refills whereas None policy does nothing."""
    none_policy = NonePolicy()
    heuristic = HeuristicPolicy()

    # Create mock snapshot where station inventory is at critical level
    now = SimpleNamespace(
        tick=8,
        sim_time=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        tick_minutes=15,
    )
    station = SimpleNamespace(
        id="station-mirpur",
        name="Mirpur Station",
        region_id="region-dhaka",
        demand_profile="urban_high",
        demand_multiplier=1.8,  # Injected demand spike
        capacity={FuelType.DIESEL: 30000.0, FuelType.PETROL: 25000.0, FuelType.OCTANE: 15000.0},
        inventory={FuelType.DIESEL: 1500.0, FuelType.PETROL: 10000.0, FuelType.OCTANE: 8000.0},
        status=StationStatus.OPEN,
    )
    depot = SimpleNamespace(
        id="depot-gazipur",
        name="Gazipur Depot",
        inventory={FuelType.DIESEL: 60000.0, FuelType.PETROL: 50000.0, FuelType.OCTANE: 30000.0},
        dispatch_capacity_per_tick=15000.0,
        status=StationStatus.OPEN,
    )
    route = SimpleNamespace(
        id="route-gazipur-mirpur",
        source_depot_id="depot-gazipur",
        destination_station_id="station-mirpur",
        status=RouteStatus.AVAILABLE,
        transit_ticks=2,
        max_shipment=10000.0,
    )
    snapshot = SimpleNamespace(
        instance=now,
        stations=[station],
        depots=[depot],
        routes=[route],
        allocations=[],
        demand_history=[],
    )

    # 1. NonePolicy produces 0 allocations -> station will stock out
    none_plans = none_policy.recommend(snapshot, [])
    assert len(none_plans) == 0

    # 2. Heuristic policy evaluates risk and issues an allocation to prevent stockout
    from core.risk import Forecast, ForecastRecord

    record = ForecastRecord(
        forecast=Forecast(
            station_id="station-mirpur",
            fuel_type=FuelType.DIESEL,
            hours_to_stockout=1.5,
            p10_hours=1.0,
            p50_hours=1.5,
            p90_hours=2.0,
            stockout_probability_24h=0.95,
            confidence=0.90,
            risk_level=RiskLevel.CRITICAL,
            needs_review=True,
        ),
        trajectory=[],
        drivers={"demand_multiplier": 1.8},
    )

    plans = heuristic.recommend(snapshot, [record])
    assert len(plans) >= 1
    assert plans[0].request.destination_station_id == "station-mirpur"
    assert plans[0].request.fuel_type == FuelType.DIESEL
    assert plans[0].request.quantity > 0
