# FINAL SYSTEM DESIGN — Fuel Supply Intelligence & Resilience Platform

| | |
|---|---|
| **Status** | **FINAL v1.1** — decisions locked; changes only via a change request (§17). v1.1 = after reviewing both colleague repos (§0, §18) |
| **Date** | 2026-11-20 · deadline Thu 2026-11-26 |
| **Supersedes** | `PROPOSED_SYSTEM_DESIGN.md` (full tradeoff tables for D1–D4, D9–D10 live there; this file keeps the decision + the argument in short form) |
| **Companions** | `ARCHITECTURE.md` (diagrams, sequences, schemas) · `CLAUDE.md` (agent rules) · `SKILLS.md` (skill set) · `PIPELINE.md` (next) |

## 0. Changes since the proposal

| Change | Reason |
|---|---|
| **D5: PostgreSQL 16 → PostgreSQL 18** (your request) | Render supports 18 and makes it the default for new databases (changelog Nov 2025); native `uuidv7()`; see §6.2 for what it changes in compose/CI |
| **Added deliverables:** `SKILLS.md`, `CLAUDE.md` | your request |
| **New: explicit time model (§4)** | The simulator can tick at 8–15 ticks/s; ingestion cadence, recommendation validity and demo mode must be defined in two clocks — this was implicit before |
| **Open questions O1–O7 got defaults (§16)** | You did not answer them; defaults are chosen so work is not blocked — override any of them |

### v1.1 — after reading both colleague repos' code and docs (2026-11-20)

