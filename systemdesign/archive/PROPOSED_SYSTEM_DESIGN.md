# PROPOSED SYSTEM DESIGN — Fuel Supply Intelligence & Resilience Platform

| | |
|---|---|
| **Status** | PROPOSED v0.1 — for review (not final) |
| **Date** | 2026-11-20 (deadline: Thu 2026-11-26) |
| **Inputs** | `statement.md`, BUP CSE Fest 2026 hackathon brief, BUP Fuel Supply Simulator Integration Guide, `thunderstorm009/fuel_simulator` README |
| **Not yet read** | `IamAsif53/Fuel-Management-System` (fetch was rate-limited) |
| **Next docs** | `FINAL_SYSTEM_DESIGN.md` → `ARCHITECTURE.md` → `SKILL.md` → `PIPELINE.md` |

**How to review:** every choice has an ID (`D1`…`D22`). Reply per ID with **accept / change to X / reject**. Anything marked ⚠ is an assumption I could not verify from the docs.

---

## 1. What we are building (one paragraph)

An operator-facing web platform that sits on top of the organizer's simulator: it **observes** the network (REST truth, SSE as a hint), **detects/predicts** shortages, **recommends** constraint-valid depot→station allocations with explanations, lets a human **approve**, **dispatches** through the simulator's single write endpoint, and keeps **monitoring and recovering** when the simulator, the predictor, or our own services fail.

**Non-goals (v1):** our own simulator; real infrastructure; RL (optional in the brief — only if time remains, and only with a baseline comparison); Kubernetes; multi-tenancy; enterprise auth.

---

## 2. Facts from the docs that drive the design

| # | Fact (source) | Design consequence |
|---|---|---|
| F1 | Simulator is *the world, not the brain*; deterministic for same seed + actions + events (Guide §2) | Replayable tests; policy bake-offs on a second simulator instance; exact-value acceptance tests |
| F2 | REST is truth, SSE is a hint; no `Last-Event-ID`; queue of 200 then silent drop (Guide §6) | Ingestion = poll + refetch-on-event; reconnect → full resync |
| F3 | Only write is `POST /v1/allocations`; idempotency key in body; cancel does **not** free a key (Guide §5.4) | Outbox + deterministic keys; never reuse a key with a changed body |
| F4 | 9 ordered validation rules before accept (Guide §5.2) | Our own pre-flight constraint checker mirrors them; optimizer constraints = same rules |
| F5 | Allocation lifecycle: PENDING → depart next tick → `transit_ticks` (2–4) → arrive (Guide §4.10, §8.4) | Forecast horizon must exceed lead time; "in-transit" never counts as inventory |
| F6 | Supply arrivals and events are **read-only** from `/v1`; our only lever is redistribution (Guide §4.8) | Problem = distribution across 2 depots × 4 stations × 3 fuels, not procurement |
| F7 | Demand profile, hour-of-day factors, region factors are **published** (Guide §8.5–8.6); `demand-history` has `demand`, `served`, `unmet` per tick | Demand is *uncensored* even during stockouts → a physics-informed model beats a generic ML black box and stays explainable |
| F8 | Faults: `latency`, `unavailable`, `error_rate`, `stale_data` (header `X-Simulator-Stale`), `stream_disconnect`; errors use `{"error":…}` for faults vs `{"detail":…}` for domain (Guide §7.10, §9) | Client must parse both envelopes; stale header invalidates cache and blocks dispatch |
| F9 | Brief: prediction service may be killed, malformed fields may be injected, traffic may spike, dependencies may slow (Brief §11–12) | Predictor is a **real separate service** with circuit breaker + fallback — justified by a requirement, not fashion |
| F10 | Brief guardrails: simulated ≠ real, human review of consequential decisions, no hard-coded secrets (Brief §19, §26) | Approval gate is mandatory; "SIMULATED" banner; env-only secrets |
| F11 | Judges run against the **published simulator image** locally; deliverable includes `docker compose up` (Guide §2, Brief §13) | `SIMULATOR_BASE_URL` configurable; **compose is the canonical runtime**, Vercel/Render is the always-on showcase |

⚠ Doc inconsistencies to verify against the live Swagger (`/docs`) on day 1: tick length (15 vs 8 minutes), speed (8 vs 15 ticks/s), idempotent replay status (**201** in §5.4 vs **200** in §9 → client accepts both), `/v1/events` and `/v1/regions` missing from the quick list, brief's `POST /simulate` and `POST /advance-time` **do not exist** in the guide (we build our own what-if model; stepping is `/admin/step`).

---

## 3. Quality attributes (ranked) — how we break ties

1. **Demonstrable end-to-end by Nov 26** (7 days) — simplest thing that satisfies a requirement wins.
2. **Resilience** — every external dependency has a timeout, a failure mode, and a visible degraded state.
3. **Explainability** — every recommendation carries signals, constraints, alternatives, confidence.
4. **Reproducibility** — `docker compose up` from a clean clone.
5. **Observability** — a judge can tell if *our* system is healthy.
6. **Raw performance** — least important: the world is 12 observations per tick. We need *measured* limits, not big numbers.

---

## 4. Decision summary

