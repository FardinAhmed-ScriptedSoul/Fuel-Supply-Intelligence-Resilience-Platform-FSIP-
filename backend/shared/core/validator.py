"""Pure allocation validation matching the simulator's documented check order."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.models import AllocationStatus, AllocationTerms, Snapshot


@dataclass(frozen=True)
class Violation:
    code: str
    message: str


def validate(
    recommendation: AllocationTerms,
    snapshot: Snapshot,
    reservations: Sequence[AllocationTerms] = (),
) -> list[Violation]:
    """Return the first simulator-order violation, if any.

    Snapshot allocations only consume dispatch capacity when they were created on
    the current tick, matching the observed per-tick simulator accounting. Planning
    reservations are subtracted from inventory/capacity before emitting each item.
    """
    idempotency_key = getattr(recommendation, "idempotency_key", None)
    if idempotency_key:
        previous = next(
            (
                allocation
                for allocation in snapshot.allocations
                if allocation.idempotency_key == idempotency_key
            ),
            None,
        )
        if previous is not None:
            if _same_terms(previous, recommendation):
                return []
            return [
                Violation(
                    "IDEMPOTENCY_KEY_MISMATCH",
                    "idempotency key is permanently bound to a different allocation body",
                )
            ]
    depot = next((row for row in snapshot.depots if row.id == recommendation.source_depot_id), None)
    station = next(
        (row for row in snapshot.stations if row.id == recommendation.destination_station_id),
        None,
    )
    route = next((row for row in snapshot.routes if row.id == recommendation.route_id), None)
    if depot is None or station is None or route is None:
        return [Violation("NOT_FOUND", "depot, station, or route does not exist")]
    if (
        route.source_depot_id != recommendation.source_depot_id
        or route.destination_station_id != recommendation.destination_station_id
    ):
        return [Violation("ROUTE_MISMATCH", "route endpoints do not match the request")]
    if getattr(depot.status, "value", depot.status) not in {"OPEN", "CONSTRAINED"}:
        return [Violation("DEPOT_CLOSED", "depot is not open for dispatch")]
    if getattr(station.status, "value", station.status) != "OPEN":
        return [Violation("STATION_CLOSED", "station is not open to receive fuel")]
    if getattr(route.status, "value", route.status) != "AVAILABLE":
        return [Violation("ROUTE_DISRUPTED", "route is not available")]

    # F-010: Check scheduled or active route disruption events covering departure tick
    departure_tick = snapshot.instance.tick + 1
    for event in getattr(snapshot, "events", []):
        event_status = (
            getattr(event.status, "value", event.status) if hasattr(event, "status") else ""
        )
        event_type = getattr(event, "type", getattr(event, "event_type", ""))
        event_type = getattr(event_type, "value", event_type)
        parameters = getattr(event, "parameters", {}) or {}
        target_ids = parameters.get("route_ids", [])
        target_id = getattr(event, "target_id", "")
        if target_id and not target_ids:
            target_ids = [target_id]
        if (
            event_type == "route_disruption"
            and route.id in target_ids
            and event_status in {"SCHEDULED", "ACTIVE"}
        ):
            start = getattr(event, "start_tick", snapshot.instance.tick)
            end = getattr(event, "end_tick", None)
            if end is None:
                end = start + getattr(event, "duration_ticks", 0) - 1
            if start <= departure_tick <= end:
                return [
                    Violation(
                        "ROUTE_DISRUPTED",
                        f"route disruption event covers departure tick {departure_tick}",
                    )
                ]

    if recommendation.quantity > route.max_shipment:
        return [Violation("ROUTE_CAPACITY_EXCEEDED", "quantity exceeds route max_shipment")]

    fuel = recommendation.fuel_type
    reserved_inventory = sum(
        row.quantity
        for row in reservations
        if row.source_depot_id == depot.id and row.fuel_type is fuel
    )
    # F-010: Deduct pending allocations from available inventory
    pending_depot = sum(
        allocation.quantity
        for allocation in snapshot.allocations
        if allocation.source_depot_id == depot.id
        and allocation.fuel_type is fuel
        and allocation.status == AllocationStatus.PENDING
    )
    if depot.inventory[fuel] - reserved_inventory - pending_depot < recommendation.quantity:
        return [
            Violation(
                "INSUFFICIENT_INVENTORY",
                "depot has insufficient on-hand inventory net of pending shipments",
            )
        ]

    dispatch_used = sum(
        allocation.quantity
        for allocation in snapshot.allocations
        if allocation.source_depot_id == depot.id
        and allocation.created_tick == snapshot.instance.tick
        and allocation.status in {AllocationStatus.PENDING, AllocationStatus.IN_TRANSIT}
    )
    dispatch_used += sum(row.quantity for row in reservations if row.source_depot_id == depot.id)
    if dispatch_used + recommendation.quantity > depot.dispatch_capacity_per_tick:
        return [
            Violation("DISPATCH_CAPACITY_EXCEEDED", "depot per-tick dispatch capacity exceeded")
        ]

    reserved_destination = sum(
        row.quantity
        for row in reservations
        if row.destination_station_id == station.id and row.fuel_type is fuel
    )
    # F-010: Include in-flight shipments in destination headroom
    in_flight_destination = sum(
        allocation.quantity
        for allocation in snapshot.allocations
        if allocation.destination_station_id == station.id
        and allocation.fuel_type is fuel
        and allocation.status in {AllocationStatus.PENDING, AllocationStatus.IN_TRANSIT}
    )
    if (
        station.inventory[fuel]
        + reserved_destination
        + in_flight_destination
        + recommendation.quantity
        > station.capacity[fuel]
    ):
        return [
            Violation(
                "DESTINATION_CAPACITY_EXCEEDED",
                "station fuel capacity exceeded (including in-flight headroom)",
            )
        ]
    return []


def _same_terms(left: object, right: AllocationTerms) -> bool:
    return all(
        getattr(left, field) == getattr(right, field)
        for field in (
            "source_depot_id",
            "destination_station_id",
            "route_id",
            "fuel_type",
            "quantity",
        )
    )
