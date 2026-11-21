# Endpoint reference (from the Integration Guide)

| Method + path | Notes |
|---|---|
| `GET /v1/health` | liveness; bypasses faults |
| `GET /v1/instance` | `tick`, `sim_time`, `tick_minutes`, `status` (PAUSED/RUNNING), `seed`, `scenario_id` |
| `GET /v1/regions` | `demand_factor` (Dhaka 1.00, Chattogram 1.08) |
| `GET /v1/depots[/{id}]` | `status` OPEN/CONSTRAINED, `dispatch_capacity_per_tick`, `capacity`, `inventory` |
| `GET /v1/stations[/{id}]` | `status` OPEN/OUTAGE, `demand_profile`, `demand_multiplier`, `capacity`, `inventory` |
| `GET /v1/routes` | `transit_ticks`, `max_shipment`, `status` AVAILABLE/DISRUPTED |
| `GET /v1/supply-arrivals` | sorted by `planned_tick`; `status` SCHEDULED/DELAYED/ARRIVED |
| `GET /v1/events` | `SCHEDULED/ACTIVE/RESOLVED`, newest first |
| `GET /v1/allocations` | our ledger; `status` PENDING/IN_TRANSIT/ARRIVED/FAILED/CANCELLED |
| `GET /v1/demand-history?station_id=&limit=` | limit clamped 1..2000 (default 200) |
| `GET /v1/metrics` | `served_demand_liters`, `unmet_demand_liters`, `service_level`, `allocation_liters`, `allocation_failures` |
| `POST /v1/allocations` | body: `idempotency_key, source_depot_id, destination_station_id, route_id, fuel_type, quantity` |
| `POST /v1/allocations/{id}/cancel` | PENDING only; 409 `CANNOT_CANCEL` otherwise |
| `GET /v1/stream` | SSE: `simulation.tick`, `allocation.status_changed`, `inventory.updated`, `simulator.notice` |
| `/admin/*` | run, pause, toggle, step, reset, events, faults, faults/clear, audit, dashboard (`/admin`) |

World: depots `depot-gazipur` (dispatch 12,000/tick) and `depot-patiya` (11,000/tick); stations `station-mirpur`, `station-tongi`, `station-karnaphuli`, `station-coxsbazar`; routes `gazipur-mirpur (2t, 7000)`, `gazipur-tongi (2t, 6500)`, `patiya-karnaphuli (2t, 7000)`, `patiya-coxsbazar (3t, 6000)`, `gazipur-karnaphuli (4t, 5000)`, `patiya-mirpur (4t, 5000)`.