| ID | Decision | Choice | Runner-up (why not) |
|---|---|---|---|
| D1 | Architecture style | **Hybrid:** modular monolith (API + ingestion worker, one codebase) + separate **predictor service** + SPA frontend | Microservices (ops cost, 7 days); pure monolith (cannot honestly demo "prediction service down") |
| D2 | Backend language | **Python 3.12 + FastAPI (async)** | Go, Node/TS (§7.1) |
| D3 | Internal structure | **DDD-lite bounded contexts as modules + Clean/hexagonal layering** | Full tactical DDD (aggregates/event-sourcing = overhead), plain MVC |
| D4 | Design bias | **Contract-first at the edges, behavior-first at the core** | Pure data-first (anemic domain) |
| D5 | Database | **PostgreSQL 16** | MongoDB (§10.1) |
| D6 | Redis | **Not in v1**; `CachePort` allows adding it | Redis now (extra moving part, no proven need) |
| D7 | ORM/migrations | SQLAlchemy 2.0 async + Alembic | Raw SQL (slower to iterate), Prisma (wrong language) |
| D8 | Simulator I/O | `httpx` async + own circuit breaker + `tenacity` retries | `requests` (blocking) |
| D9 | Forecast | **Published-profile baseline + online demand-ratio estimation + Monte-Carlo stockout probability** | LSTM/GBM (no data volume, not explainable, slower) |
| D10 | Allocation | **Rolling-horizon LP (SciPy HiGHS)** with a **priority heuristic** as baseline *and* fallback | RL (optional; only after baseline bake-off exists) |
| D11 | GenAI | LLM **explains** structured output behind an `LLMPort`; template fallback | LLM in the decision path (unsafe, non-deterministic) |
| D12 | Frontend | **React + TS + Vite SPA**, TanStack Query, Tailwind, Recharts | Next.js (SSR unneeded; adds a server runtime) |
| D13 | Browser updates | **Short polling (2–5 s) in v1**, SSE as stretch | WebSocket (bidirectional unneeded); SSE-first (⚠ Vercel proxy timeouts) |
| D14 | Auth | Bearer operator token (viewer = read-only) | JWT/OAuth (not worth it) |
| D15 | Observability | `prometheus-client` + structlog JSON + in-app status page; Prometheus/Grafana in compose | Full OTel tracing (optional) |
| D16 | Load test | **k6** | Locust (heavier, Python-bound) |
| D17 | Containers | Multi-stage, non-root, healthchecks; compose profiles | — |
| D18 | Repo | Monorepo, trunk-based, short-lived branches, vertical slices | Polyrepo (coordination tax) |
| D19 | CI/CD | GitHub Actions; Vercel Git integration for FE; Render auto-deploy/deploy-hook for BE | Jenkins/GitLab (not needed) |
| D20 | Cloud topology | Vercel (SPA) + Render (API [+ in-process worker] + Postgres) + simulator image as a Render web service | Single VM (violates stated Vercel/Render plan) |
| D21 | Testing | 4 levels: unit / integration / E2E / acceptance, per feature | — |
| D22 | Patterns | Repository, Strategy, ACL, Outbox, Circuit Breaker, State Machine, CQRS-lite, DI (not Singleton) | Event sourcing, Saga (no need) |

---

## 5. System context & architecture

```
                       ┌─────────────────────── Operator (browser) ───────────────────────┐
                       │  React SPA (Vercel / nginx in compose)                           │
                       └───────────────▲──────────────────────────────────────────────────┘
                                       │ REST (+ SSE stretch)       Bearer token for approvals
┌────────────────────────── Participant backend (one codebase) ───────────────────────────┐
│  API process (FastAPI)                       Worker process (same image, other entrypoint)│
│  ┌────────┐ ┌──────────┐ ┌─────────┐ ┌─────┐  ┌──────────────────────────────────────┐   │
│  │ network│ │ forecast │ │ decision│ │ ops │  │ ingest loop · outbox dispatcher ·    │   │
│  │ module │ │ module   │ │ module  │ │ mod │  │ alert evaluator · cache invalidator  │   │
│  └───┬────┘ └────┬─────┘ └────┬────┘ └──┬──┘  └───────────────┬──────────────────────┘   │
└──────┼───────────┼────────────┼─────────┼─────────────────────┼──────────────────────────┘
       │           │ HTTP + breaker        │ metrics/logs        │
       │           ▼                       ▼                     │
       │   ┌───────────────┐        Prometheus → Grafana         │
       │   │ Predictor svc │  (separate service; FastAPI)        │
       │   │ forecast+MC   │  fallback = in-process baseline     │
       │   └───────────────┘                                     │
       ▼                                                         ▼
 ┌───────────┐                                         ┌─────────────────────────┐
 │ PostgreSQL│  snapshots · forecasts · recs ·         │ BUP Fuel Supply         │
 │           │  decisions · outbox · audit · alerts    │ Simulator (published    │
 └───────────┘                                         │ image, :8000)           │
                                                       └─────────────────────────┘
```

**Loop mapping:** Observe (`network`) → Detect/Predict (`forecast`) → Decide/Simulate (`decision`) → Act (outbox → simulator) → Monitor/Recover (`ops` + breakers + fallbacks).

