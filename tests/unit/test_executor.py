from __future__ import annotations

import json
from pathlib import Path

import pytest
from worker.executor import Executor

from core.models import Allocation, Snapshot
from core.sim_client import SimBusinessError, SimUnavailable

SAMPLES = Path(__file__).parents[2] / "docs" / "sim-samples"
REC_ID = "123e4567-e89b-12d3-a456-426614174000"


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


def recommendation(status: str = "APPROVED") -> dict[str, object]:
    body = {
        "idempotency_key": "rec-executor-test",
        "source_depot_id": "depot-gazipur",
        "destination_station_id": "station-mirpur",
        "route_id": "route-gazipur-mirpur",
        "fuel_type": "DIESEL",
        "quantity": 3000,
    }
    return {
        "id": REC_ID,
        "status": status,
        "idempotency_key": body["idempotency_key"],
        "request_body": body,
        "sim_allocation_id": None,
    }


class MemoryExecutorStore:
    def __init__(self, row: dict[str, object]) -> None:
        self.rows = [row]
        self.updates: list[tuple[str, str, str | None, int | None]] = []

    async def get_recommendations_for_execution(self) -> list[dict[str, object]]:
        return [
            row for row in self.rows if row["status"] in {"APPROVED", "SUBMITTED", "IN_TRANSIT"}
        ]

    async def update_recommendation(
        self,
        recommendation_id: str,
        status: str,
        *,
        failure_reason: str | None = None,
        sim_allocation_id: int | None = None,
    ) -> None:
        self.updates.append((recommendation_id, status, failure_reason, sim_allocation_id))
        self.rows[0]["status"] = status
        self.rows[0]["failure_reason"] = failure_reason
        if sim_allocation_id is not None:
            self.rows[0]["sim_allocation_id"] = sim_allocation_id


class FakeSimClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.bodies: list[dict[str, object]] = []

    async def create_allocation(self, body: dict[str, object]):
        self.bodies.append(body)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return type("Result", (), {"data": outcome})()


@pytest.mark.asyncio
async def test_stale_fresh_read_expires_without_submitting() -> None:
    snapshot = snapshot_fixture()
    snapshot.stale = True
    store = MemoryExecutorStore(recommendation())
    client = FakeSimClient([])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()

    assert client.bodies == []
    assert store.rows[0]["status"] == "EXPIRED"
    assert "stale" in store.rows[0]["failure_reason"]


@pytest.mark.asyncio
async def test_validation_failure_marks_failed_without_post() -> None:
    snapshot = snapshot_fixture()
    snapshot.routes[0].status = "DISRUPTED"
    store = MemoryExecutorStore(recommendation())
    client = FakeSimClient([])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()

    assert client.bodies == []
    assert store.rows[0]["status"] == "FAILED"
    assert "ROUTE_DISRUPTED" in store.rows[0]["failure_reason"]


