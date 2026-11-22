import json
from pathlib import Path

import pytest

from core.models import Allocation, AllocationRequest, FuelType, Snapshot
from core.validator import Violation, validate

SAMPLES = Path(__file__).parents[2] / "docs" / "sim-samples"


def snapshot_fixture() -> Snapshot:
    raw = {
        name: json.loads((SAMPLES / f"{name}.json").read_text())
        for name in (
            "instance",
            "regions",
            "depots",
            "stations",
            "routes",
            "supply-arrivals",
            "events",
            "metrics",
        )
    }
    raw["supply_arrivals"] = raw.pop("supply-arrivals")
    raw.update(
        allocations=[],
        demand_history=[],
        fetched_at="2026-01-01T00:00:00Z",
        stale=False,
        data_status="HEALTHY",
    )
    return Snapshot.model_validate(raw)


def request(**overrides: object) -> AllocationRequest:
    values: dict[str, object] = {
        "idempotency_key": "rec-test",
        "source_depot_id": "depot-gazipur",
        "destination_station_id": "station-mirpur",
        "route_id": "route-gazipur-mirpur",
        "fuel_type": "DIESEL",
        "quantity": 3000,
    }
    values.update(overrides)
    return AllocationRequest.model_validate(values)


@pytest.mark.parametrize(
    ("mutation", "overrides", "expected_code"),
    [
        ("", {"source_depot_id": "missing-depot"}, "NOT_FOUND"),
        ("", {"destination_station_id": "station-tongi"}, "ROUTE_MISMATCH"),
        ("closed_depot", {}, "DEPOT_CLOSED"),
        ("outage_station", {}, "STATION_CLOSED"),
        ("disrupted_route", {}, "ROUTE_DISRUPTED"),
        ("", {"quantity": 7001}, "ROUTE_CAPACITY_EXCEEDED"),
        ("low_inventory", {"quantity": 1001}, "INSUFFICIENT_INVENTORY"),
        ("", {"quantity": 6500}, "DESTINATION_CAPACITY_EXCEEDED"),
    ],
)
def test_validator_reports_simulator_violations_in_order(
    mutation: str, overrides: dict[str, object], expected_code: str
) -> None:
    snapshot = snapshot_fixture()
    if mutation == "closed_depot":
        snapshot.depots[0].status = "CLOSED"
    elif mutation == "outage_station":
        snapshot.stations[0].status = "OUTAGE"
    elif mutation == "disrupted_route":
        snapshot.routes[0].status = "DISRUPTED"
    elif mutation == "low_inventory":
        snapshot.depots[0].inventory[FuelType.DIESEL] = 1000

    violations = validate(request(**overrides), snapshot)

    assert violations
    assert violations[0].code == expected_code


def test_dispatch_capacity_includes_pending_and_in_flight_allocations_for_this_tick() -> None:
    snapshot = snapshot_fixture()
    snapshot.allocations = [
        Allocation.model_validate(
            {
                "id": 1,
                "idempotency_key": "same-tick",
                "source_depot_id": "depot-gazipur",
                "destination_station_id": "station-tongi",
                "route_id": "route-gazipur-tongi",
                "fuel_type": "PETROL",
                "quantity": 6500,
                "created_tick": snapshot.instance.tick,
                "departure_tick": snapshot.instance.tick,
                "expected_arrival_tick": snapshot.instance.tick + 2,
                "actual_arrival_tick": None,
                "status": "IN_TRANSIT",
                "failure_reason": None,
            }
        ),
    ]

    violations = validate(request(quantity=6500), snapshot)

    assert [violation.code for violation in violations] == ["DISPATCH_CAPACITY_EXCEEDED"]


def test_validator_accounts_for_prior_planning_reservations() -> None:
    snapshot = snapshot_fixture()
    prior = request(quantity=4000)

    violations = validate(request(quantity=3000), snapshot, reservations=[prior])

    assert [violation.code for violation in violations] == ["DESTINATION_CAPACITY_EXCEEDED"]


def test_validator_accepts_feasible_allocation() -> None:
    assert validate(request(), snapshot_fixture()) == []


def test_validator_accepts_exact_idempotency_replay_before_current_constraints() -> None:
    snapshot = snapshot_fixture()
    prior = request()
    snapshot.allocations = [
        Allocation.model_validate(
            {
                "id": 7,
                **prior.model_dump(mode="json"),
                "created_tick": snapshot.instance.tick,
                "departure_tick": None,
                "expected_arrival_tick": None,
                "actual_arrival_tick": None,
                "status": "PENDING",
                "failure_reason": None,
            }
        )
    ]
    snapshot.depots[0].inventory[FuelType.DIESEL] = 0

    assert validate(prior, snapshot) == []


