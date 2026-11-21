# BACKLOG — features, branches, acceptance criteria

| | |
|---|---|
| **Status** | v1.0 · 2026-11-20 · lives at `docs/process/BACKLOG.md` |
| **Trunk** | the colleague repo `thunderstorm009/fuel_simulator` (Sprints 1–4 implemented) — see `FINAL_SYSTEM_DESIGN.md` §18 |
| **Rule** | one row = one feature = one branch = one PR. Create it with `make feature ID=F-### NAME=<kebab>` |
| **Evidence legend** | **[measured]** I ran it on 2026-11-20 · **[doc]** stated in a colleague repo's docs, not re-verified by me · **[verify]** confirm against the live simulator before relying on it |

## 1. Priority and order

| ID | Branch | Pri | Track | Depends | Levels |
|---|---|:--:|---|---|---|
| F-001 | `chore/F-001-postgres-18-migration` | P0 | DevOps/DB | – | I, A(smoke) |
| F-002 | `chore/F-002-ci-hardening` | P0 | DevOps | – | pipeline |
| F-003 | `fix/F-003-dependency-security-bump` | P0 | Backend | F-002 | U, I, A(smoke) |
| F-004 | `refactor/F-004-core-purity-httpx` | P1 | Backend | F-002 | U |
| F-005 | `feat/F-005-live-dispatch-acceptance` | P0 | Backend/QA | F-001 | U, I, E, A |
| F-006 | `feat/F-006-predictor-fallback` | P0 | Intelligence | F-002 | U, I, E, A |
| F-007 | `test/F-007-acceptance-scenario-suite` | P0 | QA | F-005 | A |
| F-008 | `feat/F-008-fault-handling-matrix` | P0 | Backend/Frontend | F-005, F-006 | U, I, E, A |
| F-009 | `feat/F-009-finite-supply-rationing` | P1 | Intelligence | F-007 | U, I, A |
| F-010 | `feat/F-010-preflight-hardening` | P0 | Backend | F-005 | U(property), I, A |
| F-011 | `test/F-011-load-test-k6` | P1 | DevOps | F-001 | load |
| F-012 | `chore/F-012-deploy-vercel-render` | P1 | DevOps | F-001, F-003 | I, smoke |
| F-013 | `feat/F-013-operator-identity-hardening` | P1 | Backend | F-002 | U, I, E |
| F-014 | `feat/F-014-lp-policy-bakeoff` | P2 | Intelligence | F-007, F-009 | U, A |
| F-015 | `feat/F-015-what-if-endpoint` | P2 | Intelligence | F-006 | U, I, E |
| F-016 | `feat/F-016-llm-explanations` | P2 | Intelligence | F-006 | U, I |
| F-017 | `feat/F-017-grafana-dashboards` | P1 | DevOps | F-006 | smoke |
| F-018 | `test/F-018-e2e-playwright-journeys` | P1 | QA/Frontend | F-005 | E |
| F-019 | `docs/F-019-demo-runbook-evidence-pack` | P1 | Docs | F-007, F-011 | – |
| F-020 | `chore/F-020-sql-migrations` | P2 | Backend | F-001 | I (only if schema evolves) |