---

## 6. Architecture style (D1) — monolith vs microservices vs hybrid

| Criterion | Pure monolith | Microservices | **Hybrid (chosen)** |
|---|---|---|---|
| Time to first demo | fastest | slowest (infra before features) | fast |
| Parallel work for 9 people | merge conflicts in one tree | clean ownership | **module ownership inside one repo/deploy** |
| Demo "predictor down → fallback" | fake (toggle) | real | **real (one genuine boundary)** |
| Cost on Render | 1 service | 4–6 services | 2–3 services |
| Debuggability in a live demo | best | worst (distributed failures) | good |
| Risk of distributed-system bugs | none | high | low (one network boundary we *want* to fail) |

**Why one extra service, and only one:** the brief names "prediction service becomes unavailable" as a surprise event (F9). A real process boundary makes that failure — and the recovery — demonstrable and measurable. Everything else stays in-process: no network hop where none is needed.

**Deployable units**

| Unit | Contents | Notes |
|---|---|---|
| `api` | FastAPI app; all 4 modules | Stateless; reads only from Postgres, never from the simulator (keeps dashboard fast and degradable) |
| `worker` | Same image, `python -m app.worker` | Ingest loop, outbox dispatcher, alert evaluator. **On Render free/cheap tiers** runs in-process via `RUN_WORKER_IN_PROCESS=true` (Render background workers have no free tier, ~$7/mo) |
| `predictor` | FastAPI wrapping the pure `forecast` library | Same library is imported in-process as the fallback adapter |
| `web` | React SPA | nginx in compose, Vercel in cloud |
| `postgres`, `simulator` | supporting | simulator = organizer's image, unmodified |

**Module (bounded-context) rules**

| Module | Owns | Exposes | May depend on |
|---|---|---|---|
| `network` | Simulator gateway (ACL), validation, snapshots, freshness | `NetworkSnapshot` read model | `shared` |
| `forecast` | Demand model, detection, stockout probability, confidence | `ForecastProvider` port | `shared` |
| `decision` | Policies, optimizer, what-if, recommendation state machine, approvals, outbox, dispatch | use cases | `network` read model, `forecast` port |
| `ops` | Health, alerts, audit, metrics, incident narrative (LLM) | status/alert queries | reads others via ports |
| `shared` | `Tick`, `FuelType`, `Liters`, ids, `Clock`, `Result` | — | nothing |

Rule enforced in CI (import-linter): **no module imports another module's adapters or ORM models.**

---

## 7. Backend design

### 7.1 Language choice (D2): Python/FastAPI vs Go vs Node/TS

| Criterion | Go | Node/TS | **Python/FastAPI** |
|---|---|---|---|
| Optimization / stats libs (LP, numpy, Monte-Carlo) | weak (solver bindings, no numpy) | weak | **native (SciPy HiGHS, numpy)** |
| Input validation of malformed simulator data | manual structs/validators | zod | **pydantic (strict models → "reject + alert")** |
| Forecast + predictor share code | needs 2nd language anyway | needs 2nd language anyway | **one language; library reused as fallback** |
| Raw throughput / memory | **best** | good | adequate (workload is tiny) |
| Concurrency model for poll + SSE + HTTP | **goroutines, excellent** | event loop (CPU-bound MC blocks it) | asyncio fine; MC offloaded to thread/process |
| 7-day velocity | medium | high | **high** |
| Reuse of colleague code (`thunderstorm009` is FastAPI/SQLAlchemy/Postgres) | rewrite | rewrite | **direct reuse** |
| Typed contract to frontend | codegen | **shared types** | OpenAPI → `openapi-typescript` codegen |

**Argument:** the heavy parts of this problem (forecasting, optimization, uncertainty) are numerical and live in Python. Choosing Go/Node would not remove Python — it would add a second language *plus* a network boundary between two things that want to share code. The load-test requirement asks us to *understand* limits, not to beat a benchmark, and the data volume (12 rows/tick) does not stress any of the three.
**What we give up:** Go's throughput and tiny images. **Revisit if:** the k6 run shows the API CPU-bound under dashboard load (then cache read models; Go is still not the first lever).
*If you prefer Go for the API*, the cost is: rewrite the gateway/validators, keep Python predictor, and lose in-process fallback reuse — roughly +1.5 days.

### 7.2 Layering inside each module (D3) — and a correction

"MVT" is Django's Model-View-Template; we are not on Django. Equivalent layering for us:

```
adapters/in   (FastAPI routers, request/response schemas)      ← "controller/view"
application/  (use cases: ComputeRecommendations, ApproveRec…) ← "service"
domain/       (pure: entities, value objects, policies, rules) ← "model" — no I/O, no framework imports
adapters/out  (SQLAlchemy repos, SimulatorClient, PredictorClient, LLMClient)
```
Dependency rule: arrows point inward; `domain` imports nothing from the framework, DB, or HTTP.

