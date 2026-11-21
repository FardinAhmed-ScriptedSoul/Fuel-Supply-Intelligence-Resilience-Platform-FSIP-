# ARCHITECTURE — Fuel Supply Intelligence & Resilience Platform

| | |
|---|---|
| **Status** | v1.1 — implements `FINAL_SYSTEM_DESIGN.md` v1.1 (decision IDs `D1…D22` refer to it); §2.1 maps the design onto the trunk repo as built; §3.2 corrected |
| **Format** | Mermaid (renders on GitHub, VS Code with a Mermaid extension, and most Markdown viewers) |
| **Reading order** | 1 Context → 2 Containers → 3 Deployment → 4 Components → 5 Use cases → 6 Domain → 7 Lifecycles → 8 Request paths (sequences) → 9 Data → 10 Frontend → 11 Observability → 12 Delivery |

Every section ends with **Decisions** (what was chosen here and why) so a diagram never appears without its rationale.

---

## 1. System context (C4 level 1)

```mermaid
flowchart LR
  op(["Operator<br/>fuel operations center"])
  viewer(["Viewer / Judge<br/>read-only observer"])
  org(["Organizer / Judge<br/>injects events and faults"])

  subgraph platform["Fuel Supply Intelligence & Resilience Platform"]
    sys["Decision-support platform<br/>observe, detect, predict, decide, act, recover"]
  end

  sim[("BUP Fuel Supply Simulator<br/>published Docker image")]
  llm["LLM provider<br/>explanations only"]

  op -->|"views state, approves or rejects"| sys
  viewer -->|"views dashboards and health"| sys
  org -->|"/admin: events, faults, step"| sim
  sys -->|"REST /v1 reads, one write: POST /v1/allocations"| sim
  sim -.->|"SSE /v1/stream (hint only)"| sys
  sys -->|"structured JSON in, text out"| llm
```

**Decisions**
- The simulator is the *only* source of world state and the *only* sink for actions (F1, F3). We never read its database or modify it.
- Organizers talk to the simulator's `/admin` directly; our platform does **not** depend on `/admin` (a dev-only passthrough exists for rehearsal).
- The LLM sits outside the decision path (D11): it receives already-computed structured results.

---

## 2. Containers (C4 level 2)

```mermaid
flowchart TB
  browser(["Operator browser"])

  subgraph web["web (React SPA)"]
    spa["Pages and feature hooks<br/>TanStack Query polling"]
  end

  subgraph backend["backend codebase (one image, two entrypoints)"]
    api["api<br/>FastAPI: network, forecast, decision, ops modules"]
    worker["worker<br/>ingest loop, outbox dispatcher, alert evaluator"]
  end

  predictor["predictor<br/>FastAPI around forecast_core"]
  db[("PostgreSQL 18")]
  sim[("BUP Simulator :8000")]
  llm["LLM provider"]

  subgraph obs["observability (compose profile obs)"]
    prom["Prometheus"]
    graf["Grafana"]
  end

  browser --> spa
  spa -->|"REST /api/v1 + bearer token for mutations"| api
  api --> db
  worker --> db
  worker -->|"GET /v1/*, POST /v1/allocations"| sim
  worker -.->|"SSE hint"| sim
  api -->|"HTTP + circuit breaker"| predictor
  api -.->|"in-process fallback adapter"| api
  api -->|"breaker + template fallback"| llm
  prom -->|"scrape /metrics"| api
  prom --> worker
  prom --> predictor
  graf --> prom
```

**Decisions**
- **D1 hybrid:** `api` and `worker` share a codebase and image (one set of domain code), but run as separate processes in compose so ingestion never blocks request handling.
- **`api` never calls the simulator for reads.** It serves Postgres read models, so the dashboard keeps working when the simulator is down (last-known-good).
- **`predictor` is the one real network boundary** because the brief lists "prediction service unavailable" as a surprise event (F9). The dashed self-arrow is the in-process fallback adapter built from the same `forecast_core` library.
- Mutating calls go through `api` → outbox → `worker`; the browser never talks to the simulator.

### 2.1 As-built mapping (trunk repo `thunderstorm009/fuel_simulator`, v1.1)

The diagrams show the *logical* design. The trunk already implements most of it with this physical layout; boundaries are enforced by import-linter, not by moving directories.