@pytest.mark.asyncio
async def test_timeout_retry_reuses_exact_stored_body() -> None:
    snapshot = snapshot_fixture()
    store = MemoryExecutorStore(recommendation())
    allocation = Allocation.model_validate(
        {
            "id": 82,
            "idempotency_key": "rec-executor-test",
            "source_depot_id": "depot-gazipur",
            "destination_station_id": "station-mirpur",
            "route_id": "route-gazipur-mirpur",
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
    client = FakeSimClient([SimUnavailable("timeout"), allocation])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()
    assert store.rows[0]["status"] == "SUBMITTED"
    await executor.run_once()

    assert len(client.bodies) == 2
    assert client.bodies[0] == client.bodies[1] == recommendation()["request_body"]
    assert store.rows[0]["status"] == "SUBMITTED"
    assert store.rows[0]["sim_allocation_id"] == 82


@pytest.mark.asyncio
async def test_simulator_409_is_not_retried() -> None:
    snapshot = snapshot_fixture()
    store = MemoryExecutorStore(recommendation())
    client = FakeSimClient([SimBusinessError("ROUTE_DISRUPTED", "closed", 409)])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()

    assert len(client.bodies) == 1
    assert store.rows[0]["status"] == "FAILED"
    assert "ROUTE_DISRUPTED" in store.rows[0]["failure_reason"]


@pytest.mark.asyncio
async def test_existing_key_with_different_body_is_not_recorded_as_success() -> None:
    snapshot = snapshot_fixture()
    existing = Allocation.model_validate(
        {
            "id": 83,
            "idempotency_key": "rec-executor-test",
            "source_depot_id": "depot-gazipur",
            "destination_station_id": "station-mirpur",
            "route_id": "route-gazipur-mirpur",
            "fuel_type": "DIESEL",
            "quantity": 3001,
            "created_tick": snapshot.instance.tick,
            "departure_tick": None,
            "expected_arrival_tick": None,
            "actual_arrival_tick": None,
            "status": "PENDING",
            "failure_reason": None,
        }
    )
    snapshot.allocations = [existing]
    store = MemoryExecutorStore(recommendation())
    client = FakeSimClient([])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()

    assert client.bodies == []
    assert store.rows[0]["status"] == "FAILED"
    assert "IDEMPOTENCY_KEY_MISMATCH" in store.rows[0]["failure_reason"]


@pytest.mark.asyncio
async def test_allocation_lifecycle_transitions_to_arrived() -> None:
    """Verify recommendation follows APPROVED -> SUBMITTED -> IN_TRANSIT -> ARRIVED."""
    snapshot = snapshot_fixture()
    store = MemoryExecutorStore(recommendation("APPROVED"))

    # 1. First execution: SUBMITTED
    alloc_pending = Allocation.model_validate(
        {
            "id": 99,
            "idempotency_key": "rec-executor-test",
            "source_depot_id": "depot-gazipur",
            "destination_station_id": "station-mirpur",
            "route_id": "route-gazipur-mirpur",
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
    client = FakeSimClient([alloc_pending])
    executor = Executor(store, client, lambda: _resolved(snapshot))
    await executor.run_once()
    assert store.rows[0]["status"] == "SUBMITTED"
    assert store.rows[0]["sim_allocation_id"] == 99

    # 2. Next tick: allocation becomes IN_TRANSIT
    alloc_transit = Allocation.model_validate(
        {
            **alloc_pending.model_dump(),
            "status": "IN_TRANSIT",
            "departure_tick": snapshot.instance.tick + 1,
        }
    )
    snapshot.allocations = [alloc_transit]
    await executor.run_once()
    assert store.rows[0]["status"] == "IN_TRANSIT"

    # 3. Allocation arrives: ARRIVED
    alloc_arrived = Allocation.model_validate(
        {
            **alloc_pending.model_dump(),
            "status": "ARRIVED",
            "actual_arrival_tick": snapshot.instance.tick + 3,
        }
    )
    snapshot.allocations = [alloc_arrived]
    await executor.run_once()
    assert store.rows[0]["status"] == "ARRIVED"


@pytest.mark.asyncio
async def test_invalid_stored_body_marks_failed() -> None:
    """Verify malformed stored request body fails cleanly."""
    snapshot = snapshot_fixture()
    row = recommendation()
    row["request_body"] = "not-json"
    store = MemoryExecutorStore(row)
    client = FakeSimClient([])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()
    assert store.rows[0]["status"] == "FAILED"
    assert "stored request is invalid" in store.rows[0]["failure_reason"]


@pytest.mark.asyncio
async def test_idempotency_key_mismatch_in_row_marks_failed() -> None:
    """Verify mismatched row idempotency_key fails without POST."""
    snapshot = snapshot_fixture()
    row = recommendation()
    row["idempotency_key"] = "mismatched-key"
    store = MemoryExecutorStore(row)
    client = FakeSimClient([])
    executor = Executor(store, client, lambda: _resolved(snapshot))

    await executor.run_once()
    assert store.rows[0]["status"] == "FAILED"
    assert "mismatch" in store.rows[0]["failure_reason"]
    assert client.bodies == []


@pytest.mark.asyncio
async def test_snapshot_fetch_exception_is_handled_gracefully() -> None:
    """Verify snapshot fetch exception doesn't crash executor."""

    async def _failing_snapshot():
        raise RuntimeError("network failure during snapshot fetch")

    store = MemoryExecutorStore(recommendation())
    client = FakeSimClient([])
    executor = Executor(store, client, _failing_snapshot)

    # Should not raise exception
    await executor.run_once()
    assert store.rows[0]["status"] == "APPROVED"  # unmodified


async def _resolved(snapshot: Snapshot) -> Snapshot:
    return snapshot