**DDD vs Clean — why "DDD-lite + Clean":** the domain is small and fully specified (fixed world, published rules), so full DDD tactics (rich aggregates, domain events, event sourcing) cost more than they return. But it has real invariants worth isolating — *"in-transit is not inventory"*, *"quantity ≤ route.max_shipment"*, *"a recommendation can't be approved after it is stale"*. So: take DDD's **bounded contexts + ubiquitous language**, take Clean's **dependency rule**, skip the rest.

### 7.3 Data-first or behavior-first (D4)

- **Edges are data/contract-first:** DTOs generated from the simulator's OpenAPI; DB schema derived from the contract; every inbound payload passes a strict pydantic model before it touches the domain (anti-corruption layer).
- **Core is behavior-first:** the interesting code is pure functions — `forecast(snapshot, history) → Forecast`, `plan(snapshot, forecast, policy) → Plan`, `check(plan, snapshot) → Violations`. They are written and unit-tested **before** persistence exists.
- **Why:** persistence shape follows simulator data (stable), whereas decision logic is where we iterate. Starting from tables would bake in an anemic domain; starting from behavior everywhere would ignore a contract we do not control.

### 7.4 Pattern catalog (D22)

| Pattern | Where | Why here | What we deliberately don't do |
|---|---|---|---|
| **Repository** | one port per aggregate: `SnapshotRepo`, `RecommendationRepo`, `OutboxRepo`, `AuditRepo` | unit tests use in-memory fakes; swap Postgres ↔ memory; query-shaped methods (`latest_snapshot()`, `open_alerts()`) | no generic `Repository<T>` CRUD wrapper that just re-exposes the ORM |
| **Singleton → DI composition root** | `httpx.AsyncClient`, DB engine, breaker registry, metrics registry created **once** at startup and injected | single *lifetime* without a global; tests inject fakes; no hidden state | no module-level `instance = X()` globals |
| **Anti-Corruption Layer** | `SimulatorGateway` maps `/v1/*` JSON → domain types; classifies errors | isolates doc quirks (200/201, `error` vs `detail`, stale header) | domain never sees raw simulator JSON |
| **Strategy** | `AllocationPolicy` ← `LpPolicy`, `PriorityHeuristicPolicy`, `FallbackPolicy` | "ML unavailable → fallback policy" becomes a config switch; enables bake-off | no policy chosen by `if` chains in handlers |
| **Transactional Outbox** | approve → (`decision` row + `outbox` row) in **one DB transaction**; dispatcher POSTs to simulator | dual-write problem (DB + external system); survives crashes/503s; the simulator's `idempotency_key` makes redelivery safe | no fire-and-forget POST inside the request handler |
| **Circuit Breaker + timeout + backoff** | Simulator client, Predictor client, LLM client | stop hammering a failing dependency; expose breaker state as metric | no unlimited retries; no breaker around Postgres |
| **State Machine** | Recommendation lifecycle (§8.2) | illegal transitions impossible, audit trail free | no status strings mutated ad hoc |
| **CQRS-lite** | write path (decide/approve/dispatch) vs denormalized read models for dashboard | dashboard reads never wait on the simulator | no separate event store |
| **Last-known-good cache (cache-aside)** | latest valid snapshot per entity, in Postgres + in-process | degraded mode when simulator is down | no Redis until measured need |
| **Idempotent consumer** | outbox dispatcher, ingest handler | at-least-once delivery is safe | — |
| **Not used:** Event Sourcing, Saga, Service Mesh | | no requirement they would satisfy | |

**Outbox mechanics (the key one):**
1. `POST /recommendations/{id}/approve` → one transaction: insert `decision(APPROVED)`, update rec → `APPROVED`, insert `outbox(key = "rec-{id}-item-{n}", body_hash)`.
2. Dispatcher (`SELECT … FOR UPDATE SKIP LOCKED`) takes a row → **fresh pre-flight** (re-GET depot/station/route, re-check F4 rules) → `POST /v1/allocations` with the stored key + exact body.
3. 201/200 → store simulator allocation id, mark SUBMITTED. Transient (503/timeout) → retry with backoff (same key, same body = safe, F3). Permanent 409 (`INSUFFICIENT_INVENTORY`, `ROUTE_DISRUPTED`, …) → mark FAILED, raise alert, trigger re-plan.
4. Key rule: **a changed body ⇒ new key; never mutate a stored body.**

---

## 8. Domain model & flows

### 8.1 Core types
`NetworkSnapshot{tick, sim_time, depots, stations, routes, supply_arrivals, events, fetched_at, freshness}` ·
`Forecast{station, fuel, horizon_ticks, expected_demand[], p_stockout, time_to_stockout{p10,p50,p90}, confidence, signals[]}` ·
`Recommendation{id, snapshot_ref, policy, items[Shipment], expected_impact{before,after}, alternatives[], constraints_checked[], confidence, explanation, status}` ·
`Decision{rec_id, actor, verdict, reason, at}` · `OutboxItem{key, body, attempts, state}` · `Alert{type, severity, source, state}`.
**Invariant:** only `inventory` fields count as stock; `SCHEDULED`/`DELAYED` supply and `IN_TRANSIT` shipments are tracked separately.

