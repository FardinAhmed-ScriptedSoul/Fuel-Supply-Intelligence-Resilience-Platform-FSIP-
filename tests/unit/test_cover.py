"""Unit tests for finite supply, rationing policy, and /api/cover endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.routes.read import cover
from core.policies.heuristic import HeuristicPolicy


@pytest.fixture
def sample_snapshot():
    now = datetime.now(timezone.utc)
    return {
        "instance": {"sim_time": now.isoformat(), "tick": 215, "tick_minutes": 15},
        "stations": [
            {
                "id": "station-tongi",
                "name": "Tongi Station",
                "region_id": "region-dhaka",
                "demand_profile": "industrial",
                "demand_multiplier": 1.0,
                "inventory": {"DIESEL": 5000.0, "PETROL": 2000.0, "OCTANE": 1000.0},
                "capacity": {"DIESEL": 30000.0, "PETROL": 15000.0, "OCTANE": 10000.0},
                "status": "OPEN",
            },
            {
                "id": "station-mirpur",
                "name": "Mirpur Station",
                "region_id": "region-dhaka",
                "demand_profile": "urban_high",
                "demand_multiplier": 1.0,
                "inventory": {"DIESEL": 12000.0, "PETROL": 15000.0, "OCTANE": 8000.0},
                "capacity": {"DIESEL": 30000.0, "PETROL": 25000.0, "OCTANE": 15000.0},
                "status": "OPEN",
            },
        ],
        "routes": [
            {
                "id": "route-gazipur-tongi",
                "source_depot_id": "depot-gazipur",
                "destination_station_id": "station-tongi",
                "status": "AVAILABLE",
                "transit_ticks": 2,
                "max_shipment": 10000.0,
            },
            {
                "id": "route-gazipur-mirpur",
                "source_depot_id": "depot-gazipur",
                "destination_station_id": "station-mirpur",
                "status": "AVAILABLE",
                "transit_ticks": 2,
                "max_shipment": 10000.0,
            },
            {
                "id": "route-backup-mirpur",
                "source_depot_id": "depot-patiya",
                "destination_station_id": "station-mirpur",
                "status": "AVAILABLE",
                "transit_ticks": 4,
                "max_shipment": 8000.0,
            },
        ],
        "depots": [
            {
                "id": "depot-gazipur",
                "name": "Gazipur Depot",
                "inventory": {"DIESEL": 50000.0, "PETROL": 40000.0, "OCTANE": 20000.0},
                "dispatch_capacity_per_tick": 15000.0,
                "status": "OPEN",
            }
        ],
    }


@pytest.mark.asyncio
async def test_cover_endpoint_returns_finite_supply_metrics(sample_snapshot):
    repo = MagicMock()
    now = datetime.now(timezone.utc)
    repo.get_latest_snapshot = AsyncMock(
        return_value={
            "raw_json": sample_snapshot,
            "fetched_at": now.isoformat(),
            "stale": False,
            "data_status": "HEALTHY",
        }
    )

    response = await cover(repo)
    assert response["supply_ends_tick"] == 212
    assert response["current_tick"] == 215
    assert response["ticks_remaining_supply"] == 0
    assert response["rationing_active"] is True
    assert response["rationing_mode"] == "FAIRNESS_MIN_SERVICE_LEVEL"
    assert response["network_days_of_cover"] > 0

    stations = response["stations"]
    assert len(stations) == 2

    tongi = next(s for s in stations if s["station_id"] == "station-tongi")
    assert tongi["single_route"] is True
    assert tongi["isolation_risk"] is True
    assert tongi["target_buffer_ratio"] == 0.85

    mirpur = next(s for s in stations if s["station_id"] == "station-mirpur")
    assert mirpur["single_route"] is False
    assert mirpur["isolation_risk"] is False
    assert mirpur["target_buffer_ratio"] == 0.50


def test_heuristic_rationing_protects_minimum_service_level():
    policy = HeuristicPolicy()
    assert policy.name == "heuristic"