def test_validator_blocks_same_idempotency_key_with_different_body() -> None:
    snapshot = snapshot_fixture()
    prior = request()
    snapshot.allocations = [
        Allocation.model_validate(
            {
                "id": 7,
                **prior.model_dump(mode="json"),
                "created_tick": snapshot.instance.tick,
                "departure_tick": None,
                "expected_arrival_tick": None,
                "actual_arrival_tick": None,
                "status": "PENDING",
                "failure_reason": None,
            }
        )
    ]

    violations = validate(request(quantity=3001), snapshot)

    assert [violation.code for violation in violations] == ["IDEMPOTENCY_KEY_MISMATCH"]


def test_violation_is_immutable_and_explicit() -> None:
    violation = Violation("NOT_FOUND", "source depot missing")

    assert violation.code == "NOT_FOUND"
    assert violation.message == "source depot missing"


def test_route_disruption_event_blocks_dispatch() -> None:
    """F-010: Verify scheduled or active route disruption event covering departure tick blocks dispatch."""
    snapshot = snapshot_fixture()
    # Inject a scheduled route disruption covering departure tick (instance.tick + 1)
    dep_tick = snapshot.instance.tick + 1
    event_dict = {
        "id": 101,
        "type": "route_disruption",
        "status": "SCHEDULED",
        "start_tick": dep_tick,
        "end_tick": dep_tick + 4,
        "parameters": {"route_ids": ["route-gazipur-mirpur"]},
    }
    # Append event to snapshot
    from core.models import SimEvent

    snapshot.events.append(SimEvent.model_validate(event_dict))

    violations = validate(request(), snapshot)
    assert len(violations) > 0
    assert violations[0].code == "ROUTE_DISRUPTED"
    assert "departure tick" in violations[0].message


def test_inflight_headroom_exceeded_blocks_dispatch() -> None:
    """F-010: Destination capacity calculation must account for in-flight allocations."""
    snapshot = snapshot_fixture()
    # Find destination station capacity and inventory
    station = next(s for s in snapshot.stations if s.id == "station-mirpur")
    cap = station.capacity[FuelType.DIESEL]
    station.inventory[FuelType.DIESEL] = cap - 4000  # 4000L available headroom

    # Add an in-flight allocation of 2000L heading to this station
    snapshot.allocations.append(
        Allocation.model_validate(
            {
                "id": 991,
                "idempotency_key": "in-flight-other",
                "source_depot_id": "depot-gazipur",
                "destination_station_id": "station-mirpur",
                "route_id": "route-gazipur-mirpur",
                "fuel_type": "DIESEL",
                "quantity": 2000,
                "created_tick": snapshot.instance.tick - 1,
                "departure_tick": snapshot.instance.tick - 1,
                "expected_arrival_tick": snapshot.instance.tick + 1,
                "actual_arrival_tick": None,
                "status": "IN_TRANSIT",
                "failure_reason": None,
            }
        )
    )

    # Requesting 3000L would exceed total capacity (remaining headroom is only 2000L)
    violations = validate(request(quantity=3000), snapshot)
    assert len(violations) > 0
    assert violations[0].code == "DESTINATION_CAPACITY_EXCEEDED"
    assert "in-flight" in violations[0].message


def test_depot_inventory_net_of_pending_allocations_blocks_dispatch() -> None:
    """F-010: Depot available inventory must deduct already pending allocations."""
    snapshot = snapshot_fixture()
    depot = next(d for d in snapshot.depots if d.id == "depot-gazipur")
    depot.inventory[FuelType.DIESEL] = 5000

    # Add a pending allocation consuming 3000L
    snapshot.allocations.append(
        Allocation.model_validate(
            {
                "id": 992,
                "idempotency_key": "pending-other",
                "source_depot_id": "depot-gazipur",
                "destination_station_id": "station-dhanmondi",
                "route_id": "route-gazipur-dhanmondi",
                "fuel_type": "DIESEL",
                "quantity": 3000,
                "created_tick": snapshot.instance.tick,
                "departure_tick": None,
                "expected_arrival_tick": None,
                "actual_arrival_tick": None,
                "status": "PENDING",
                "failure_reason": None,
            }
        )
    )

    # Requesting 3000L when only 2000L net inventory remains must fail
    violations = validate(request(quantity=3000), snapshot)
    assert len(violations) > 0
    assert violations[0].code == "INSUFFICIENT_INVENTORY"
    assert "pending shipments" in violations[0].message
