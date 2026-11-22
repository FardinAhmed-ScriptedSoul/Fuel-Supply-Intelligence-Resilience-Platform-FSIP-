# Known issues and verification status

Updated 2026-11-22 for the canonical repository `FardinAhmed-ScriptedSoul/Fuel-Supply-Intelligence-Resilience-Platform-FSIP-`.

Older sprint reports and result files are historical artifacts; some name a different repository and checkout. They are not proof that this canonical checkout currently passes live-runtime, load, or deployment gates.

## Confirmed in this checkout

| Area | Current evidence |
|---|---|
| Backend unit and scenario tests | 120 passed in the current Python 3.13.2 environment. |
| Frontend | Typecheck, 6 tests, and production build passed in the prior verification run. |
| Compose configuration | `docker compose --env-file .env.example config -q` passed. This validates configuration only, not service health. |
| Scenario runner | Read-only in-memory overlays and policy plans. It does not reset, step, or submit to the simulator; historical service-level metrics are not reproduced. |

## Open verification and delivery items

1. **CI repair:** `main` CI failed while collecting tests because four imported helper scripts were absent. Restorations and related fixes are on local branch `fix/restore-ci-helpers`; push and rerun required PR checks.
2. **Compose runtime:** Not verified. The last image pulls failed with host memory allocation and `unexpected EOF` errors. No volumes were deleted and no simulator state was reset.
3. **Architecture lint:** Not run locally because installing `import-linter` failed with a host `MemoryError`.
4. **Scenario benchmark:** Current CLI compares proposed plans only. The older service-level benchmark files do not come from this CLI.
5. **Cloud deployment:** `deploy/render.yaml` is explicitly an untested skeleton. Managed Postgres schema initialization is missing; production URLs, CORS, token, and Vercel variables are not configured.
6. **Presentation:** Demo rehearsal and backup recording have not been completed. Use [the five-minute demo runbook](final-demo-script.md) only after verifying the live stack.