| Logical element | Where it lives in the trunk | Status |
|---|---|---|
| `network` (gateway/ACL, validation, snapshots, freshness) | `backend/shared/core/sim_client.py`, `core/models.py`, `worker/ingest.py`, `worker/sse.py`, `api/routes/read.py` | built; `core.models` imports `httpx` (F-004) |
| `forecast` (baseline, ratio calibration, Monte-Carlo risk) | `core/forecast.py`, `core/risk.py`, `worker/forecast_job.py` | built (same approach as D9) |
| `forecast` as a **separate service** | `intel/predictor` | **skeleton** (health/metrics only) → F-006 |
| `decision` (validator, policies, recommendation, execution) | `core/validator.py`, `core/policies/{base,heuristic}.py`, `core/explain.py`, `worker/recommend_job.py`, `worker/executor.py`, `api/routes/recommendations.py` | built (heuristic only; LP → F-014; pre-flight hardening → F-010) |
| **Outbox** (§8.5) | the `recommendations` table: status + unique `idempotency_key` + stored `request_body`; the worker's executor polls `APPROVED` rows; `ON CONFLICT (idempotency_key) DO NOTHING` | built; live `ARRIVED` gate open → F-005 |
| `ops` (health, metrics, alerts, audit) | `core/metrics.py`, heartbeats/incidents/integration_events tables, `observability/` | partly built (dashboards → F-017) |
| Read-model API | `backend/api` (database only) | built |
| Process split | `api`, `worker` (serves `/health` + `/metrics`), `predictor`, `web`, Prometheus, Grafana, Postgres, simulator = **8 containers** | built; Postgres 16.8 → 18 (F-001) |
| Persistence | asyncpg + `backend/api/db.sql` (tables `snapshots, forecasts, recommendations, decisions, incidents, integration_events, heartbeats`) | built |

---

## 3. Deployment views

### 3.1 Canonical runtime — `docker compose up`

```mermaid
flowchart LR
  subgraph host["Judge or developer machine (docker compose)"]
    direction LR
    web["web :8080 (nginx)"] --> api["api :8001"]
    api --> pg[("postgres:18 :5432<br/>volume pgdata:/var/lib/postgresql")]
    api --> pred["predictor :8002"]
    worker["worker"] --> pg
    worker --> sim[("simulator :8000<br/>start mode paused")]
    prom["prometheus :9090"] --> api
    graf["grafana :3000"] --> prom
  end
```

### 3.2 Cloud showcase — Vercel + Render

```mermaid
flowchart LR
  user(["Browser"]) --> vercel["Vercel<br/>React SPA (VITE_API_URL)"]
  vercel -->|"HTTPS + CORS_ORIGIN"| rapi["Render web service<br/>api (reads database only)"]
  rapi --> rpg[("Render Postgres 18")]
  rwrk["Render web service<br/>worker (serves /health)"] --> rpg
  rwrk --> rsim["Render web service<br/>simulator image from Docker Hub"]
  gh["GitHub Actions deploy-verify"] -.->|"GET /health, /api/state"| rapi
  gh -.->|"Git integration"| vercel
```

