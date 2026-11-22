"""Evaluate allocation policies against in-memory disruption scenarios.

The runner only reads the API snapshot. It never resets, steps, or submits to the
simulator, so scenario analysis cannot change simulator or operator state.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "shared"))

from core.models import (  # noqa: E402
    AllocationTerms,
    DepotStatus,
    FuelType,
    RouteStatus,
    Snapshot,
    StationStatus,
)
from core.policies.base import PolicyPlan  # noqa: E402
from core.risk import ForecastRecord, forecast_pair  # noqa: E402

SCENARIO_DIR = PROJECT_ROOT / "scenarios"
SCENARIO_NAMES = ("baseline", "spike", "route", "delay", "depot", "outage", "combined")
POLICY_NAMES = ("none", "naive", "heuristic")


@dataclass(frozen=True)
class ScenarioMetrics:
    scenario: str
    policy: str
    run: int
    ticks: int
    service_level: float
    unmet_demand_liters: float
    served_demand_liters: float
    allocation_liters: float
    allocation_failures: int
    station_tick_stockouts: int
    elapsed_seconds: float


class NonePolicy:
    name = "none"

    def recommend(
        self, snapshot: Snapshot, forecasts: Sequence[ForecastRecord]
    ) -> list[PolicyPlan]:
        return []


class NaivePolicy:
    """Simple low-inventory refill baseline; not a substitute for validation."""

    name = "naive"

    def recommend(
        self, snapshot: Snapshot, forecasts: Sequence[ForecastRecord]
    ) -> list[PolicyPlan]:
        plans: list[PolicyPlan] = []
        for station in snapshot.stations:
            if getattr(station, "status", StationStatus.OPEN) is not StationStatus.OPEN:
                continue
            for fuel in FuelType:
                capacity = station.capacity.get(fuel, 0.0)
                inventory = station.inventory.get(fuel, 0.0)
                if capacity <= 0 or inventory / capacity >= 0.30:
                    continue
                routes = sorted(
                    (
                        route
                        for route in snapshot.routes
                        if route.destination_station_id == station.id
                        and route.status is RouteStatus.AVAILABLE
                    ),
                    key=lambda route: (route.transit_ticks, route.id),
                )
                for route in routes:
                    depot = next(
                        (item for item in snapshot.depots if item.id == route.source_depot_id),
                        None,
                    )
                    if depot is None or getattr(depot, "status", DepotStatus.OPEN) not in {
                        DepotStatus.OPEN,
                        DepotStatus.CONSTRAINED,
                    }:
                        continue
                    quantity = min(
                        route.max_shipment,
                        max(0.0, capacity - inventory),
                        depot.inventory.get(fuel, 0.0),
                        getattr(depot, "dispatch_capacity_per_tick", float("inf")),
                    )
                    if quantity <= 0:
                        continue
                    terms = AllocationTerms(
                        source_depot_id=depot.id,
                        destination_station_id=station.id,
                        route_id=route.id,
                        fuel_type=fuel,
                        quantity=quantity,
                    )
                    plans.append(
                        PolicyPlan(
                            request=terms,
                            stockout_hours=None,
                            arrival_tick=snapshot.instance.tick + route.transit_ticks,
                            projected_inventory_at_arrival=inventory,
                            target_inventory=capacity * 0.70,
                        )
                    )
                    break
        return plans


def load_scenario_events(name: str) -> list[dict[str, Any]]:
    if name not in SCENARIO_NAMES:
        raise ValueError(f"Unknown scenario: {name}")
    path = SCENARIO_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as file:
        scenario = yaml.safe_load(file)
    if not isinstance(scenario, dict) or not isinstance(scenario.get("events"), list):
        raise ValueError(f"Invalid scenario definition: {path}")
    events = scenario["events"]
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError(f"Invalid event in scenario: {path}")
        if event["type"] not in {
            "demand_spike",
            "route_disruption",
            "station_outage",
            "depot_constraint",
            "shipment_delay",
            "supply_shortfall",
        }:
            raise ValueError(f"Unsupported event type in scenario: {event['type']}")
        if not isinstance(event.get("start_tick"), int) or not isinstance(
            event.get("end_tick"), int
        ):
            raise ValueError(f"Event ticks are invalid in scenario: {path}")
        if event["end_tick"] < event["start_tick"]:
            raise ValueError(f"Event ends before it starts in scenario: {path}")
        if not isinstance(event.get("parameters", {}), dict):
            raise ValueError(f"Event parameters are invalid in scenario: {path}")
    return events


def _apply_scenario(snapshot: Snapshot, events: Sequence[dict[str, Any]]) -> Snapshot:
    scenario_snapshot = copy.deepcopy(snapshot)
    for event in events:
        parameters = event.get("parameters", {})
        if event["type"] == "demand_spike":
            regions = set(parameters.get("region_ids", []))
            multiplier = float(parameters.get("multiplier", 1.0))
            for station in scenario_snapshot.stations:
                if station.region_id in regions:
                    station.demand_multiplier *= multiplier
        elif event["type"] == "route_disruption":
            route_ids = set(parameters.get("route_ids", []))
            for route in scenario_snapshot.routes:
                if route.id in route_ids:
                    route.status = RouteStatus.DISRUPTED
        elif event["type"] == "station_outage":
            station_ids = set(parameters.get("station_ids", []))
            if parameters.get("station_id"):
                station_ids.add(parameters["station_id"])
            for station in scenario_snapshot.stations:
                if station.id in station_ids:
                    station.status = StationStatus.OUTAGE
        elif event["type"] == "depot_constraint":
            depot_ids = set(parameters.get("depot_ids", []))
            if parameters.get("depot_id"):
                depot_ids.add(parameters["depot_id"])
            for depot in scenario_snapshot.depots:
                if depot.id in depot_ids:
                    depot.status = DepotStatus.CONSTRAINED
                    dispatch_limit = parameters.get("dispatch_capacity_per_tick")
                    if dispatch_limit is not None:
                        depot.dispatch_capacity_per_tick = min(
                            depot.dispatch_capacity_per_tick, float(dispatch_limit)
                        )
        elif event["type"] == "shipment_delay":
            supply_id = parameters.get("supply_id")
            delay = max(0, int(parameters.get("delayed_ticks", 0)))
            for arrival in scenario_snapshot.supply_arrivals:
                if arrival.id == supply_id:
                    arrival.planned_tick += delay
        elif event["type"] == "supply_shortfall":
            depot_ids = set(parameters.get("depot_ids", []))
            if parameters.get("depot_id"):
                depot_ids.add(parameters["depot_id"])
            fuel = parameters.get("fuel_type")
            reduction = max(0.0, float(parameters.get("quantity", 0.0)))
            for depot in scenario_snapshot.depots:
                if depot.id in depot_ids and fuel:
                    fuel_type = FuelType(fuel)
                    depot.inventory[fuel_type] = max(
                        0.0, depot.inventory.get(fuel_type, 0.0) - reduction
                    )
    return scenario_snapshot


def _policy(name: str) -> Any:
    if name == "none":
        return NonePolicy()
    if name == "naive":
        return NaivePolicy()
    if name == "heuristic":
        from core.policies.heuristic import HeuristicPolicy

        return HeuristicPolicy()
    raise ValueError(f"Unknown policy: {name}")


def _forecasts(snapshot: Snapshot) -> list[ForecastRecord]:
    return [
        forecast_pair(snapshot, station, fuel, seed=snapshot.instance.seed)
        for station in snapshot.stations
        for fuel in FuelType
        if fuel in station.inventory
    ]


def _evaluate(
    snapshot: Snapshot, scenario_name: str, policy_name: str, ticks: int
) -> dict[str, Any]:
    events = load_scenario_events(scenario_name)
    scenario_snapshot = _apply_scenario(snapshot, events)
    forecasts = _forecasts(scenario_snapshot)
    plans = _policy(policy_name).recommend(scenario_snapshot, forecasts)
    horizon_tick = scenario_snapshot.instance.tick + ticks
    plans = [plan for plan in plans if plan.arrival_tick <= horizon_tick]
    return {
        "scenario": scenario_name,
        "policy": policy_name,
        "snapshot_tick": scenario_snapshot.instance.tick,
        "planning_horizon_ticks": ticks,
        "event_count": len(events),
        "plans": [plan.request.model_dump(mode="json") for plan in plans],
        "planned_liters": round(sum(plan.request.quantity for plan in plans), 3),
    }


def _evaluate_twice(
    snapshot: Snapshot, scenario_name: str, policy_name: str, ticks: int
) -> dict[str, Any]:
    result = _evaluate(snapshot, scenario_name, policy_name, ticks)
    repeat = _evaluate(snapshot, scenario_name, policy_name, ticks)
    result["deterministic"] = result["plans"] == repeat["plans"]
    return result


def _read_snapshot(api_url: str) -> Snapshot:
    with urlopen(f"{api_url.rstrip('/')}/api/state", timeout=10) as response:
        payload = json.load(response)
    snapshot_payload = payload.get("snapshot", payload)
    return Snapshot.model_validate(snapshot_payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8101")
    parser.add_argument("--scenario", choices=SCENARIO_NAMES, default="baseline")
    parser.add_argument("--policy", choices=POLICY_NAMES, default="heuristic")
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--all", action="store_true", help="evaluate all scenarios and policies")
    args = parser.parse_args(argv)
    if args.ticks <= 0:
        parser.error("--ticks must be positive")

    snapshot = _read_snapshot(args.api_url)
    scenario_names = SCENARIO_NAMES if args.all else (args.scenario,)
    policy_names = POLICY_NAMES if args.all else (args.policy,)
    evaluator = _evaluate_twice if args.all else _evaluate
    results = [
        evaluator(snapshot, scenario, policy, args.ticks)
        for scenario in scenario_names
        for policy in policy_names
    ]
    print(json.dumps({"mode": "read-only", "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