### 8.2 Recommendation lifecycle
```
PROPOSED ─┬─► APPROVED ─► SUBMITTING ─► SUBMITTED ─► IN_TRANSIT ─► ARRIVED
          ├─► REJECTED                     │                    └─► FAILED
          ├─► EXPIRED   (tick/snapshot moved past validity)
          └─► SUPERSEDED (newer rec for same station/fuel)
```

### 8.3 Ingestion (worker)
`loop every N s: GET /v1/instance → if tick changed (or SSE hint): GET depots/stations/routes/supply-arrivals/events/metrics + demand-history?limit=… → validate (pydantic) → persist snapshot (immutable row) → publish freshness`. Invalid payload ⇒ **reject, keep previous snapshot, raise alert** (Brief §12). `X-Simulator-Stale: true` ⇒ mark snapshot `STALE`, drop caches.

---

## 9. Intelligence design

### 9.1 Forecasting & detection (D9)
- **Baseline demand per (station, fuel, tick):** `profile_daily/ticks_per_day × hour_factor × region_factor × station.demand_multiplier` — all published (F7).
- **Online correction:** ratio `r = observed / baseline` per station-fuel, EWMA-smoothed; **CUSUM** on `r` detects sustained shifts → *demand-spike detected, estimated multiplier m̂* (explainable signal: "Dhaka diesel running ×1.7 for 9 ticks").
- **Uncertainty:** residual σ from history (profile noise is 8–12 %), propagated by **Monte-Carlo** (≈500 paths × 48 ticks × 12 series — milliseconds in numpy).
- **Stockout probability & time-to-stockout:** roll inventory forward with sampled demand, known **in-flight allocations** and **scheduled arrivals** (delayed ones shifted); `p_stockout` = share of paths hitting 0 within horizon; report P10/P50/P90 time.
- **Other detectors:** inventory-delta mismatch (change ≠ served + arrivals → data integrity alert), supply delay (planned tick passed / status `DELAYED`), route/depot/station status changes, depot dispatch-capacity saturation (bottleneck).
- **Worked example (⚠ my estimate, verify on day 1):** Tongi diesel 11,000 L vs 14,000 L/day × 1.55 daytime ⇒ ≈ 904 L/h ⇒ ≈ 12 h to empty → the likeliest first alert on a fresh baseline.
- **Why not deep learning:** no historical corpus beyond the run, the generating process is published, and operators must be able to inspect the signals (Brief §9).

### 9.2 Allocation (D10)
- **Rolling-horizon LP (MPC):** variables `x[route, fuel, tick]`; minimize expected unmet demand (weighted by station criticality) + small transport/lead-time penalty + over-fill penalty; subject to exactly the F4 rules (depot inventory, `dispatch_capacity_per_tick`, `max_shipment`, destination capacity, route/station/depot status). Solve each decision tick, **execute only the first step**, re-solve next tick. Size ≈ 6 routes × 3 fuels × 48 ticks → HiGHS solves in milliseconds.
- **Priority heuristic (baseline + fallback):** rank station-fuel by time-to-stockout, fill to target days-of-cover with greedy feasible shipments, cross-region routes only when same-region depot is short.
- **Evidence (Brief §8 asks "why better than rules"):** run both policies on **a second simulator instance** (same seed, `/admin/reset`, `/admin/step`) and compare `service_level`, unmet liters, stockout-hours → table in the deliverables. Offline/CI only; the demo instance is never touched.
- **RL:** stretch only, and only if the bake-off harness exists.

### 9.3 What-if / expected impact
No simulator `/simulate` exists (§2). `whatif(plan)` re-runs the same forward model with the plan injected → "stockout risk 72 % → 19 %", with alternatives (second-best plans). **Model honesty metric:** `forecast_abs_error` (predicted vs actual served/unmet per tick) exported to Prometheus.

### 9.4 Confidence and human review
`confidence` from MC dispersion, history length, snapshot freshness. Below threshold ⇒ `review_required` (UI forces opening the evidence panel before approve). **All** recommendations need human approval (F10); there is no auto-dispatch in v1.

### 9.5 Generative AI (D11)
LLM receives a structured JSON (signals, constraints, alternatives) and returns a short operator explanation / incident summary; schema-validated output; cached per `(rec_id, version)`; **template fallback** when LLM is down or slow (circuit breaker). Never decides, never writes. Provider key via env only.

---

## 10. Data design

### 10.1 PostgreSQL vs MongoDB (D5)

| Need | Postgres | MongoDB |
|---|---|---|
| Idempotency uniqueness (`UNIQUE(key)`) | native constraint | unique index works, but |
| Approve + outbox atomically | **one ACID txn, trivial** | multi-doc txn possible, replica-set required, clunkier |
| Time-series features (rolling windows, `LAG`, `date_bin`) | **window functions** | aggregation pipeline, more verbose |
| Schema | simulator schema is **fixed and documented** → relational fits | schema flexibility is not a need |
| Flexible explanation payloads | **JSONB** where needed | native |
| `SKIP LOCKED` job claiming for outbox | **yes** | awkward |
| Hosting | Render Postgres / Neon | Atlas free |
| Team familiarity | colleague repo already Postgres | — |

**Argument:** our correctness story (exactly-once-ish dispatch, audit trail, FK from decision → recommendation → snapshot) is relational. Mongo's main advantage — schema freedom — buys nothing against a fixed simulator contract.

