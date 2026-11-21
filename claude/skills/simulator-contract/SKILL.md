---
name: simulator-contract
description: Use when writing, testing or reviewing code that calls the BUP Fuel Supply Simulator (SimulatorGateway/sim_client, ingestion, SSE, allocation dispatch, executor, error handling, fault handling, or admin-driven tests). Covers error envelopes, idempotency, the 9 validation rules in order, stale data, fault types, time model and deterministic testing.
---

# Simulator contract (BUP Fuel Supply Simulator)

Source: the official Integration Guide (`problem/`), plus facts marked **[verified]** (observed on the live image by the trunk repo) or **[verify]** (claimed in a colleague's docs, not yet re-tested). Never invent simulator behavior — test it and record it in `docs/sim-findings.md`.

## Non-negotiables
1. **REST is truth; SSE is a hint.** Refetch via REST after any event, gap or reconnect. No `Last-Event-ID`; the per-subscriber queue (200) drops silently; 15 s silence is normal keepalive.
2. **Two error envelopes.** Faults: `{"error":{"code":"FAULT_INJECTED",…}}` (503). Domain: `{"detail":{"code":"…","message":"…"}}`. `stream_disconnect` nests under `detail`. Pydantic validation errors: `{"detail":[…]}` (422).
3. **Stale data:** header `X-Simulator-Stale: true` on `/v1/*` GETs ⇒ invalidate caches, mark snapshot STALE, **block approve/dispatch**.
4. **Only write:** `POST /v1/allocations` (+ `POST /v1/allocations/{id}/cancel`, PENDING only, refunds depot).
5. **Idempotency (body field `idempotency_key`, 1–150 chars):** same key + same body ⇒ replay of the existing allocation (guide says 201 in §5.4 and 200 in §9 — **accept both**; **[verified]** 201 with the same id); same key + different body ⇒ 409 `IDEMPOTENCY_KEY_MISMATCH`; **cancel does not free a key**.
6. **In-transit and scheduled supply are not inventory.**

## Validation order for `POST /v1/allocations` (first failure wins)
idempotency → `NOT_FOUND` (404) → `ROUTE_MISMATCH` → `DEPOT_CLOSED` → `STATION_CLOSED` → `ROUTE_DISRUPTED` → `ROUTE_CAPACITY_EXCEEDED` (qty > `max_shipment`) → `INSUFFICIENT_INVENTORY` → `DISPATCH_CAPACITY_EXCEEDED` (in-flight + pending from this depot this tick + qty > `dispatch_capacity_per_tick`) → `DESTINATION_CAPACITY_EXCEEDED` (`station.inventory + qty > capacity`) — all 409 except `NOT_FOUND`.
**Permanent** (do not retry the same body): all 409 domain codes. **Transient** (retry same key + body with backoff): 503 `FAULT_INJECTED`, timeouts.

## Lifecycle
`PENDING` (created) → departs next tick → `IN_TRANSIT` → after `transit_ticks` (2–4) → `ARRIVED`; or `FAILED` (route disrupted at departure) / `CANCELLED`. Metrics `allocation_liters` count only IN_TRANSIT + ARRIVED.

## Facts to re-verify before relying on them **[verify]**
- Scheduled supply ends at **tick 212** (3 recurring waves of 6 arrivals; 4 initial arrivals at ticks 12–20).
- **Tongi** and **Cox's Bazar** each have a single route (no reroute when it is disrupted).
- A shipment failing at departure is **not refunded** (cancel refunds only PENDING).
- The destination-capacity rule ignores in-flight shipments ⇒ cumulative arrivals can overflow a station.
- With no action, the first station stockout is around tick 66.

## Faults and events (admin; for tests and rehearsal only — `/admin/*` bypasses faults)
- Faults (`POST /admin/faults`, `duration_seconds` 1–3600, auto-expire; `POST /admin/faults/clear`): `latency{delay_ms}`, `unavailable`, `error_rate{rate}`, `stale_data`, `stream_disconnect`. `/v1/health` is never faulted.
- Events (`POST /admin/events`, `start_tick`, `duration_ticks`, `parameters`): `demand_spike{multiplier,station_ids,region_ids}`, `route_disruption{route_ids}`, `station_outage{station_ids}`, `depot_constraint{depot_ids}`, `shipment_delay{delay_ticks,depot_ids,fuel_types}` (one-shot), `supply_shortfall{factor,…}` (one-shot). Empty filter lists mean "all".
- Time control: `POST /admin/pause | run | toggle | step | reset`.

## Time model
Two clocks: wall seconds (ingestion cadence, timeouts, breaker windows) vs sim ticks (horizons, transit, recommendation validity). Read tick length from `/v1/instance` (docs disagree 8 vs 15 — **[verified]** 15). `demand-history`: always pass `limit` (≤ 2000); 12 rows per tick (4 stations × 3 fuels); rows carry `demand`, `served`, `unmet`.

## Deterministic testing recipe
pause → `/admin/reset` (same seed) → inject events/faults → submit allocations → `/admin/step` N times → assert exact values. Never sleep to wait for ticks. The world: 2 regions, 2 depots (Gazipur, Patiya), 4 stations (Mirpur, Tongi, Karnaphuli, Cox's Bazar), 6 routes, 3 fuels. Full tables in `references/endpoints.md` and the guide §8.

## Pre-flight checklist before any POST (see feature F-010)
fresh GET depot/station/route · the 9 rules · no `SCHEDULED`/`ACTIVE` `route_disruption` covering the departure tick · destination headroom incl. in-flight arrivals · depot inventory net of other approved-unsent shipments · stable idempotency key and immutable stored body.
