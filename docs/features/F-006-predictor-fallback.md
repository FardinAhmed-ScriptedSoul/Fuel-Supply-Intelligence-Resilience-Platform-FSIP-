# Feature Spec: F-006 Predictor service with breaker and in-process fallback

## Summary
- Backlog ID: F-006
- Title: Predictor service with breaker and in-process fallback
- Track: Intelligence
- Priority: P0

## Implementation Details
1. Predictor service implemented in `intel/predictor`:
   - Exposes `POST /predict` endpoint consuming Snapshot, station_id, and fuel_type.
   - Computes 24h/96-tick Monte Carlo trajectories and stockout probability.
   - Supports failure simulation via `POST /admin/fail` (token-gated).
   - Dual port support (8103 primary, 8100 forwarder).
2. Remote forecaster & circuit breaker in `backend/worker/forecaster.py`:
   - `RemoteForecaster` connects to `PREDICTOR_URL` with bounded timeouts (1.5s).
   - Tracks consecutive failures: opens circuit after `failure_threshold` (default 5).
   - Half-open probing after `reset_after_s` (10s).
   - Transparent in-process fallback via `InProcessForecaster` using identical core intelligence models (`core.risk.forecast_pair`).
3. Integration and unit tests in `tests/integration/test_predictor.py` and `tests/unit/test_forecast_job.py`.