**Tables:** `snapshots` (immutable, JSONB payload + extracted columns), `demand_obs`, `forecasts`, `recommendations`, `recommendation_items`, `decisions`, `outbox`, `allocations_ledger`, `alerts`, `audit_log` (append-only), `service_health_samples`. Retention: prune `snapshots` older than N hours except latest per tick bucket.

**Hosting caveat (verified Oct–Aug 2026 sources):** Render **free Postgres expires 30 days after creation** (then a grace period, then deleted) → fine for the deadline, **not** for a long-lived demo; paid Postgres starts ≈ $6/mo. ⚠ Neon free tier is an alternative; I did not verify current limits.

### 10.2 Redis (D6): not in v1
Candidate uses and why each is unnecessary now: **cache of last-known-good state** → Postgres latest-snapshot + in-process TTL; **pub/sub fan-out** → single API process + polling; **job queue** → outbox table with `SKIP LOCKED`; **rate-limit** → per-IP in-memory limiter. Adding Redis = one more container, one more failure mode, extra Render cost. **Trigger to add:** k6 shows DB reads on `/network/state` as the bottleneck after read-model caching. `CachePort` keeps the swap cheap.

---

## 11. Backend API (public, versioned `/api/v1`)

| Group | Endpoints |
|---|---|
| Health | `GET /health/live`, `GET /health/ready` (deps), `GET /metrics` (Prometheus), `GET /api/v1/system/status` (component status, p95, error rate, breaker states, fallback active?) |
| Network | `GET /network/state` (snapshot + freshness + sim banner), `/stations`, `/depots`, `/routes`, `/supply`, `/events` |
| Intelligence | `GET /forecasts?station=&fuel=`, `GET /alerts`, `POST /whatif` |
| Decisions | `POST /recommendations:compute`, `GET /recommendations`, `GET /recommendations/{id}`, `POST /…/{id}/approve`, `POST /…/{id}/reject`, `GET /decisions` (audit), `GET /dispatches` |
| Explain | `GET /recommendations/{id}/explanation` |
| Dev only (`DEV_TOOLS_ENABLED`) | simulator control passthrough (step/run/pause, inject event/fault) for demo rehearsal; **judges use the simulator's own `/admin`**, we never depend on it |

Errors: `application/problem+json` `{type, title, status, detail, code, request_id}`. Approve/reject/compute require operator token (constant-time compare); viewers read only. All list endpoints paginate; all inputs validated.

---

## 12. Frontend design (D12, D13)

**Stack:** React 18, TypeScript, Vite, React Router, **TanStack Query** (server state), Zustand only for tiny UI state, Tailwind (+ shadcn/ui primitives), Recharts, React Flow (network topology: depots → routes → stations, risk-coloured). Types generated from our OpenAPI.

**Why SPA not Next.js:** no SEO/SSR need, token-gated operator tool; Next adds a server runtime and a second "backend" to reason about on Vercel.

**Layers (feature-sliced):**
```
src/
  api/            typed client, error mapping, query keys        ← API layer
  features/       network/ forecast/ recommendations/ alerts/ system/  (each: hooks, view-models, components)
  components/     design-system primitives (Card, StatusPill, Gauge…)   ← presentation
  app/            routing, providers, error boundaries, SIMULATED banner
```
Rule: components never call `fetch`; they use feature hooks. View-models (pure functions) translate API data → display (unit-testable).

**Screens:** (1) **Network overview** — topology + inventory bars + freshness badge; (2) **Station/depot detail** — inventory, demand curve, forecast band, supply; (3) **Risk & alerts** — ranked stockout risk; (4) **Recommendation inspector** — signals, constraints, alternatives, impact 72→19 %, confidence, approve/reject; (5) **Decision history/audit**; (6) **System status** — Brief §16 panel (backend/DB/simulator/predictor/decision engine health, p95, error rate, fallback state).
**Degraded UX:** persistent banner states: `LIVE`, `STALE (simulator unreachable — showing last known @ tick N)`, `FALLBACK POLICY ACTIVE`, `APPROVALS DISABLED (stale data)`. Always-visible **"SIMULATED DATA"** tag (F10).
**Updates:** polling (2–5 s, `ETag`/304); SSE directly to API origin as stretch (⚠ unverified whether Vercel rewrites to external origins buffer/timeout long-lived streams → avoid proxying SSE through Vercel).

---

## 13. Resilience design

