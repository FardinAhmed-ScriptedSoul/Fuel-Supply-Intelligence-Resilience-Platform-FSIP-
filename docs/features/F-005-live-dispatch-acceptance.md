# Feature Spec: F-005 Live dispatch acceptance (approve -> ARRIVED, replay)

## Summary
- Backlog ID: F-005
- Title: Live dispatch acceptance (approve -> ARRIVED, replay)
- Track: Backend / QA
- Priority: P0

## Changes
1. Hardened allocation executor lifecycle management:
   - Tracks status transitions through `APPROVED -> SUBMITTED -> IN_TRANSIT -> ARRIVED`.
   - Correctly handles permanent 409 rejections as `FAILED` without redundant retries.
   - Preserves exact key and body on 503 transient retries to maintain idempotency.
   - Enforces snapshot freshness: marks recommendations `EXPIRED` if snapshot is stale or degraded.
2. Verified replay safety:
   - Submitting an identical key and body replays seamlessly without allocating duplicate fuel.
   - Key mismatch or altered body on existing key is safely rejected with `IDEMPOTENCY_KEY_MISMATCH`.
3. Extended executor unit test suite in `tests/unit/test_executor.py` achieving >95% code coverage.
