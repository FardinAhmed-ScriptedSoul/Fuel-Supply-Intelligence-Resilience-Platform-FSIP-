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

1. **Review and merge:** PR #17 is open and all current CI checks pass; it still needs the repository's normal review/approval and merge.
2. **Local Compose runtime:** Not verified locally. The C: drive has about 380 MB free after cleaning task-generated npm files, and Docker reports an inconsistent build-cache snapshot. Do not remove unrelated Docker data to work around it. CI's disposable Compose smoke and E2E checks did pass.
3. **Architecture lint:** It could not be installed locally because the host ran out of memory; the GitHub backend architecture check passed.
4. **Scenario benchmark:** Current CLI compares proposed plans only. The older service-level benchmark files do not come from this CLI.
5. **Cloud deployment:** `deploy/render.yaml` is explicitly an untested skeleton. Managed Postgres schema initialization is missing; production URLs, CORS, token, and Vercel variables are not configured.
6. **Presentation:** Demo rehearsal and backup recording have not been completed. Use [the five-minute demo runbook](final-demo-script.md) only after verifying the local live stack.
