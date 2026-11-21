# Feature Spec: F-010 Pre-flight hardening (events, in-flight headroom)

## Summary
- Backlog ID: F-010
- Title: Pre-flight hardening (events, in-flight headroom)
- Track: Backend
- Priority: P0

## Changes
1. Hardened pre-flight validation in `backend/shared/core/validator.py`:
   - Checks active and scheduled `route_disruption` events: blocks dispatch if disruption overlaps with the shipment's departure tick (`snapshot.instance.tick + 1`).
   - Destination headroom computation accounts for in-flight allocations (`PENDING` and `IN_TRANSIT`) destined for the same station and fuel type, preventing overflows upon arrival.
   - Depot inventory availability calculation subtracts existing `PENDING` allocations from on-hand inventory to prevent over-promising fuel before dispatch.
2. Added unit and property verification tests in `tests/unit/test_validator.py`.
