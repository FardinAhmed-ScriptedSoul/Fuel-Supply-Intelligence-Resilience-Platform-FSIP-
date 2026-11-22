# Operations

## Local Compose stack

From the repository root, validate configuration, start the services, then check their health:

```sh
docker compose --env-file .env.example config -q
docker compose --env-file .env.example up -d --build --wait --wait-timeout 300
docker compose ps
bash scripts/smoke.sh
```

Use `.env.example` only for a local demo. If you have a configured `.env`, use `docker compose` (or `--env-file .env`) instead; do not overwrite existing credentials. Stop containers with `docker compose down` to preserve named volumes. `docker compose down -v` deletes local PostgreSQL and Grafana state and must only be used when that data is intentionally disposable.

The six platform services and default URLs are:

| Service | URL |
|---|---|
| Simulator | `http://localhost:8000` |
| API | `http://localhost:8101` |
| Worker | `http://localhost:8102` |
| Predictor | `http://localhost:8103` |
| Frontend | `http://localhost:${FRONTEND_HOST_PORT:-5173}` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |

PostgreSQL is an additional supporting container and is not published on a host port by default. Docker Compose waits for required dependencies' health checks.

## Configuration

Copy `.env.example` to `.env` and set local values. `DATABASE_URL` and `POSTGRES_PASSWORD` must match when the database volume is initialized. Set `OPERATOR_TOKEN` to enable operator decision routes. When choosing a non-default frontend port, set `CORS_ORIGIN` to the corresponding browser origin. Never commit `.env` or credentials; `.env.example` is safe to publish and documents variable names/defaults.

## Useful commands

```sh
docker compose config -q
bash scripts/smoke.sh
docker compose ps
docker compose logs --tail=100 api worker predictor frontend prometheus grafana
```

The simulator can be paused or reset only through its documented administrative controls. A reset changes simulator state; it is not part of ordinary startup or smoke verification. Do not approve a recommendation during routine health checks.

## Recovery notes

- **Simulator unavailable:** inspect worker logs, simulator health, and `/api/data-health`; worker keeps the last accepted snapshot and marks it degraded.
- **Stale data:** inspect `snapshot_age_seconds`, worker ingestion logs, and the simulator stale header. The worker must refetch authoritative REST state before execution.
- **Worker unavailable:** inspect worker health/logs and database availability. API read routes continue to return stored state where available, but no new synchronization or execution occurs.
- **API unavailable:** frontend requests fail; cached data may remain visible with an API-unavailable status.
- **Database unavailable:** API/worker startup or requests may fail health/dependency checks. Preserve the named volume while diagnosing.
- **Frontend or registry build failure:** run `npm --prefix web run build` separately from `docker compose build frontend` to distinguish local bundle errors from image-registry or Docker metadata errors.
- **Recommendation backlog:** inspect worker logs and persisted recommendation/execution status. Only explicitly APPROVED recommendations are eligible for executor handling.

To restore normal operation after a simulator fault, clear the simulator fault using its supported admin endpoint and confirm a subsequent worker refresh restores healthy freshness. Do not treat SSE reconnection as data replay; REST polling/refetch remains the source of truth.

## Deployment strategy and limitations

The verified path is local Docker Compose; GitHub Actions also built and smoke-tested its disposable Compose stack in PR #17, run [45044716397](https://github.com/FardinAhmed-ScriptedSoul/Fuel-Supply-Intelligence-Resilience-Platform-FSIP-/actions/runs/45044716397). The PR is still awaiting review/merge. This does not deploy to production.

The Render/Vercel plan in `deploy/render.yaml` is an untested blueprint. Do not deploy it as-is: managed Postgres does not automatically apply `backend/api/db.sql`. Before a hosted deployment:

1. Review and validate the Render blueprint and provision Postgres, simulator, worker, and API services.
2. Apply `backend/api/db.sql` to the managed database using a controlled one-off migration step before starting API/worker services.
3. Configure `DATABASE_URL`, `SIM_BASE_URL`, `PREDICTOR_URL`, a strong `OPERATOR_TOKEN`, and the exact frontend `CORS_ORIGIN` in the hosting provider; configure Vercel's `VITE_API_URL` to the API URL.
4. Configure GitHub Actions repository variables `PROD_API_URL`, `PROD_WORKER_URL`, and `PROD_WEB_URL` so the post-deploy verification job runs instead of being skipped.
5. After merging to `main`, verify service `/health` endpoints, API `/api/state`, frontend loading, and the deploy-verification workflow before presenting the hosted URL.

Production secrets management and deployment are not configured or verified. The local Compose stack was not verified on the developer machine because its system drive is full and Docker reports an inconsistent build-cache snapshot. See `PROGRESS.md` for current verification and remaining presentation tasks.