| Change | Evidence / reason |
|---|---|
| **O1 decided: adopt `thunderstorm009/fuel_simulator` as the trunk**; harvest selected assets from `IamAsif53/Fuel-Management-System` (§18) | Repo A: ~6.0k Python LOC, 74 unit/scenario + 33 integration tests pass in my sandbox, ruff clean, 82 % coverage **[measured]**, and its architecture already matches this design. Repo B: ~2.6k LOC, "Phase 01 in progress" per its own `PROGRESS.md`; heavier stack (TimescaleDB on PG 16, Redis, 7 services, autopilot mode) that conflicts with D5/D6 and the human-approval guardrail |
| **Keep the repo's `core / api / worker / predictor / web` layout**; module boundaries enforced by import-linter instead of a directory reorganization | A reorg costs a day and buys nothing the contracts don't. 4 contracts tested against the real code: 3 kept, 1 broken (`core.models` imports `httpx`) → F-004 |
| **D7 revised:** asyncpg + plain SQL (`db.sql`), not SQLAlchemy/Alembic | The repo already runs this way; additive idempotent SQL suffices (F-020 only if the schema evolves) |
| **Outbox = the `recommendations` table** (status + unique `idempotency_key` + stored `request_body`, polled by the worker's executor) | Functionally equivalent to a separate outbox for a single worker; `ON CONFLICT (idempotency_key) DO NOTHING` already present |
| **Env var names follow the repo** (`SIM_BASE_URL`, `SIM_*_TIMEOUT_S`, `SIM_BREAKER_*`, `INGEST_INTERVAL_S`, `OPERATOR_TOKEN`, `PREDICTOR_URL`, `CORS_ORIGIN`) | Avoid a rename churn across compose/docs/tests |
| **PostgreSQL 16.8 → 18 is feature F-001** (volume mount changes; local volumes must be recreated once) | D5; repo compose currently pins `postgres:16.8-alpine` **[measured]** |
| **New facts folded in** (§3) and **new safety checks** (§7): finite supply, single-route stations, no refund on failed departure, in-flight headroom | From the other repo's verified-facts doc **[doc]**; each marked "verify" until re-tested on the live simulator |
| **Cloud plan corrected** (§13): the repo's worker is a separate process, so "in-process worker" no longer applies; no-sleep showcase ≈ $27/mo | Repo structure + Render pricing summaries |
| **Rejected from repo B:** autopilot / four-eyes auto-dispatch, Redis, TimescaleDB, LightGBM as the primary model | Guardrail (human review of consequential decisions), D6, D9 (explainable physics-informed model; LightGBM allowed only as a bake-off challenger) |
| **New process docs:** `FEATURE_IMPLEMENTATION_PLAN.md`, `SECURITY_AND_REVIEW_POLICY.md`, `PIPELINE.md`, `BACKLOG.md`, starter kit | Your request |

---

## 1. Mission & scope

An operator platform on top of the organizer's simulator: **observe → detect → predict → decide → simulate → act (human-approved) → monitor → recover**, demonstrable end to end, runnable with `docker compose up`, also deployed (Vercel + Render).

| Tier | Scope |
|---|---|
| **MUST** | Ingestion + validated snapshots · dashboard (inventory, demand, supply, routes, events) · stockout forecast + alerts · recommendations with explanation, constraints, alternatives, confidence · human approve/reject · outbox dispatch to simulator · degraded modes for simulator/predictor/malformed data · health/metrics/logs · k6 load test · acceptance scenarios · compose + CI + deploy |
| **SHOULD** | LP policy + bake-off evidence vs heuristic · what-if endpoint · LLM explanation (template fallback) · Grafana dashboards · decision audit page |
| **COULD** | SSE to browser · replay of a recorded run · RL experiment (only after bake-off harness exists) |
| **WON'T** | Own simulator · real-world integration · auto-dispatch without human · Kubernetes · multi-tenant auth |

---

## 2. Locked decision register

| ID | Decision | Final choice | Core argument (one line) |
|---|---|---|---|
| D1 | Style | Hybrid: modular monolith (`api` + `worker`, one codebase) + separate `predictor` service + SPA | One real process boundary where the brief demands a demonstrable failure (prediction service down); none elsewhere |
| D2 | Language | Python 3.12, FastAPI, async | Numerics (SciPy/numpy), pydantic validation for "reject malformed input", fallback shares the predictor's library |
| D3 | Structure | DDD-lite bounded contexts + Clean/hexagonal layering, **enforced by import-linter on the existing `core/api/worker` layout** | Small fully-specified domain: take contexts and dependency rule, skip aggregates/event sourcing |
| D4 | Bias | Contract-first at edges, behavior-first in core | Persistence follows a stable simulator contract; decision logic is what we iterate |
| **D5** | **Database** | **PostgreSQL 18** | Atomic approve+outbox, unique idempotency, window functions, `SKIP LOCKED`, JSONB; fixed schema ⇒ no need for Mongo's flexibility |
| D6 | Redis | Not in v1; `CachePort` | Every candidate use is covered by Postgres/in-process; add only on measured bottleneck |
| D7 | Data access | **asyncpg + plain SQL (`backend/api/db.sql`)**; additive idempotent changes (F-020 if needed) | Already how the trunk works; no ORM layer to learn in 6 days |
| D8 | Simulator I/O | `httpx` async, strict timeouts, own circuit breaker, `tenacity` retries | Breaker state must be a metric we own |
| D9 | Forecast | Published-profile baseline + online demand-ratio (EWMA/CUSUM) + Monte-Carlo stockout probability | Generating process is published; explainable; milliseconds |
| D10 | Allocation | Rolling-horizon LP (SciPy HiGHS); priority heuristic = baseline **and** fallback | Constraints are linear; heuristic guarantees an answer when LP/predictor fails |
| D11 | GenAI | LLM explains structured output via `LLMPort`; template fallback; never in decision path | Operator comprehension without non-determinism in decisions |
| D12 | Frontend | React 18 + TS + Vite SPA, TanStack Query, Tailwind, Recharts, React Flow | No SSR need; fewer runtimes on Vercel |
| D13 | Browser updates | Short polling 2–5 s with ETag; SSE stretch (direct to API origin) | Robust under Vercel/Render proxying ⚠ unverified for long-lived streams |
| D14 | Auth | Bearer operator token; viewer read-only | Brief asks to restrict sensitive actions, not enterprise IAM |
| D15 | Observability | prometheus-client + structlog JSON + in-app status page; Prometheus/Grafana in compose | Free-tier cloud can't host a metrics stack |
| D16 | Load test | k6 | Scriptable, thresholds usable in CI |
| D17 | Containers | Multi-stage, non-root, healthchecks, compose profiles `core/obs/chaos` | Reproducibility (judges run compose) |
| D18 | Repo | Monorepo, trunk-based, vertical slices | 9 people, 7 days |
| D19 | CI/CD | GitHub Actions; Vercel Git integration; Render deploy hook | Native integrations over custom scripts |
| D20 | Cloud | Vercel (SPA) + Render (api, worker, simulator image, Postgres 18; see §13 for cost/sleep limits) | Your stated plan; compose remains canonical runtime |
| D21 | Testing | 4 levels per feature: unit / integration / E2E / acceptance | Each catches a different class of defect (§12) |
| D22 | Patterns | Repository, Strategy, ACL, Outbox (recommendations table), Circuit Breaker, State Machine, CQRS-lite, DI (not Singleton) | Each answers a concrete requirement (table in §5) |

---

## 3. Facts that constrain us (from the simulator guide / brief)

- Deterministic world; REST is truth; SSE is a hint (no replay; silent drop after 200 queued events) → resync via REST after any gap.
- One domain write: `POST /v1/allocations`; idempotency key in body; same key + same body ⇒ replay; same key + different body ⇒ 409; **cancel does not free a key**.
- Validation order: idempotency → not-found → route mismatch → depot closed → station closed → route disrupted → route capacity → insufficient inventory → dispatch capacity → destination capacity.
- Lifecycle: PENDING → departs next tick → `transit_ticks` (2–4) → ARRIVED; in-transit stock is not inventory.
- Supply arrivals/events are read-only from `/v1` → our only lever is **redistribution**.
- `demand-history` carries `demand`, `served`, `unmet` ⇒ demand is observed even during stockouts (uncensored).
- Faults return `{"error":…}`; domain errors return `{"detail":…}`; `X-Simulator-Stale: true` on stale reads; `/v1/health` and `/admin/*` bypass faults.
- ⚠ Verify day 1 against Swagger: tick length (15 vs 8 min), speed defaults, replay status 200 vs 201 (client accepts both), missing `/v1/events`/`/v1/regions` in the quick list; brief's `POST /simulate` and `POST /advance-time` do not exist in the guide.

**Added in v1.1**
- **[measured by repo A on the live image]** `tick_minutes` = 15, default speed 8 ticks/s, same-key replay returns **201** with the same id, same key + different body ⇒ 409, dispatch budget **resets per tick**, region `demand_factor` multiplies station demand, an event injected with a past `start_tick` is accepted and shows `ACTIVE` after one step (its side effects are not inferred).
- **[doc — repo B's verified-facts file; re-verify]** the scheduled supply **ends at tick 212** (3 recurring waves of 6 arrivals at ticks 64–84, 128–148, 192–212 after the 4 initial arrivals), after which the network is a closed system of roughly 6 days of total demand ⇒ rationing, not just redistribution.
- **[doc; re-verify]** **Tongi** and **Cox's Bazar** have exactly one route each ⇒ no alternative path when that route is disrupted ⇒ isolation risk.
- **[doc; re-verify]** a shipment whose route is disrupted **at departure** becomes `FAILED` with **no refund** (cancel refunds only `PENDING`).
- **[doc; re-verify]** the simulator checks `station.inventory + quantity ≤ capacity` at **creation** only and ignores in-flight shipments ⇒ two valid shipments can overflow the station on arrival.
- **[doc; re-verify]** with no action, the first station stockout occurs around **tick 66** — the do-nothing baseline for acceptance tests.

---

## 4. Time model (new)

Two clocks exist; mixing them is the most likely source of subtle bugs.

| Clock | Unit | Used for |
|---|---|---|
| **Wall clock** | seconds | ingestion cadence, timeouts, retry backoff, breaker windows, UI polling, metrics |
| **Sim clock** | ticks | forecast horizon, transit/lead time, recommendation validity (`valid_until_tick`), demand-history windows |

Rules:
1. **Ingestion is wall-clock-paced (repo default `INGEST_INTERVAL_S=5`), not per-tick.** At 8–15 ticks/s per-tick ingestion is impossible and pointless. Each cycle reads the latest state and **backfills `demand-history`** with `limit = min(2000, 12 × (tick_now − last_ingested_tick) + 12)` (12 rows per tick = 4 stations × 3 fuels).
2. **Recommendations expire in ticks** (`valid_until_tick = created_tick + K`, default K = 4) and are **re-validated against a fresh read before dispatch** (pre-flight, §7).
3. **Demo/test modes:** *deterministic* = simulator `paused`, we drive `/admin/step` (tests, acceptance, bake-off); *live* = simulator `running` at a slow speed chosen for readability (demo). Compose default start mode = `paused`.
4. Tick length is read from `/v1/instance` at runtime — never hard-coded.

---

## 5. Architecture summary

**Units:** `web` (SPA) · `api` (FastAPI, 4 modules) · `worker` (same image; ingest loop, outbox dispatcher, alert evaluator) · `predictor` (FastAPI around the pure `forecast_core` library) · `postgres` · `simulator` (organizer image, untouched). Diagrams: `ARCHITECTURE.md`.

**Modules:** `network` (gateway/ACL, validation, snapshots, freshness) · `forecast` (model, detection, probabilities, confidence) · `decision` (policies, optimizer, what-if, lifecycle, approvals, outbox, dispatch) · `ops` (health, alerts, audit, metrics, narrative) · `shared` kernel. Cross-module access only via ports/read models; enforced by `import-linter` in CI.
**Mapping to the trunk's files (v1.1; boundaries are logical, enforced by `.importlinter`):** `network` ≈ `core/sim_client.py` + `core/models.py` + `worker/ingest.py` + `worker/sse.py` + `api/routes/read.py`; `forecast` ≈ `core/forecast.py` + `core/risk.py` + `worker/forecast_job.py` + `intel/predictor`; `decision` ≈ `core/validator.py` + `core/policies/*` + `core/explain.py` + `worker/recommend_job.py` + `worker/executor.py` + `api/routes/recommendations.py`; `ops` ≈ `core/metrics.py` + health/heartbeats + `observability/`. Physically: `core` = domain/pure logic (plus the simulator client), `api` and `worker` = application + adapters.

**Layers per module:** `adapters/in → application → domain ← adapters/out`; `domain` imports no framework/DB/HTTP. ("MVT" is Django's pattern — not used.)

**Worker placement (as built in the trunk):** `api` reads only the database; `worker` owns all simulator I/O, forecasting, recommendation jobs and approved execution, and serves `/health` + `/metrics`; `predictor` is currently a health/metrics skeleton (F-006). On Render the worker can run as a *web* service because it exposes HTTP; there is no in-process worker mode.

**Pattern → requirement map**

| Pattern | Requirement it serves |
|---|---|
| Repository (per aggregate, query-shaped, in-memory fakes) | Fast unit tests; swappable persistence |
| DI composition root (singleton *lifetime*, not Singleton pattern) | One `httpx` client / engine / breaker registry, no globals, testable |
| Anti-Corruption Layer (`SimulatorGateway`) | "Invalid simulator response → reject + alert" |
| Strategy (`AllocationPolicy`) | "ML unavailable → fallback policy"; bake-off |
| Transactional Outbox + simulator idempotency key | Reliable "approve → allocate" across DB + external system |
| Circuit Breaker + timeout + backoff | "Dependency slow/unavailable → degraded mode" |
| State Machine (recommendation) | Auditable, illegal transitions impossible |
| CQRS-lite read models | Dashboard never waits on the simulator |
| Last-known-good snapshot | Degraded mode with cached state |

---

## 6. Data

### 6.1 PostgreSQL vs MongoDB (final reasoning)
Our correctness story is relational: *one transaction* writes the decision + outbox row; `UNIQUE(idempotency_key)` enforces F3; recommendation → decision → outbox → simulator allocation are foreign-keyed for audit; the simulator schema is fixed, so schema flexibility buys nothing; time-series features need window functions; outbox claiming needs `FOR UPDATE SKIP LOCKED`. Mongo can approximate each, with more ceremony and a replica set for transactions.

### 6.2 What PostgreSQL 18 changes for us
| Item | Impact |
|---|---|
| Docker image `postgres:18` | In 18+ images the data volume mount point is **`/var/lib/postgresql`** (not `/var/lib/postgresql/data`) — use `pgdata:/var/lib/postgresql` in compose ⚠ confirm in the image docs |
| `uuidv7()` built in | Time-ordered primary keys (`DEFAULT uuidv7()`) — index locality, sortable ids, no extension |
| `RETURNING OLD/NEW` | Outbox state transitions can return previous and new state in one statement for audit rows |
| Skip scan on multicolumn B-tree | Helps `(station_id, fuel_type, tick)` lookups that omit the leading column — minor |
| Async I/O | Free read-performance; not a design driver |
| Hosting | Render: PG 18 supported and default for new DBs; **free Postgres still expires 30 days after creation** → paid tier (~$6/mo) for any demo living past the deadline |
| CI / tests | GitHub Actions `services: postgres: image: postgres:18`; testcontainers `postgres:18`; pin `asyncpg`/SQLAlchemy versions and let CI prove compatibility ⚠ |

### 6.3 Core schema (conceptual sketch — **the authoritative schema is `backend/api/db.sql`**: tables `snapshots, forecasts, recommendations, decisions, incidents, integration_events, heartbeats`; in v1.1 the `recommendations` table doubles as the outbox, so the separate `outbox` table below is optional; full ERD in `ARCHITECTURE.md`)
```sql
CREATE TABLE snapshots (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tick int NOT NULL, sim_time timestamptz NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  freshness text NOT NULL CHECK (freshness IN ('LIVE','STALE','INVALID')),
  payload jsonb NOT NULL);
CREATE INDEX snapshots_tick_idx ON snapshots (tick DESC);

CREATE TABLE demand_obs (
  station_id text, fuel_type text, tick int,
  demand_l numeric, served_l numeric, unmet_l numeric,
  PRIMARY KEY (station_id, fuel_type, tick));

CREATE TABLE recommendations (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  snapshot_id uuid NOT NULL REFERENCES snapshots(id),
  created_tick int NOT NULL, valid_until_tick int NOT NULL,
  policy text NOT NULL, status text NOT NULL,
  confidence numeric, review_required boolean NOT NULL DEFAULT false,
  items jsonb NOT NULL, impact jsonb, alternatives jsonb,
  constraints jsonb, explanation jsonb, created_at timestamptz DEFAULT now());

CREATE TABLE decisions (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  recommendation_id uuid NOT NULL REFERENCES recommendations(id),
  actor text NOT NULL, verdict text NOT NULL, reason text,
  decided_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE outbox (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  recommendation_id uuid NOT NULL REFERENCES recommendations(id),
  idempotency_key text NOT NULL UNIQUE,          -- "rec-<uuid>-i<n>", ≤150 chars
  body jsonb NOT NULL, body_hash text NOT NULL,  -- never mutate after insert
  state text NOT NULL DEFAULT 'PENDING',         -- PENDING|SENDING|SENT|FAILED_PERMANENT
  attempts int NOT NULL DEFAULT 0,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  sim_allocation_id int, last_error jsonb);
CREATE INDEX outbox_due_idx ON outbox (next_attempt_at) WHERE state = 'PENDING';
```
Other tables: `forecasts`, `alerts`, `audit_log` (append-only), `service_health_samples`. Retention: prune old snapshots, keep one per N ticks.

### 6.4 Redis
Not in v1. Trigger to add: k6 shows DB reads on `/network/state` as the bottleneck *after* read-model caching. `CachePort` makes the swap local.

---

## 7. Decision engine

**Forecast (D9).** `baseline(t) = daily_profile/ticks_per_day × hour_factor × region_factor × station.demand_multiplier`. Online ratio `r = observed/baseline` (EWMA); **CUSUM** on `r` flags sustained shifts → "demand ×m̂ for N ticks". Residual σ → **Monte-Carlo** (≈500 paths × 48 ticks × 12 series) rolling inventory forward with known in-flight allocations and scheduled/delayed arrivals ⇒ `p_stockout`, `time_to_stockout{P10,P50,P90}`. Detectors also cover inventory-delta mismatch, supply delay, route/depot/station status change, depot dispatch saturation.
*Worked estimate (verify):* Tongi diesel 11,000 L at ≈ 904 L/h daytime ⇒ ≈ 12 h to empty.

**Allocation (D10).** Rolling-horizon LP: variables `x[route, fuel, tick]`; minimize expected unmet demand (criticality-weighted) + small lead-time/transport penalty + over-fill penalty; subject to the simulator's own rules (depot inventory, `dispatch_capacity_per_tick`, `max_shipment`, destination capacity, route/station/depot status); execute first step only; re-solve next cycle. **Heuristic:** rank station-fuel by time-to-stockout, fill toward target cover with greedy feasible shipments; cross-region routes only when the local depot is short. Both policies produce the same `Recommendation` shape.

**Pre-flight (before every dispatch).** Fresh `GET` of depot/station/route → re-run the 9 rules → pass ⇒ POST; fail ⇒ `STALE_RECOMMENDATION` + re-plan, never POST.
**v1.1 pre-flight additions (F-010):** also block when (a) a `SCHEDULED`/`ACTIVE` `route_disruption` event covers the departure tick (a failed departure loses the fuel); (b) destination headroom, **including in-flight shipments arriving by the arrival tick**, would be exceeded; (c) the depot's inventory net of other approved-but-unsent shipments is insufficient.

**Finite supply and isolation (F-009).** Add a *fuel budget* view (`/api/cover`: days of cover per fuel/region, `supply_ends_tick`); after the last scheduled arrival optimize for **fairness** (protect the minimum service level) rather than top-ups; give single-route stations (Tongi, Cox's Bazar) an elevated cover target and an *isolation risk* flag. LP and any LightGBM challenger are judged in the bake-off, never adopted on faith.

**What-if.** Same forward model with a plan injected → "72 % → 19 %" + alternatives. **Honesty metric:** `forecast_abs_error` vs realized served/unmet.

**Bake-off (evidence for "better than rules").** Second simulator instance, same seed, `/admin/reset` + `/admin/step`; compare `service_level`, unmet liters, stockout-ticks per policy; offline/nightly CI only.

**Confidence → review.** From MC dispersion, history length, snapshot freshness. Low ⇒ `review_required` (UI forces opening the evidence panel). **Every** recommendation needs human approval.

**GenAI.** Input = structured JSON; output = schema-validated short explanation / incident summary; cached per `(rec_id, version)`; breaker + template fallback.

---

## 8. Resilience contract

| Failure | Detect | Behavior | Operator sees |
|---|---|---|---|
| Simulator 503 (`unavailable`/`error_rate`) | status, either envelope | timeout 3 s → jittered backoff → breaker opens → serve last-known-good | `STALE @ tick N` banner |
| Simulator latency | per-call timeout | single-flight per resource; lower cadence | latency chip |
| `stale_data` header | `X-Simulator-Stale` | snapshot `STALE`, drop caches, **block approve/dispatch** | `APPROVALS DISABLED` |
| SSE drop / `stream_disconnect` | EOF, 503, >45 s silence | polling continues; reconnect backoff; full REST resync | — |
| Malformed/missing fields | strict pydantic | reject payload, keep previous snapshot, alert | alert |
| Predictor down/slow | timeout + breaker | in-process baseline forecast + heuristic policy | `FALLBACK POLICY ACTIVE` |
| Low confidence | threshold | `review_required` | review banner |
| LLM down | breaker | template explanation | none |
| Postgres down | readiness fail | read-only from in-memory last snapshot; writes → problem+json 503 | degraded banner |
| Dispatch 409 | code | permanent: FAILED + alert + re-plan | failure row |
| Dispatch 503/timeout | transient | outbox retry, same key + same body | pending badge |
| Worker restart / Render cold start (~1 min) | process start | full resync from REST | brief STALE |
| Traffic spike | 429 / k6 limits | rate limit + read-model cache | documented capacity |

Config (env, **names as in the repo's `.env.example`**): `SIM_BASE_URL`, `SIM_CONNECT_TIMEOUT_S=2`, `SIM_READ_TIMEOUT_S=3`, `SIM_MAX_RETRIES=3`, `SIM_BREAKER_FAILURE_THRESHOLD=5`, `SIM_BREAKER_RESET_S=10`, `INGEST_INTERVAL_S=5`, `PREDICTOR_URL`, `OPERATOR_TOKEN`, `CORS_ORIGIN`; new: `REC_VALID_TICKS=4`, `DEV_TOOLS_ENABLED=false`, `ENV=local`.

---

## 9. API surface

**As built in the trunk (confirm against code):** `GET /api/state`, `/api/data-health`, `/api/events`, `/api/risks`, `/api/risks/{station}/{fuel}/trajectory`, `/api/recommendations`, `/api/decisions`, `/api/health`; `POST /api/recommendations/{id}/approve` and `/reject` (operator token); `POST /api/chaos/forecast-fail` (operator token, demo only). Service health: each service's `/health`, plus `/metrics` for Prometheus.
**Planned additions:** `GET /api/cover` (F-009), `POST /api/whatif` (F-015), `GET /api/recommendations/{id}/explanation` (F-016), per-operator identity (F-013). Keep existing routes backward compatible.
Errors: prefer `application/problem+json {type,title,status,detail,code,request_id}` for new routes. Mutations need the operator token; inputs validated; lists paginated; `/api/chaos/*` and any dev passthrough disabled unless `DEV_TOOLS_ENABLED=true`.

---

## 10. Frontend

Feature-sliced layers: `api/` (typed client from OpenAPI, error mapping, query keys) → `features/*` (hooks, pure view-models) → `components/` (design-system primitives) → `app/` (routing, providers, error boundaries, banners). Components never call `fetch`. Screens: Network overview (React Flow topology) · Station/depot detail · Risk & alerts · Recommendation inspector · Decision history · System status. Persistent state banners: `LIVE | STALE | FALLBACK ACTIVE | APPROVALS DISABLED` plus an always-visible **SIMULATED DATA** tag. Visual/motion quality rules and skills: `SKILLS.md`.

---

## 11. Observability

Metrics: HTTP rate/latency histogram/errors; `simulator_requests_total{status}`, `simulator_latency_seconds`, `breaker_state{dep}`, `snapshot_age_seconds`, `forecast_abs_error`, `forecast_confidence`, `shortage_alerts_open`, `recommendations_total{policy}`, `fallback_activations_total`, `outbox_pending`, `dispatch_failures_total{code}`, process CPU/mem. Logs: structlog JSON with `request_id`, `tick`, `rec_id`. Grafana (compose `obs`): Golden signals · Intelligence · Resilience · Dispatch pipeline. Cloud: Render logs + in-app status page.

**Initial targets (validate with k6 on Wed; they are goals, not measurements):** `GET /network/state` p95 ≤ 250 ms at 50 concurrent users (local compose) · `POST /recommendations:compute` p95 ≤ 2 s · error rate < 1 % · breaker opens within 10 s of simulator failure · worker restart → resynced ≤ 60 s.

---

## 12. Testing — four levels per feature

| Level | Scope | Tooling | When |
|---|---|---|---|
| Unit | Pure domain (forecast, CUSUM, constraint checker, optimizer invariants, state machine), FE view-models | pytest + **hypothesis** ("no plan violates the 9 rules"), Vitest + RTL | every commit |
| Integration | Repos vs real Postgres 18; gateway vs **real simulator container** driven by `/admin/step`; predictor contract; outbox idempotency; fault handling via `/admin/faults` | pytest, testcontainers / GH `services`, respx, MSW | every PR |
| E2E | UI → API → DB → simulator journeys | Playwright on compose | PR to main / nightly |
| Acceptance | Brief scenarios as executable Given/When/Then: shipment delay, demand spike, depot constraint, route disruption, combined crisis, predictor down, malformed data, traffic spike | pytest helpers over `/admin/events|faults` | per feature + pre-release |

E2E proves paths work; acceptance proves outcomes (alert raised, rec reduces risk, `service_level` ≥ baseline policy, recovery visible). **Definition of Done:** code + unit + integration green → E2E journey updated → acceptance scenario passes → metrics/logs added → OpenAPI/docs updated → preview deployed → smoke green.

---

## 13. Environments & deployment

**Compose (canonical):** `postgres:18`, `simulator` (`asifmahmoud414/bup-fuel-supply-simulator:1.0.0`, start `paused`), `api`, `worker`, `predictor`, `web` (profile `core`); `prometheus`, `grafana` (`obs`); fault scripts (`chaos`). Healthchecks + `depends_on: service_healthy`. `make up|down|test|smoke|load`.

**Cloud showcase:** Vercel (SPA, `VITE_API_URL` → API with `CORS_ORIGIN` set; no rewrite needed) → Render `api` + `worker` (web service) → Render Postgres 18; simulator image as a Render web service; `deploy/render.yaml` is an **untested** skeleton; managed Postgres needs the schema applied on boot (F-012). Constraints (verified from 2026 pricing sources): free web services sleep after 15 min idle (~1 min wake), 750 free instance-hours per workspace, no free background workers, free Postgres expires in 30 days; Starter ≈ $7/mo per service removes sleep (api + worker + simulator + DB ≈ $27/mo). The hosted simulator's `/admin` is unauthenticated — restrict access or keep the cloud demo non-interactive for faults. Judges run against their own simulator via `SIMULATOR_BASE_URL`.

---

## 14. Security & hygiene
`.env.example` only; secrets in GitHub/Render/Vercel stores; strict pydantic validation; CORS allow-list; operator token (constant-time compare); rate limiting; `pip-audit`/`npm audit`/secret scan in CI; non-root containers; never proxy simulator `/admin` in production; "SIMULATED" labelling; human review preserved.

---

## 15. Plan (re-baselined: the trunk already has Sprints 1–4)

| Day | Focus | Backlog (see `BACKLOG.md`) | Exit criterion |
|---|---|---|---|
| Fri 20 | Foundations and gates | F-001 Postgres 18 · F-002 CI hardening · F-003 dependency bump · F-004 core purity | `make pre-pr-fast` OK; 5 required checks on a PR |
| Sat 21 | Dispatch gate + safety + predictor | F-005 live dispatch acceptance · F-010 pre-flight hardening · start F-006 · start F-018 | approved allocation reaches `ARRIVED`; replay verified |
| Sun 22 | Resilience + scenarios | F-006 · F-007 acceptance suite · F-008 fault matrix · start F-009 | every resilience row demonstrated; do-nothing vs policy numbers |
| Mon 23 | Scarcity, deploy, observability, load | F-009 · F-012 · F-017 · F-011 | deployed stack verified; k6 report |
| Tue 24 | Hardening + stretch | F-013 · F-018 · (F-014/F-015/F-016 only if ahead) | security waivers closed |
| Wed 25 | **Freeze 18:00**; evidence + rehearsal | F-019 | evidence pack; cold-start from clean clone |
| Thu 26 | Deliver | tag `v1.0.0` | demo |

Tracks (scale to actual headcount): backend core · intelligence · frontend · DevOps/observability/load · QA/acceptance · docs/demo/progress reports. Daily update per `statement.md`: done / doing / blockers / next. Process: `FEATURE_IMPLEMENTATION_PLAN.md`; gates: `SECURITY_AND_REVIEW_POLICY.md`; pipeline: `PIPELINE.md`.

---

## 16. Open questions → defaults taken (override any)

| # | Question | Default chosen | Impact if you change it |
|---|---|---|---|
| O1 | Base on `thunderstorm009`'s repo or greenfield? | **DECIDED (v1.1): adopt `thunderstorm009/fuel_simulator` as trunk; harvest from `IamAsif53/Fuel-Management-System` (§18)** — based on cloning both and running A's tests | Reversible only at a high cost after Fri |
| O2 | Python acceptable? | **Yes** (you only changed D5) | Go/Node ≈ +1.5 days |
| O3 | Cloud budget | **Compose is the graded runtime; cloud = free tier + wake-before-demo unless you approve ≈ $27/mo (api, worker, simulator, DB on Starter)** | $27/mo removes sleep; predictor can be a 4th service (+$7) |
| O4 | LLM provider | **Provider-agnostic `LLMPort`; template fallback ships first** | Need an API key by Mon 23 |
| O5 | Is "9 people" all on this product? | **Assume yes; tracks in §15** | Fewer people ⇒ drop SHOULD items |
| O6 | Progress-update audience/cadence | **Daily, in the format above** | — |
| O7 | Mandated tools? | **None assumed** | — |

---

## 17. Risks & change control

| Risk | Mitigation |
|---|---|
| Doc/Swagger mismatch | Day-1 contract probe; tolerant gateway |
| Sim speed vs ingestion | Wall-clock cadence + backfill (§4) |
| Render sleep / free DB expiry | Starter instance, paid DB, or compose as graded runtime |
| 7-day scope | Vertical slices; MUST first; heuristic before LP before LLM |
| 9-person merge conflicts | Module ownership, import-linter, OpenAPI contracts |
| Unknown judge-injected events | Status-driven handling, not scenario-hardcoded |
| LP/LLM instability | Heuristic and template fallbacks always present |

**Change control:** a decision in §2 changes only through a short ADR in `docs/adr/NNN-title.md` (context, options, decision, consequences) + update of this file's register. Nothing else needs ceremony.

---

## 18. Adoption plan: trunk = `thunderstorm009/fuel_simulator`

**What I checked (2026-11-20, cloned both repos):**

| | Repo A `thunderstorm009/fuel_simulator` | Repo B `IamAsif53/Fuel-Management-System` (FSIP) |
|---|---|---|
| Code | 49 Python files / ~5.96k LOC; 20 TS(X) files / ~0.94k LOC | 21 Python files / ~2.57k LOC; 11 TS(X) files / ~0.26k LOC |
| Tests | 74 unit+scenario and 33 integration pass here (1 integration test needs Docker); ruff clean; coverage 82 % | 104 unit tests claimed in its `PROGRESS.md` (not run by me) |
| Progress | Sprints 1–4 implemented; open gate: approved allocation → `ARRIVED` + replay | Phase 00 done, Phase 01 in progress |
| Architecture | api (DB only) / worker (simulator I/O, forecast, recommend, execute) / predictor (skeleton) / web / Prometheus / Grafana — **same as this design** | engine / intelligence / api / frontend / TimescaleDB (PG 16) / Redis / observability |
| Forecast & risk | published-profile baseline + ratio calibration + seeded vectorized Monte Carlo (**same as D9**) | LightGBM multi-step (planned) |
| Dispatch safety | human approval, fresh validation, stable idempotency key, `ON CONFLICT DO NOTHING`; no auto-submit | autopilot mode + four-eyes for > 7,000 L (planned) |
| Process assets | rich `docs/` (simulator contract, sim findings with live evidence, resilience, security, risk register, evidence per sprint) | verified-facts doc, API/UI/module specs, `AGENTS.md`, `PROGRESS.md` discipline, 24 captured fixtures + 26 contract tests |

**Gaps in the trunk to close (all in `BACKLOG.md`):** Postgres 16.8 → 18 (F-001); thin CI — no real-DB/simulator integration, no E2E, no security scans, no deploy verification (F-002); 14 starlette advisories (F-003); `core.models` imports `httpx` (F-004); executor 71 % covered and live gate open (F-005); predictor skeleton (F-006); no acceptance scenarios (F-007); fault matrix incomplete (F-008); no finite-supply logic (F-009); pre-flight lacks event/in-flight checks (F-010); no load test (F-011); no cloud deploy (F-012); single shared token + chaos endpoint exposure (F-013); heuristic only (F-014).

**Harvest from repo B (copy with attribution, as normal PRs):** the verified-facts notes → merge into `docs/sim-findings.md` after re-verification; the captured fixtures and contract tests → compare with `docs/sim-samples/` + `tests/scenarios/`; the LP formulation/digital-twin specs → F-014/F-015; the `AGENTS.md` + `PROGRESS.md` discipline → already folded into `CLAUDE.md` and the feature plan; the UI spec → design reference for F-009/F-017.

**Team logistics:** Repo B's author can keep working in B for specs/fixtures; all new code lands in A through the PR process. Ask A's owner for write access (or fork and PR) and confirm the owner agrees to the branch-protection and review policy.

**Not verified by me:** A's compose stack end-to-end (no Docker here), its live acceptance gate, the web app running in a browser, repo B's tests, and every **[doc]** fact above on the live simulator.