**Decisions**
- **Compose is canonical** (F11): judges run our submission against their own published simulator, so `SIM_BASE_URL` is the only coupling.
- **The worker is a separate process in the trunk** (no in-process mode). Because it serves `/health`, it can be deployed as a Render *web* service; Render deploys from the repo itself (`autoDeployTrigger: checksPass`) and GitHub Actions only **verifies** (`deploy-verify`).
- **Cost/sleep reality (third-party 2026 pricing summaries — confirm on Render's pages):** free web services sleep after 15 min idle and share ~750 instance-hours; background workers have no free tier; free Postgres expires after 30 days; Starter ≈ $7/mo per service (api + worker + simulator + DB ≈ $27/mo for no-sleep). Otherwise: wake the stack before the demo and treat compose as the graded runtime.
- The predictor is a separate service in compose; in cloud it can be omitted (the worker falls back to its in-process baseline — which is also the demonstrable degraded mode).
- Postgres volume is mounted at `/var/lib/postgresql` for the 18 image (⚠ confirm against image docs). Managed Postgres does not run `docker-entrypoint-initdb.d`, so schema must be applied on boot (F-012).
- `/admin` of a publicly hosted simulator is unauthenticated: restrict by obscure URL/IP or keep cloud fault-injection off.

---

## 4. Backend components

### 4.1 Module and layer map

```mermaid
flowchart TB
  subgraph shared["shared kernel"]
    sk["Tick, FuelType, Liters, ids, Clock, Result"]
  end

  subgraph network["network module"]
    n_in["in: query routers"] --> n_app["app: IngestSnapshot, GetNetworkState"]
    n_app --> n_dom["domain: NetworkSnapshot, Freshness, validators"]
    n_app --> n_out["out: SimulatorGateway (ACL), SnapshotRepo"]
  end

  subgraph forecast["forecast module"]
    f_app["app: ComputeForecast, DetectAnomalies"] --> f_dom["domain: baseline, CUSUM, MonteCarlo, confidence"]
    f_out["out: PredictorHttpClient, InProcessPredictor"] 
  end

  subgraph decision["decision module"]
    d_in["in: recommendation routers"] --> d_app["app: Compute, Approve, Reject, Dispatch, WhatIf"]
    d_app --> d_dom["domain: AllocationPolicy (LP, heuristic), ConstraintChecker, Recommendation state machine"]
    d_app --> d_out["out: RecommendationRepo, OutboxRepo, SimulatorDispatchGateway"]
  end

  subgraph ops["ops module"]
    o_app["app: HealthStatus, AlertEvaluator, Narrate"] --> o_out["out: MetricsRegistry, AuditRepo, LLMClient"]
  end

  d_app -->|"reads NetworkSnapshot read model"| n_app
  d_app -->|"ForecastProvider port"| f_app
  f_app --> f_out
  o_app -->|"reads via ports"| n_app
  o_app --> d_app
  n_dom --> sk
  f_dom --> sk
  d_dom --> sk
```

### 4.2 Dependency rules (enforced by `import-linter`)

| Rule | Why |
|---|---|
| `domain` imports nothing from FastAPI, SQLAlchemy, httpx | Pure, fast unit tests; hypothesis property tests |
| `application` depends on `domain` and **ports** only | Use cases are testable with in-memory fakes |
| `adapters` implement ports; only the composition root wires them | No hidden globals (singleton *lifetime*, not Singleton pattern) |
| A module may use another module only through its published port or read model | Keeps ownership boundaries for a 9-person team |

**Decisions**
- **DDD-lite + Clean (D3):** four bounded contexts with a shared kernel; no aggregates-with-events, no event sourcing — the domain is small and fully specified.
- **Behavior-first core (D4):** `domain` functions are written and tested before any table exists; adapters are generated from the simulator contract.
- **Strategy for policies (D10/D22):** `AllocationPolicy` has `LpPolicy`, `PriorityHeuristicPolicy`, `FallbackPolicy`; the choice is configuration, not control flow.

---

## 5. Use cases

### 5.1 Actors and use cases

```mermaid
flowchart LR
  op(["Operator"])
  vw(["Viewer"])
  org(["Organizer"])
  sim(["Simulator"])
  llm(["LLM provider"])

  subgraph sysb["Platform"]
    uc1(["UC1 View network state"])
    uc2(["UC2 See shortage risk and alerts"])
    uc3(["UC3 Inspect forecast signals"])
    uc4(["UC4 Compute recommendation"])
    uc5(["UC5 Inspect recommendation evidence"])
    uc6(["UC6 What-if a plan"])
    uc7(["UC7 Approve or reject"])
    uc8(["UC8 Track dispatch and arrival"])
    uc9(["UC9 Review decision history"])
    uc10(["UC10 Check system health"])
    uc11(["UC11 Operate in degraded mode"])
  end

  vw --> uc1
  vw --> uc2
  vw --> uc10
  op --> uc1
  op --> uc2
  op --> uc3
  op --> uc4
  op --> uc5
  op --> uc6
  op --> uc7
  op --> uc8
  op --> uc9
  op --> uc10
  uc4 -.->|"include"| uc5
  uc7 -.->|"include"| uc8
  uc11 -.->|"extends UC1, UC4, UC7"| uc1
  org -->|"injects events and faults"| sim
  uc8 --> sim
  uc1 --> sim
  uc5 --> llm
```

### 5.2 Use-case table

| ID | Use case | Actor | Precondition | Main flow | Alternate / failure |
|---|---|---|---|---|---|
| UC1 | View network state | Operator, Viewer | ≥ 1 valid snapshot | SPA polls `/network/state` | Simulator down → last-known-good + `STALE` banner |
| UC2 | See shortage risk | Operator, Viewer | forecasts computed | Risk list ranked by `p_stockout`, time-to-stockout | Predictor down → fallback forecast, flagged |
| UC3 | Inspect forecast | Operator | UC2 | Demand curve vs baseline, CUSUM signal, uncertainty band | — |
| UC4 | Compute recommendation | Operator | fresh snapshot | Policy runs → items, impact, alternatives, constraints, confidence | LP fails → heuristic; low confidence → `review_required` |
| UC5 | Inspect evidence | Operator | recommendation exists | Open panel: signals, constraints, alternatives, narrative | LLM down → template narrative |
| UC6 | What-if | Operator | snapshot | Re-run forward model with edited plan → risk before/after | — |
| UC7 | Approve / reject | Operator (token) | status PROPOSED, snapshot LIVE | Decision + outbox in one transaction | Stale data → approvals disabled; expired → re-plan |
| UC8 | Track dispatch | Operator | APPROVED | Outbox → simulator → IN_TRANSIT → ARRIVED | 409 permanent → FAILED + re-plan; 503 → retry |
| UC9 | Decision history | Operator | — | Audit list with who/when/why | — |
| UC10 | System health | Operator, Viewer | — | Component status, p95, error rate, breaker states | — |
| UC11 | Degraded operation | Operator | any dependency failure | Banners explain what is limited | See resilience matrix |

**Decisions**
- Mutating actions (UC4, UC6 compute, UC7) require the operator token; viewers are read-only (D14).
- UC7 is the *only* path to a simulator write — human review of consequential decisions is structural, not a convention (F10).

---

## 6. Domain model

```mermaid
classDiagram
  class NetworkSnapshot {
    +uuid id
    +int tick
    +datetime simTime
    +Freshness freshness
    +Depot[] depots
    +Station[] stations
    +Route[] routes
    +SupplyArrival[] supply
    +Event[] events
  }
  class Forecast {
    +StationId station
    +FuelType fuel
    +int horizonTicks
    +float pStockout
    +TimeToStockout tts
    +float confidence
    +Signal[] signals
  }
  class Recommendation {
    +uuid id
    +int createdTick
    +int validUntilTick
    +string policy
    +Status status
    +float confidence
    +bool reviewRequired
    +Shipment[] items
    +Impact impact
    +Alternative[] alternatives
    +Constraint[] constraintsChecked
  }
  class Shipment {
    +DepotId source
    +StationId destination
    +RouteId route
    +FuelType fuel
    +float quantity
  }
  class Decision {
    +uuid id
    +string actor
    +Verdict verdict
    +string reason
    +datetime decidedAt
  }
  class OutboxItem {
    +string idempotencyKey
    +json body
    +string bodyHash
    +State state
    +int attempts
    +int simAllocationId
  }
  class Alert {
    +string type
    +Severity severity
    +string source
    +State state
  }
  NetworkSnapshot "1" --> "many" Forecast : basis for
  NetworkSnapshot "1" --> "many" Recommendation : derived from
  Recommendation "1" *-- "many" Shipment
  Recommendation "1" --> "0..many" Decision
  Recommendation "1" --> "many" OutboxItem : one per shipment
  Forecast "many" --> "many" Alert : raises
```

**Invariants (tested as properties):** `inventory` counts only on-hand stock — scheduled/delayed supply and in-transit shipments are separate; every `Shipment.quantity ≤ route.max_shipment`; `OutboxItem.body` is immutable after insert (a changed body requires a new key); a `Recommendation` cannot be approved after `validUntilTick` or on a non-`LIVE` snapshot.

---

## 7. Lifecycles and state machines

### 7.1 Recommendation

```mermaid
stateDiagram-v2
  [*] --> PROPOSED
  PROPOSED --> APPROVED : operator approves
  PROPOSED --> REJECTED : operator rejects
  PROPOSED --> EXPIRED : tick passes validUntilTick
  PROPOSED --> SUPERSEDED : newer rec for same station and fuel
  APPROVED --> SUBMITTING : dispatcher claims outbox row
  SUBMITTING --> SUBMITTED : simulator 200 or 201
  SUBMITTING --> STALE_RECOMMENDATION : pre-flight fails
  SUBMITTING --> FAILED : permanent 409
  SUBMITTING --> SUBMITTING : transient 503 or timeout, backoff retry
  SUBMITTED --> IN_TRANSIT : allocation departs
  IN_TRANSIT --> ARRIVED
  IN_TRANSIT --> FAILED
  STALE_RECOMMENDATION --> [*] : re-plan creates new PROPOSED
  ARRIVED --> [*]
  REJECTED --> [*]
  EXPIRED --> [*]
  SUPERSEDED --> [*]
  FAILED --> [*]
```

### 7.2 Circuit breaker (per dependency: simulator, predictor, LLM)

```mermaid
stateDiagram-v2
  [*] --> CLOSED
  CLOSED --> OPEN : failures >= BREAKER_FAILURES within BREAKER_WINDOW_S
  OPEN --> HALF_OPEN : after BREAKER_RESET_S
  HALF_OPEN --> CLOSED : probe succeeds
  HALF_OPEN --> OPEN : probe fails
```

### 7.3 Snapshot freshness

```mermaid
stateDiagram-v2
  [*] --> LIVE
  LIVE --> STALE : X-Simulator-Stale header or fetch older than limit
  LIVE --> INVALID : payload fails validation (rejected, previous kept)
  STALE --> LIVE : fresh valid fetch
  INVALID --> LIVE : next valid fetch
```

**Decisions**
- A state machine makes illegal transitions impossible and gives the audit trail for free (D22).
- `STALE` snapshots **disable approve/dispatch**; reads remain available (graceful degradation).
- `SUBMITTING → SUBMITTING` is safe only because of the simulator's idempotency rule: same key + same body replays (accept 200 **or** 201); a changed body would 409.

---

## 8. How a request travels — sequences

### 8.1 Middleware pipeline for any API request

```mermaid
flowchart LR
  A["Browser"] --> B["Vercel rewrite /api"]
  B --> C["FastAPI: request-id + structured log context"]
  C --> D["CORS allow-list"]
  D --> E["Rate limit"]
  E --> F["Auth: bearer token for mutations"]
  F --> G["Pydantic request validation"]
  G --> H["Router (adapter in)"]
  H --> I["Use case (application)"]
  I --> J["Repository / port (adapter out)"]
  J --> K["Response model + problem+json on error"]
  K --> L["Metrics: rate, latency histogram, errors"]
  L --> A
```

| Hop | Responsibility | Failure → response |
|---|---|---|
| request-id/log | correlate logs and traces | — |
| rate limit | protect under traffic spike | 429 problem+json |
| auth | operator token on mutating routes | 401/403 |
| validation | reject malformed input | 422 problem+json |
| use case | business rules | domain error → 409/422 with `code` |
| repository/port | DB or dependency call with timeout/breaker | 503 with degraded hint |
| metrics | feed Prometheus + status page | — |

### 8.2 Dashboard read (never touches the simulator)

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser (TanStack Query)
  participant V as Vercel
  participant A as API
  participant R as SnapshotRepo (Postgres)
  B->>V: GET /api/v1/network/state (If-None-Match)
  V->>A: proxy request
  A->>A: request-id, rate limit, validate
  A->>R: latest snapshot and read models
  R-->>A: snapshot + freshness
  alt ETag unchanged
    A-->>B: 304 Not Modified
  else changed
    A-->>B: 200 state + freshness + simulated flag
  end
  Note over B: renders LIVE or STALE banner from freshness
```

### 8.3 Ingestion cycle (worker, wall-clock paced)

```mermaid
sequenceDiagram
  autonumber
  participant W as Worker ingest loop
  participant G as SimulatorGateway (ACL + breaker)
  participant S as Simulator
  participant DB as Postgres
  participant M as Metrics
  loop every INGEST_INTERVAL_S (default 1 s)
    W->>G: fetch instance
    G->>S: GET /v1/instance
    alt simulator healthy
      S-->>G: tick, sim_time, status
      G->>S: GET depots, stations, routes, supply-arrivals, events, metrics
      G->>S: GET demand-history (limit = min(2000, 12*delta_ticks + 12))
      S-->>G: JSON (+ maybe X-Simulator-Stale)
      G->>G: strict validation (pydantic)
      alt valid and not stale
        G-->>W: NetworkSnapshot LIVE
        W->>DB: insert snapshot, upsert demand_obs
      else stale header
        G-->>W: NetworkSnapshot STALE
        W->>DB: insert snapshot with freshness STALE
        W->>M: snapshot_stale metric, alert
      else malformed or missing fields
        G-->>W: validation error
        W->>M: alert: input rejected, previous snapshot kept
      end
    else 503 or timeout
      G-->>W: failure (breaker counts it)
      W->>M: simulator_requests_total{status=5xx}, breaker_state
      Note over W,DB: previous LIVE snapshot remains the last-known-good
    end
  end
```

### 8.4 Compute a recommendation (predictor boundary + fallback)

```mermaid
sequenceDiagram
  autonumber
  participant O as Operator UI
  participant A as API (decision use case)
  participant N as network read model
  participant P as Predictor (breaker)
  participant F as In-process fallback
  participant POL as AllocationPolicy
  participant DB as Postgres
  O->>A: POST /recommendations:compute (bearer token)
  A->>N: latest snapshot
  N-->>A: snapshot (freshness LIVE)
  A->>P: forecast(snapshot, demand history)
  alt predictor healthy
    P-->>A: forecasts + confidence
  else timeout or breaker open
    A->>F: baseline forecast (same forecast_core)
    F-->>A: forecasts, flagged fallback_active
    Note over A: metric fallback_activations_total++
  end
  A->>POL: plan(snapshot, forecasts)
  alt LP policy succeeds
    POL-->>A: shipments + impact + alternatives
  else LP infeasible or error
    POL->>POL: priority heuristic
    POL-->>A: shipments, policy=heuristic
  end
  A->>A: ConstraintChecker (the 9 simulator rules)
  A->>A: confidence, review_required, valid_until_tick
  A->>DB: insert recommendation (PROPOSED)
  A-->>O: 201 recommendation (evidence included)
```

### 8.5 Approve → outbox → simulator (the reliable write)

```mermaid
sequenceDiagram
  autonumber
  participant O as Operator UI
  participant A as API
  participant DB as Postgres
  participant D as Worker outbox dispatcher
  participant G as SimulatorGateway
  participant S as Simulator
  O->>A: POST /recommendations/{id}/approve (bearer token)
  A->>A: check status PROPOSED, snapshot LIVE, not expired
  A->>DB: one transaction: insert decision, update rec to APPROVED, insert outbox rows (key rec-id-iN)
  A-->>O: 202 Accepted (dispatch pending)
  loop dispatcher poll
    D->>DB: SELECT ... FOR UPDATE SKIP LOCKED where due
    D->>G: pre-flight: re-GET depot, station, route and re-check the 9 rules
    alt pre-flight fails
      D->>DB: rec to STALE_RECOMMENDATION, alert, trigger re-plan
    else pre-flight ok
      G->>S: POST /v1/allocations (idempotency_key, same body)
      alt 200 or 201
        S-->>G: allocation id, status PENDING
        D->>DB: outbox SENT, store sim_allocation_id
      else 503 or timeout
        D->>DB: attempts++, next_attempt_at = backoff with jitter
        Note over D,S: retry later with same key and same body is a safe replay
      else 409 domain error
        S-->>G: code e.g. ROUTE_DISRUPTED
        D->>DB: outbox FAILED_PERMANENT, rec FAILED, alert, re-plan
      end
    end
  end
  Note over D,S: later ingestion cycles observe IN_TRANSIT then ARRIVED
```

### 8.6 Crisis: demand spike detected → adapted recommendation

```mermaid
sequenceDiagram
  autonumber
  participant ORG as Organizer
  participant S as Simulator
  participant W as Worker
  participant FC as forecast_core
  participant AL as Alert evaluator
  participant UI as Operator UI
  participant A as API
  ORG->>S: POST /admin/events demand_spike x1.8 region-dhaka
  S-->>S: station demand_multiplier rises while event ACTIVE
  loop next ingestion cycles
    W->>S: GET stations, demand-history
    W->>FC: update demand ratio (EWMA) and CUSUM
    FC-->>W: shift detected, estimated multiplier, new p_stockout
  end
  W->>AL: p_stockout above threshold
  AL-->>UI: alert: station, fuel, time-to-stockout, signals
  UI->>A: compute recommendation
  A-->>UI: cross-checked plan, impact 72% to 19%, alternatives
  UI->>A: approve
  Note over A,S: continues as 8.5, then recovery is visible when the event resolves
```

### 8.7 Predictor outage

```mermaid
sequenceDiagram
  autonumber
  participant A as API
  participant BR as Breaker
  participant P as Predictor
  participant F as Fallback forecaster
  participant UI as Operator UI
  A->>BR: call forecast
  BR->>P: HTTP request (timeout)
  P--xBR: no response
  BR->>BR: failure count reaches threshold, state OPEN
  A->>F: use baseline forecast
  A-->>UI: results flagged FALLBACK POLICY ACTIVE
  Note over BR: after BREAKER_RESET_S go HALF_OPEN and probe
  BR->>P: probe
  P-->>BR: ok
  BR->>BR: CLOSED, banner clears
```

### 8.8 Explanation (LLM outside the decision path)

```mermaid
sequenceDiagram
  autonumber
  participant UI as Operator UI
  participant A as API
  participant C as Explanation cache
  participant L as LLM client (breaker)
  UI->>A: GET /recommendations/{id}/explanation
  A->>C: lookup (rec_id, version)
  alt cache hit
    C-->>A: stored text
  else miss
    A->>L: structured JSON: signals, constraints, alternatives
    alt LLM ok
      L-->>A: schema-validated explanation
      A->>C: store
    else LLM down or invalid output
      A->>A: template explanation
    end
  end
  A-->>UI: explanation (source: llm or template)
```

**Decisions across §8**
- **Reads never block on the simulator** (8.2) — CQRS-lite read models; this is what makes the dashboard degradable.
- **Wall-clock ingestion with backfill** (8.3) because the simulator may run at 8–15 ticks/s; per-tick ingestion would be both impossible and unnecessary.
- **Outbox over inline POST** (8.5; in the trunk the outbox *is* the `recommendations` table, see §2.1): approve and "to-send" are one DB transaction; the dispatcher is at-least-once and the simulator's idempotency makes redelivery safe. Pre-flight prevents sending a plan that became invalid while waiting.
- **Fallback is a code path, not a toggle** (8.4, 8.7): the in-process forecaster uses the same `forecast_core`, so degraded results are coherent, just less refined.
- **Human approval is mandatory** (8.5): there is no route from compute to dispatch without a `Decision` row.

---

## 9. Data architecture

```mermaid
erDiagram
  SNAPSHOTS ||--o{ RECOMMENDATIONS : "basis"
  RECOMMENDATIONS ||--o{ DECISIONS : "judged by"
  RECOMMENDATIONS ||--o{ OUTBOX : "dispatches"
  SNAPSHOTS ||--o{ FORECASTS : "basis"
  FORECASTS ||--o{ ALERTS : "raises"
  RECOMMENDATIONS ||--o{ AUDIT_LOG : "recorded in"
  DEMAND_OBS {
    text station_id PK
    text fuel_type PK
    int tick PK
    numeric demand_l
    numeric served_l
    numeric unmet_l
  }
  SNAPSHOTS {
    uuid id PK
    int tick
    timestamptz sim_time
    text freshness
    jsonb payload
  }
  RECOMMENDATIONS {
    uuid id PK
    uuid snapshot_id FK
    int created_tick
    int valid_until_tick
    text policy
    text status
    numeric confidence
    boolean review_required
    jsonb items
    jsonb impact
  }
  DECISIONS {
    uuid id PK
    uuid recommendation_id FK
    text actor
    text verdict
    text reason
  }
  OUTBOX {
    uuid id PK
    uuid recommendation_id FK
    text idempotency_key UK
    jsonb body
    text body_hash
    text state
    int attempts
    int sim_allocation_id
  }
  FORECASTS {
    uuid id PK
    uuid snapshot_id FK
    text station_id
    text fuel_type
    numeric p_stockout
    numeric confidence
  }
  ALERTS {
    uuid id PK
    text type
    text severity
    text state
  }
  AUDIT_LOG {
    uuid id PK
    text action
    text entity
    jsonb detail
  }
```

**Decisions**
- **PostgreSQL 18 (D5):** one transaction covers decision + outbox; `UNIQUE(idempotency_key)` enforces the simulator's idempotency contract locally; `DEFAULT uuidv7()` gives time-ordered keys; partial index `outbox (next_attempt_at) WHERE state='PENDING'` keeps the dispatcher cheap.
- `snapshots.payload` is JSONB (raw validated copy for audit/replay) with the hot fields extracted; `demand_obs` is relational because forecasting needs windowed queries.
- **No Redis (D6):** latest-snapshot read model + in-process TTL cache cover degraded mode.

---

## 10. Frontend architecture

```mermaid
flowchart TB
  subgraph app["app/ (routing, providers, error boundaries, global banners)"]
    r["Router"]
  end
  subgraph features["features/* (vertical slices)"]
    f1["network: hooks, view-models, panels"]
    f2["forecast and alerts"]
    f3["recommendations: inspector, approve flow"]
    f4["system: status page"]
  end
  subgraph comps["components/ (design-system primitives)"]
    c1["Card, StatusPill, Gauge, Table, Banner"]
  end
  subgraph api["api/"]
    q["TanStack Query client, typed from OpenAPI, error mapping"]
  end
  r --> features
  features --> comps
  features --> q
  q -->|"polling 2-5 s, ETag"| backend["Backend /api/v1"]
```

**Decisions**
- **SPA over Next.js (D12):** no SSR need; one fewer runtime on Vercel.
- **Server state in TanStack Query, almost no client state:** the backend is the source of truth; polling with ETag gives near-real-time without WebSocket machinery (D13). SSE is a stretch, connected directly to the API origin because long-lived streams through Vercel rewrites are unverified.
- **Components never call `fetch`;** feature hooks do. View-models are pure functions → unit-testable without a DOM.
- **Banners are first-class:** `LIVE | STALE | FALLBACK ACTIVE | APPROVALS DISABLED` plus a permanent **SIMULATED DATA** tag (F10).

---

## 11. Observability architecture

```mermaid
flowchart LR
  api["api"] -->|"/metrics"| prom["Prometheus"]
  worker["worker"] -->|"/metrics"| prom
  pred["predictor"] -->|"/metrics"| prom
  prom --> graf["Grafana dashboards<br/>Golden signals, Intelligence, Resilience, Dispatch"]
  prom --> rules["Alert rules"]
  rules --> status["In-app system status and alerts"]
  api -->|"JSON logs"| logs["stdout, Docker logs, Render logs"]
  worker -->|"JSON logs"| logs
  api -->|"/health/ready, /system/status"| status
```

| Layer | Signals |
|---|---|
| Application | request rate, latency histogram (p50/p95/p99), error rate |
| Integration | `simulator_requests_total{status}`, `simulator_latency_seconds`, `breaker_state{dep}`, `snapshot_age_seconds` |
| Intelligence | `forecast_abs_error`, `forecast_confidence`, `shortage_alerts_open`, `recommendations_total{policy}`, `fallback_activations_total` |
| Dispatch | `outbox_pending`, `dispatch_failures_total{code}` |
| System | process CPU/memory |
| Logs | structured JSON with `request_id`, `tick`, `rec_id`: decisions, integration failures, recoveries |

**Decision:** Prometheus/Grafana run in compose (`obs` profile) where judges look; in the free cloud tier the same data is surfaced by the in-app status page (running a metrics stack there is impractical).

---

## 12. Delivery architecture (summary — details in `PIPELINE.md`)

```mermaid
flowchart LR
  dev["Feature branch"] --> pr["Pull request"]
  pr --> ci1["Lint, types, import-linter"]
  ci1 --> ci2["Unit tests"]
  ci2 --> ci3["Integration tests<br/>postgres:18 + simulator services"]
  ci3 --> ci4["Build images"]
  ci4 --> prev["Vercel preview"]
  prev --> merge["Merge to main"]
  merge --> e2e["E2E on compose (Playwright)"]
  e2e --> push["Push images (GHCR)"]
  push --> deploy["Render deploy hook + Vercel production"]
  deploy --> smoke["Smoke: /health/ready"]
  smoke -->|"fail"| rb["Rollback to previous deploy"]
  nightly["Nightly"] --> acc["Acceptance suite, k6 load, policy bake-off"]
```

**Decision:** the four test levels map to pipeline stages so a failure points at a class of defect: unit (logic) → integration (contracts with Postgres/simulator) → E2E (user journeys) → acceptance (business outcomes).

---

## 13. Decision traceability

| Requirement (brief) | Where satisfied |
|---|---|
| Operator application | §10, UC1–UC11 |
| Simulator integration | §2, §8.3, §8.5 |
| Intelligence (predict/detect/decide/GenAI) | §4.1 forecast/decision modules, §8.4, §8.8 |
| Explainable decisions | recommendation evidence (§6), UC5 |
| Resilience / graceful degradation | §7.2, §7.3, §8.3, §8.7, resilience matrix in `FINAL_SYSTEM_DESIGN.md` §8 |
| Observability + health | §11, UC10 |
| Deployment (reproducible) | §3.1 compose, §3.2 cloud |
| CI/CD, tests | §12 |
| Load testing | k6 against `/network/state` and `/recommendations:compute` (§12 nightly) |
| Human review of consequential decisions | UC7, §8.5 |
