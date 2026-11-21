# Feature Spec: F-004 Keep core pure (remove httpx from core.models)

## Summary
- Backlog ID: F-004
- Title: Keep core pure (remove httpx from core.models)
- Track: Backend
- Priority: P1

## Changes
1. Removed `from httpx import Response` from `backend/shared/core/models.py`.
2. Moved `parse_sim_error(response: httpx.Response) -> SimulatorError` from `core.models` to `backend/shared/core/sim_client.py` where HTTP adapter logic resides.
3. Updated unit test import in `tests/unit/test_models.py`.
4. Removed the temporary ignore rule (`core.models -> httpx`) from `.importlinter`.
5. Pure core contract is now 100% strictly enforced across all core modules.