| Failure | Detection | Behavior | Recovery / visible state |
|---|---|---|---|
| Simulator `unavailable` / `error_rate` (503 `FAULT_INJECTED`) | status + both envelope shapes | timeout 3 s, jittered backoff, breaker opens after N failures; **serve last-known-good** | breaker half-open probes `/v1/health`; auto-resync; banner `STALE` |
| Simulator `latency` | per-call timeout budget | cut at timeout; reduce poll rate; no pile-up (single-flight per resource) | metric `sim_latency_seconds` |
| `stale_data` | `X-Simulator-Stale: true` | snapshot marked STALE; caches dropped; **block approve/dispatch** | clears when header disappears |
| `stream_disconnect` / SSE drop | 503 / EOF / silence > 45 s | fall back to polling; reconnect with backoff; **full REST resync** (no replay, F2) | metric `sse_reconnects_total` |
| Malformed / missing fields | pydantic strict validation | **reject payload, keep previous snapshot, alert** | alert auto-resolves on next valid fetch |
| Predictor down/slow | client timeout + breaker | **in-process baseline forecast + heuristic policy**; recs flagged "fallback" | breaker closes → `fallback_activations_total` stops |
| Low confidence | threshold | `review_required` | operator inspects |
| LLM down | breaker | template explanation | cosmetic only |
| Postgres down | readiness fail | API serves in-memory last snapshot **read-only**; writes → 503 with problem+json | reconnect pool; outbox resumes |
| Dispatch 409 (domain) | error code | permanent: FAILED + alert + re-plan; never blind-retry | audit entry |
| Dispatch 503/timeout | transient | outbox retry, same key + body | idempotent replay (accept 200 **or** 201) |
| Worker crash/restart (incl. Render cold start ≈ 1 min) | process restart | state in DB; first loop = full resync | no data loss |
| Traffic spike on our API | k6-measured limits | rate limit, cached read models, 429 | documented capacity |

Timeout/retry defaults live in config (`SIM_TIMEOUT_S`, `BREAKER_FAILURES`, `BREAKER_RESET_S`, `RETRY_MAX`) so we can tune per demo.

---

## 14. Observability (D15)

- **Metrics (Prometheus):** HTTP rate/latency histogram/error rate; `simulator_requests_total{status}`, `simulator_latency_seconds`, `breaker_state{dep}`; `snapshot_age_seconds`; `forecast_abs_error`, `forecast_confidence`, `shortage_alerts_open`, `recommendations_total{policy}`, `fallback_activations_total`, `outbox_pending`, `dispatch_failures_total{code}`; process CPU/memory.
- **Logs:** structlog JSON with `request_id`, `tick`, `rec_id`; events for decisions, integration failures, recoveries.
- **Health:** `/health/live` (process), `/health/ready` (DB + simulator + predictor), `/api/v1/system/status` (UI panel).
- **Dashboards (compose `obs` profile):** Grafana provisioned — Golden signals, Intelligence, Resilience (breaker states, fallbacks), Dispatch pipeline.
- **Alerts:** Prometheus rules → shown in-app (no external pager).
- **Cloud:** Render log stream + in-app status page (running Prometheus/Grafana on free tier is impractical); optional Grafana Cloud scrape later.

---

## 15. Security & hygiene
No secrets in git (`.env.example` only; GitHub/Render/Vercel secret stores); validate all inbound data; strict CORS allow-list; operator-token for mutating routes; rate limit; dependency scan (`pip-audit`, `npm audit`) and secret scan in CI; non-root containers; `/admin` of the simulator never proxied in production; "SIMULATED" labelling everywhere.

---

## 16. Containers & environments (D17, D20)

**Compose (canonical, F11):** `postgres`, `simulator` (published image `asifmahmoud414/bup-fuel-supply-simulator:1.0.0`, start mode `paused`), `api`, `worker`, `predictor`, `web` — profile `core`; `prometheus`, `grafana` — profile `obs`; fault/chaos scripts — profile `chaos`. Healthchecks + `depends_on: condition: service_healthy`. One `.env`; `make up | down | test | smoke | load`.

**Cloud showcase (D20):**
```
Browser ─► Vercel (SPA) ──/api rewrite──► Render: API (+worker in-process) ─► Render Postgres
                                              │
                                              └─► Render: simulator image (public Docker Hub image)
```
⚠ Cloud caveats to decide on (§22): free Render web services **sleep after 15 min idle, ~1 min to wake**; 750 free instance-hours per workspace (≈ one always-on service, not two); background workers have no free tier. Starter ($7/mo) removes sleep. The hosted simulator's `/admin` is unauthenticated and would be public → restrict by IP/obscure URL or keep the cloud demo read/visual only. The *graded* runtime is still local compose against the judges' simulator.

---

## 17. Testing strategy (D21) — four levels per feature

| Level | Scope | Tools | Runs |
|---|---|---|---|
| **Unit** | pure domain: forecast math, CUSUM, constraint checker, optimizer invariants, state machine, FE view-models | pytest, **hypothesis** (property tests: "plan never violates F4 rules"), Vitest + RTL | every commit (< 1 min) |
| **Integration** | repos vs real Postgres; `SimulatorGateway` vs **real simulator container** (deterministic via `/admin/step`); predictor HTTP contract; outbox idempotency; fault handling via `/admin/faults` | pytest + testcontainers / GH `services:`, respx for edge cases, MSW (FE) | every PR |
| **E2E** | user journeys through UI + API + DB + simulator: view → alert → inspect → approve → arrives | Playwright on compose stack | PR to main / nightly |
| **Acceptance** | business criteria as executable scenarios, one per brief scenario: shipment delay, demand spike, depot constraint, regional disruption, combined crisis, + predictor-down, malformed data, API traffic spike | pytest (Given/When/Then helpers) driving `/admin/events|faults`, asserting alerts raised, rec produced, `service_level` ≥ baseline policy, recovery shown | before merge of each feature + pre-release |