Levels: **U**nit · **I**ntegration · **E**2E · **A**cceptance. P0 = must for a credible demo; P1 = strongly expected by the brief; P2 = stretch, cut first when behind (the colleague repo's own cut order: P2 → polish → extra charts).

## 2. Suggested schedule (re-baselined: the colleague repo already has Sprints 1–4)

| Day | Focus | Features |
|---|---|---|
| **Fri 20** | Foundations and gates | F-001, F-002, F-003 (parallel), F-004 |
| **Sat 21** | Close the dispatch gate; safety hardening; predictor | F-005, F-010, start F-006, start F-018 |
| **Sun 22** | Resilience and scenarios | finish F-006, F-007, F-008, start F-009 |
| **Mon 23** | Scarcity logic, deploy, observability, load | F-009, F-012, F-017, F-011 |
| **Tue 24** | Hardening + stretch | F-013, F-018 finish; F-014/F-015/F-016 only if ahead |
| **Wed 25** | **Freeze 18:00**; evidence + rehearsal | F-019; bug fixes only after 18:00 |
| **Thu 26** | Deliver | tag `v1.0.0`, demo |

---

## 3. Feature details

### F-001 — PostgreSQL 18 migration
- **Why:** decision D5 = PostgreSQL 18; the repo's compose uses `postgres:16.8-alpine` **[measured]**. DB layer coverage is low: `api/database.py` 26 %, `worker/store.py` 29 % **[measured]**.
- **Do:** compose image → `postgres:18-alpine`; data volume mount → `/var/lib/postgresql` (**[verify]** in the 18 image docs; the data directory layout changed); existing 16 volumes are **incompatible** — each developer runs `docker compose down -v` **once** (tell the team first); keep `db.sql` idempotent; add DB-backed integration tests (marker `db`).
- **Acceptance:**
  1. `docker compose up` boots Postgres 18; `SELECT version()` reports 18.x.
  2. Applying `db.sql` twice succeeds (idempotent) on PG 18 — proven by the CI `db-integration` job.
  3. Round-trip tests for `store.py`: insert snapshot, persist forecasts/recommendations, `ON CONFLICT (idempotency_key) DO NOTHING`, status updates.
  4. Coverage of `database.py` and `store.py` ≥ 70 %.

### F-002 — CI hardening (adopt the starter kit)
- **Do:** copy kit workflows/templates/scripts/`.importlinter`/`requirements-ci.txt`; merge `Makefile.additions`; enable branch protection from `.github/branch-protection.json`; fill real handles in `CODEOWNERS`; add pytest markers (`db`, `sim`, `acceptance`, `slow`); bump ruff `target-version` to `py312`; fix the flaky wall-clock test `tests/unit/test_risk.py::test_all_twelve_pairs_complete_under_fifty_milliseconds` (it failed once at 50.2 ms **[measured]**) by asserting a generous bound or a relative benchmark.
- **Acceptance:** (1) a PR with a failing test cannot merge; (2) `make pre-pr-fast` ends `RESULT: OK` on a clean branch; (3) all five required checks appear on a PR; (4) `lint-imports` reports 4 contracts kept (1 with the documented ignore).

### F-003 — Dependency security bump
- **Why:** `pip-audit` reports **14 advisories in `starlette 0.46.2`** (via `fastapi 0.115.12`) **[measured]**; fix versions listed up to 1.3.1.
- **Do:** bump `fastapi` to a release whose `starlette` is patched; re-pin; run everything; remove the `continue-on-error` waiver from the CI `security` job and from policy §5.
- **Acceptance:** `pip-audit -r requirements.txt` exits 0; all four levels green; no API contract change; compose-smoke green.

### F-004 — Keep `core` pure
- **Why:** import-linter found `core.models` importing `httpx.Response` (line 9) **[measured]**, so the "pure core" contract is only kept via a temporary ignore.
- **Do:** move the response-parsing helper into `core/sim_client.py`; delete the `ignore_imports` entry in `.importlinter`.
- **Acceptance:** `lint-imports` keeps all contracts with **no** ignore; existing tests unchanged and green.

### F-005 — Live dispatch acceptance (close the open Sprint-4 gate)
- **Why:** the repo README says an approved allocation reaching `ARRIVED` and an identical body/key replay are **not yet verified**; `executor.py` is at 71 % coverage **[measured]** — this is the safety-critical path.
- **Acceptance:**
  1. Given a PROPOSED recommendation, When the operator approves and the simulator is stepped N ticks (paused, `/admin/step`), Then the allocation reaches `ARRIVED` and recommendation status follows `APPROVED → SUBMITTED → IN_TRANSIT → ARRIVED`.
  2. An identical request (same key, same body) returns the same allocation id (accept 200 or 201).
  3. **Replay after the depot's inventory is exhausted** returns the original allocation (open question in `docs/sim-findings.md` — settle it and record it).
  4. Executor unit tests cover: stale snapshot ⇒ `EXPIRED`; permanent 409 ⇒ `FAILED` + alert (no blind retry); transient 503/timeout ⇒ retry with the **same** key/body; changed body never reuses a key.
  5. Coverage of `executor.py` ≥ 90 %. Evidence saved under `docs/evidence/`.

### F-006 — Predictor service with circuit breaker and in-process fallback
- **Why:** the predictor is only a health/metrics skeleton **[doc + code read]**; the brief lists "prediction service unavailable" as a surprise event.
- **Acceptance:**
  1. Predictor exposes `POST /forecast` using the shared `core` logic; worker calls it via `PREDICTOR_URL` with timeout + breaker.
  2. When the predictor is down/slow, the worker uses the in-process baseline forecast and heuristic policy; `fallback_activations_total` increments; `/health` and the UI show `FALLBACK POLICY ACTIVE`.
  3. After recovery the breaker closes and the banner clears without a restart.
  4. Low confidence ⇒ `review_required` on the recommendation.
  5. `/api/chaos/forecast-fail` (demo) is token-gated and disabled unless `DEV_TOOLS_ENABLED`.

### F-007 — Acceptance scenario suite (brief scenarios)
- **Do:** `tests/acceptance/` with helpers (`reset`, `step`, `inject_event`, `inject_fault`); scenarios mirror the baked-in scenario files **[doc: demand spike Dhaka ×1.8 at tick 8 for 12 ticks; shipment delay Gazipur diesel +8 at tick 6; supply shortfall; combined]**.
- **Acceptance:** for each of {shipment delay, demand spike, depot constraint, route disruption, station outage, combined} the suite proves: alert raised, recommendation produced, recovery visible; and compares **do-nothing vs our policy** on `service_level` and unmet liters, writing `results/*.json`. (Do-nothing baseline first stockout ≈ tick 66 **[doc, verify]**.) Alert lead time before first stockout is asserted.

### F-008 — Fault-handling matrix proven
- **Acceptance:** one test (or recorded run) per row of the resilience contract (`FINAL_SYSTEM_DESIGN.md` §8): simulator 503 / latency / `stale_data` (dispatch blocked) / `stream_disconnect` (polling + resync) / malformed payload (rejected + alert, last good kept) / DB down (read-only degraded) / predictor down / dispatch 409 vs 503. Each shows a **visible** banner or metric and automatic recovery after `/admin/faults/clear`.

### F-009 — Finite supply and rationing
- **Why:** per the colleague's verified-facts doc **[doc, verify]**, scheduled supply ends at **tick 212** (3 recurring waves of 6 arrivals at ticks 64–84, 128–148, 192–212) and total fuel is then ≈ 6 days of demand; **Tongi** and **Cox's Bazar** each have a single route, so they cannot be rerouted.
- **Acceptance:** (1) `GET /api/cover` returns days-of-cover per fuel/region and `supply_ends_tick`; (2) the UI shows the "supply ends in N ticks" marker; (3) after the last arrival the policy optimizes for fairness (protect the minimum service level) instead of naive top-ups; (4) single-route stations get an elevated cover target and an *isolation risk* flag; (5) acceptance scenario shows lower unmet liters than plain heuristic.

### F-010 — Pre-flight hardening
- **Why:** the simulator checks `station.inventory + quantity ≤ capacity` only at creation and ignores in-flight shipments, and a shipment that fails at departure because its route is disrupted is **not refunded** **[doc, verify]**.
- **Acceptance (property tests with hypothesis):** random plans never (a) exceed destination headroom once in-flight arrivals are added, (b) depart on a route with a scheduled/active `route_disruption` covering the departure tick, (c) over-commit a depot net of other approved-but-unsent shipments, (d) violate any of the simulator's 9 rules. Pre-flight failure ⇒ `STALE_RECOMMENDATION` + re-plan, never a POST.

### F-011 — Load test (k6)
- **Do:** flesh out `deploy/k6/load.js`; paths: dashboard reads (`/api/state`, `/api/risks`) and the recommendation read/approve path against the compose stack.
- **Acceptance:** report concurrency, avg/p50/p95/p99, throughput, error rate, CPU/memory (from Prometheus) in `docs/results/load-test.md`; initial targets p95 ≤ 250 ms at 50 VUs and error rate < 1 % — record **measured** values, whatever they are, plus the first bottleneck.

### F-012 — Deploy to Vercel + Render
- **Do:** finish `deploy/render.yaml` (**untested** skeleton), apply the schema on boot (managed Postgres does not run `docker-entrypoint-initdb.d`), set `CORS_ORIGIN` to the Vercel URL, `VITE_API_URL` to the API URL, set repo variables `PROD_API_URL`, `PROD_WORKER_URL`, `PROD_WEB_URL`.
- **Constraints (third-party pricing summaries; check Render's pages):** free web services sleep after 15 min, ~750 free instance-hours per workspace, no free background workers, free Postgres expires after 30 days; Starter ≈ $7/mo per service.
- **Acceptance:** deployed stack answers `/health`, `/api/state` returns live data, the SPA loads and shows data; `deploy-verify` workflow green; rollback rehearsed once.

### F-013 — Operator identity and hardening
- **Acceptance:** per-operator tokens (`OPERATOR_TOKENS=name:token,…`) or equivalent so decisions record a real actor; startup refuses empty/`change-me` token unless `ENV=local`; `/api/chaos/*` disabled unless `DEV_TOOLS_ENABLED=true`; failed-auth rate limit; tests for 401/403.

### F-014 — LP policy and bake-off (stretch)
- **Do:** rolling-horizon LP (SciPy HiGHS) as an `AllocationPolicy`; `scripts/bakeoff.py` runs both policies on a **second simulator instance** (same seed) via `/admin/reset` + `/admin/step`.
- **Acceptance:** table comparing heuristic vs LP on `service_level`, unmet liters, stockout-ticks; LP failure falls back to heuristic; property test: LP output satisfies all 9 rules. (A LightGBM forecaster, proposed in the other colleague repo, may enter only as a *challenger* in the bake-off, never as the sole model.)

### F-015 — What-if endpoint (stretch)
- **Acceptance:** `POST /api/whatif` re-runs the forward model with an edited plan and returns risk before/after + alternatives; the brief's `POST /simulate` does not exist in the simulator guide, so this is our own model; `forecast_abs_error` exported.

### F-016 — LLM explanations (stretch)
- **Acceptance:** `LLMPort` + provider adapter behind a breaker; input is structured JSON only; output schema-validated; cached; template fallback proven by test; hostile-string unit test; the LLM never influences a decision.

### F-017 — Grafana dashboards and alert rules
- **Acceptance:** provisioned dashboards for Golden signals, Intelligence (forecast error/confidence/alerts), Resilience (breaker state, fallbacks, snapshot age), Dispatch (outbox/failures); Prometheus alert rules surface in the in-app status page.

### F-018 — E2E journeys (Playwright)
- **Acceptance:** `web/e2e/` runs in CI against compose: dashboard loads with live data → risk alert visible → open recommendation evidence → approve with token → status progresses; plus a degraded-banner journey. `E2E_BASE_URL` configurable.

### F-019 — Demo runbook and evidence pack
- **Acceptance:** `docs/final-demo-script.md` updated to the 14-step story; evidence folder with test outputs, load-test report, bake-off table, resilience demo recording notes; cold-start rehearsal from a clean clone with `docker compose up`.

### F-020 — SQL migrations (only if needed)
- **Acceptance:** numbered additive SQL files applied idempotently at API start; documented; PG 18 CI proves it. Skip if the schema stays unchanged.
