"""Operator read endpoints. These routes only query the local database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from api.database import ReadRepository
from core.models import FuelType

router = APIRouter(prefix="/api")


def get_repository(request: Request) -> ReadRepository:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="No snapshot repository is available")
    return repository


RepositoryDep = Annotated[ReadRepository, Depends(get_repository)]


def _as_datetime(value: datetime | str) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _data_status(age_seconds: float, stale: bool, stored_status: str) -> str:
    if age_seconds > 120:
        return "OFFLINE"
    if stale or age_seconds >= 15 or stored_status != "HEALTHY":
        return "DEGRADED"
    return "HEALTHY"


async def _latest(repository: ReadRepository) -> tuple[dict[str, Any], datetime, float, str, bool]:
    record = await repository.get_latest_snapshot()
    if record is None:
        raise HTTPException(status_code=503, detail="No snapshot has been stored")
    fetched_at = _as_datetime(record["fetched_at"])
    age_seconds = max(0.0, (datetime.now(timezone.utc) - fetched_at).total_seconds())
    stale = bool(record["stale"])
    status = _data_status(age_seconds, stale, str(record["data_status"]))
    snapshot = dict(record["raw_json"])
    snapshot["fetched_at"] = fetched_at.isoformat()
    snapshot["stale"] = stale
    snapshot["data_status"] = status
    return snapshot, fetched_at, age_seconds, status, stale


@router.get("/state")
async def state(repository: RepositoryDep) -> dict[str, Any]:
    snapshot, fetched_at, age, status, stale = await _latest(repository)
    return {
        "snapshot": snapshot,
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/data-health")
async def data_health(repository: RepositoryDep) -> dict[str, Any]:
    _, fetched_at, age, status, stale = await _latest(repository)
    return {
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/events")
async def events(repository: RepositoryDep) -> dict[str, Any]:
    snapshot, fetched_at, age, status, stale = await _latest(repository)
    incidents = await repository.get_incidents()
    return {
        "events": snapshot.get("events", []),
        "incidents": incidents,
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/metrics-summary")
async def metrics_summary(repository: RepositoryDep) -> dict[str, Any]:
    snapshot, fetched_at, age, status, stale = await _latest(repository)
    return {
        "metrics": snapshot.get("metrics", {}),
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/risks")
async def risks(repository: RepositoryDep) -> dict[str, Any]:
    _, fetched_at, age, status, stale = await _latest(repository)
    forecasts = await repository.get_latest_forecasts()
    return {
        "forecasts": forecasts,
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/risks/{station_id}/{fuel_type}/trajectory")
async def risk_trajectory(
    station_id: str, fuel_type: str, repository: RepositoryDep
) -> dict[str, Any]:
    try:
        normalized_fuel = FuelType(fuel_type.upper()).value
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unknown fuel type") from exc
    _, fetched_at, age, status, stale = await _latest(repository)
    record = await repository.get_forecast_trajectory(station_id, normalized_fuel)
    if record is None:
        raise HTTPException(status_code=404, detail="No forecast exists for this station and fuel")
    return {
        **record,
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }


@router.get("/cover")
async def cover(repository: RepositoryDep) -> dict[str, Any]:
    from core.world import DAILY_LITERS

    snapshot, fetched_at, age, status, stale = await _latest(repository)
    current_tick = snapshot.get("instance", {}).get("tick", 0)
    supply_ends_tick = 212
    ticks_remaining = max(0, supply_ends_tick - current_tick)
    rationing_active = current_tick >= supply_ends_tick or ticks_remaining <= 20

    stations_raw = snapshot.get("stations", [])
    routes_raw = snapshot.get("routes", [])
    depots_raw = snapshot.get("depots", [])

    fuels = ["DIESEL", "PETROL", "OCTANE"]
    network_inventory: dict[str, float] = {f: 0.0 for f in fuels}
    network_daily_demand: dict[str, float] = {f: 0.0 for f in fuels}
    region_inventory: dict[str, dict[str, float]] = {}
    region_daily_demand: dict[str, dict[str, float]] = {}

    station_summaries = []
    for st in stations_raw:
        st_id = st.get("id", "")
        region = st.get("region_id", "")
        profile = st.get("demand_profile", "urban_high")
        multiplier = float(st.get("demand_multiplier", 1.0))
        st_inv = st.get("inventory", {})
        st_cap = st.get("capacity", {})

        if region not in region_inventory:
            region_inventory[region] = {f: 0.0 for f in fuels}
            region_daily_demand[region] = {f: 0.0 for f in fuels}

        routes_to_st = [r for r in routes_raw if r.get("destination_station_id") == st_id]
        is_single_route = len(routes_to_st) == 1

        st_cover: dict[str, float] = {}
        for f in fuels:
            inv = float(st_inv.get(f, 0.0))
            daily = DAILY_LITERS.get(profile, {}).get(f, 5000.0) * multiplier
            days = round(inv / daily, 2) if daily > 0 else 999.0
            st_cover[f] = days

            network_inventory[f] += inv
            network_daily_demand[f] += daily
            region_inventory[region][f] += inv
            region_daily_demand[region][f] += daily

        station_summaries.append({
            "station_id": st_id,
            "name": st.get("name", st_id),
            "region_id": region,
            "demand_profile": profile,
            "demand_multiplier": multiplier,
            "single_route": is_single_route,
            "isolation_risk": is_single_route,
            "target_buffer_ratio": 0.85 if is_single_route else (0.50 if rationing_active else 0.70),
            "inventory": st_inv,
            "capacity": st_cap,
            "days_of_cover": st_cover,
        })

    for d in depots_raw:
        d_inv = d.get("inventory", {})
        for f in fuels:
            network_inventory[f] += float(d_inv.get(f, 0.0))

    fuel_cover: dict[str, Any] = {}
    total_net_inv = sum(network_inventory.values())
    total_net_demand = sum(network_daily_demand.values())
    for f in fuels:
        inv = network_inventory[f]
        dem = network_daily_demand[f]
        fuel_cover[f] = {
            "total_inventory_liters": inv,
            "daily_demand_liters": dem,
            "days_of_cover": round(inv / dem, 2) if dem > 0 else 999.0,
        }

    region_cover: dict[str, Any] = {}
    for region, inv_map in region_inventory.items():
        dem_map = region_daily_demand[region]
        region_cover[region] = {
            f: {
                "inventory_liters": inv_map[f],
                "daily_demand_liters": dem_map[f],
                "days_of_cover": round(inv_map[f] / dem_map[f], 2) if dem_map[f] > 0 else 999.0,
            }
            for f in fuels
        }

    return {
        "supply_ends_tick": supply_ends_tick,
        "current_tick": current_tick,
        "ticks_remaining_supply": ticks_remaining,
        "rationing_active": rationing_active,
        "rationing_mode": "FAIRNESS_MIN_SERVICE_LEVEL" if rationing_active else "STANDARD_COVER",
        "network_days_of_cover": round(total_net_inv / total_net_demand, 2) if total_net_demand > 0 else 999.0,
        "fuel_cover": fuel_cover,
        "region_cover": region_cover,
        "stations": station_summaries,
        "fetched_at": fetched_at.isoformat(),
        "data_age_seconds": age,
        "data_status": status,
        "stale": stale,
        "simulated": True,
    }