**Distinction:** E2E proves the *paths work*; acceptance proves the *outcomes meet the requirement* (measured against simulator metrics).
**Definition of Done per feature:** code + unit + integration tests green → E2E journey updated → acceptance scenario passes → metrics/logs added → docs/OpenAPI updated → deployed to Render/Vercel preview → smoke test green.
Pyramid target: ~70 % unit, 20 % integration, ~7 % E2E, ~3 % acceptance (few, expensive, high-value).

---

## 18. CI/CD (summary — full detail in `PIPELINE.md`)

`PR:` lint (ruff, eslint) → type-check (mypy/pyright, tsc) → unit → integration (postgres + simulator services) → build images → import-linter → security scans → preview deploy (Vercel auto-preview).
`main:` + E2E on compose → push images (GHCR) → Render deploy (hook) + Vercel prod → post-deploy `/health/ready` smoke → rollback = Render/Vercel previous deploy.
`nightly:` acceptance suite + k6 load run + policy bake-off, artifacts uploaded as evidence.

---

## 19. Team workflow & 7-day plan

Trunk-based, short-lived branches, PRs with 1 review, **vertical slices** (each slice = UI + API + domain + tests + deploy). Contract first: agree OpenAPI for a slice *before* parallel FE/BE work.

| Day | Goal (slice) | Exit criterion |
|---|---|---|
| Fri 20 | Finalize design docs; scaffold monorepo; compose (sim + db); CI skeleton; verify Swagger quirks | `make up` + green CI |
| Sat 21 | **Slice 1:** ingestion → snapshots → dashboard (read-only) | deployed, live tick visible |
| Sun 22 | **Slice 2:** forecast + detection + alerts + predictor svc | stockout alert on demand-spike inject |
| Mon 23 | **Slice 3:** recommendations + LP/heuristic + approval + outbox dispatch | approve → allocation ARRIVED |
| Tue 24 | **Slice 4:** fault handling, degraded modes, health/metrics/Grafana, LLM explanation | all §13 rows demoed |
| Wed 25 | k6 load test, acceptance suite, bake-off table, README, demo script, freeze | evidence pack complete |
| Thu 26 | Buffer, deliver, final demo rehearsal | — |

**Suggested tracks (9 people, scale down as needed):** Backend core/ingestion (2) · Forecast & optimizer (2) · Frontend (2) · DevOps/observability/load (1) · QA/acceptance (1) · Docs/demo/progress reports (1). **Daily progress update** (required by `statement.md`): done / doing / blockers / next.

---

## 20. Reuse of `thunderstorm009/fuel_simulator`

| Adopt (after code review) | Gap we fill |
|---|---|
| API/worker split, snapshot persistence, validated simulator client, idempotent submission, approval workflow, Prometheus/Grafana provisioning, CI + tests | Real predictor service (currently a skeleton), fault-injection demos, k6 load evidence, LLM explanation, optimizer + bake-off, live ARRIVED acceptance (README says unverified) |

⚠ I have read the README only, not the code. Recommendation: **adopt as the base if a 2-hour review confirms code quality and test health**; otherwise greenfield using its architecture as a reference. Needs your call (O1).

---

## 21. Risks

| Risk | Mitigation |
|---|---|
| Doc/Swagger mismatches | day-1 contract probe; gateway tolerant (200/201, both error envelopes) |
| Render sleep/cold start during demo | Starter instance or keep-alive; compose is the graded runtime |
| 7-day scope | vertical slices; heuristic first, LP second, GenAI last; cut RL, SSE-to-browser |
| 9-person merge chaos | module ownership + import-linter + OpenAPI contracts |
| Optimizer instability | heuristic fallback always available; property tests on constraints |
| Judges inject unknown events | event handling is generic (status-driven), not scenario-hardcoded |
| LLM latency/cost | breaker + cache + template fallback |

---

## 22. Open questions for you (answers change the design)

- **O1** Base on `thunderstorm009`'s repo or greenfield? What does `IamAsif53`'s repo contain (paste README/tree)?
- **O2** Python/FastAPI (D2) acceptable, or does the team need Go/Node? (§7.1 gives the cost of switching.)
- **O3** Cloud budget: is ~$14/mo (API + predictor on Render Starter, no sleep) OK, or free tier + in-process predictor in cloud (real separate predictor only in compose)?
- **O4** Which LLM provider/key can the team use for D11?
- **O5** Is "9 people" the whole batch on one product, or are you working in smaller teams? (affects §19 tracks)
- **O6** Who is the audience for progress updates (mentor/manager) and what cadence (daily)?
- **O7** Any mandated tools from the internship (cloud, repo host, issue tracker)?

---

## 23. What comes next
1. You review → mark each `D#` / `O#`.
2. I produce **`FINAL_SYSTEM_DESIGN.md`** (decisions locked, diagrams final), then **`ARCHITECTURE.md`** (C4 views, sequence diagrams, schemas, API contracts), **`SKILL.md`** (design/testing/motion/etc. skill set and when to use each), **`PIPELINE.md`** (feature → 4-level tests → CI → deploy → rollback, with workflow YAML).
