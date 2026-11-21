# Feature Spec: F-003 Dependency security bump (fastapi/starlette)

## Summary
- Backlog ID: F-003
- Title: Dependency security bump (fastapi/starlette)
- Track: Backend
- Priority: P0

## Changes
1. Upgraded `fastapi` to `>=0.115.14` and added `starlette>=0.46.2` in `requirements.txt` to eliminate the 14 known security advisories in starlette.
2. Removed the temporary `continue-on-error: true` waiver from the CI `security` job in `.github/workflows/ci.yml`.
3. Verified zero breaking API changes in route definitions and handlers.

