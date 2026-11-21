# SPRINTS — five sprints from 20 Nov to the 26 Nov deadline

| | |
|---|---|
| **Status** | v1.0 · 2026-11-20 · source of truth for dates and scope: `planning/sprints.json` + `planning/backlog.json` (this file is the readable view) |
| **Date reading** | You wrote "20/11/26 to 20/11/25". I read it as **Fri 20 Nov 2026 -> Wed 25 Nov 2026 (feature freeze 18:00)**, and **Thu 26 Nov is the delivery day**, so Sprint 5 covers 25–26 Nov. If you meant something else, edit `planning/sprints.json` — every script follows it. |
| **Naming** | Platform sprints are **S1–S5**. They are different from the "Sprint 1–4" history inside the trunk repo (that work is already done). |
| **Capacity note** | A "sprint" here is 1–2 days. Scope is therefore deliberately tight, P2 items are explicit cut candidates, and each sprint ends with a demonstrable result. |

```mermaid
gantt
  dateFormat  YYYY-MM-DD
  axisFormat  %d %b
  section Sprints
  S1 Foundations and Gates        :s1, 2026-11-20, 1d
  S2 Safe Dispatch                :s2, 2026-11-21, 1d
  S3 Resilience and Scenarios     :s3, 2026-11-22, 1d
  S4 Scarcity, Deploy, Observe    :s4, 2026-11-23, 2d
  S5 Freeze, Evidence, Delivery   :s5, 2026-11-25, 2d
  section Milestones
  Feature freeze 18:00            :milestone, m1, 2026-11-25, 0d
  Deadline                        :milestone, m2, 2026-11-26, 0d
```

---

## S1 — Foundations & Gates · Fri 20 Nov
**Goal:** adopt the trunk repo, move to PostgreSQL 18, and put CI, branch protection and the review workflow in place so every later feature ships through gates.

| Feature | Branch | Pri |
|---|---|:--:|
| F-001 PostgreSQL 18 migration | `chore/F-001-postgres-18-migration` | P0 |
| F-002 CI hardening (adopt starter kit) | `chore/F-002-ci-hardening` | P0 |
| F-003 Dependency security bump | `fix/F-003-dependency-security-bump` | P0 |
| F-004 Keep core pure | `refactor/F-004-core-purity-httpx` | P1 |

**Exit criteria**
- [ ] `docker compose` boots PostgreSQL 18; `db.sql` applies cleanly (CI `db-integration` green)
- [ ] Five required checks enforced on `main` (backend, db-integration, frontend, security, compose-smoke)
- [ ] `pip-audit` clean and the temporary waiver removed
- [ ] import-linter: all contracts kept with no ignore

**Demo:** open a PR from a feature branch; show required checks, the PR template, `make pre-pr` output.
**Risks:** no write access to the trunk repo (ask now) · everyone must recreate their local DB volume once for PG 18 (announce first) · Docker not installed on someone's machine.

## S2 — Safe Dispatch · Sat 21 Nov
**Goal:** close the open dispatch gate and harden pre-flight so an approved recommendation provably reaches ARRIVED without ever sending an unsafe shipment.

| Feature | Branch | Pri |
|---|---|:--:|
| F-005 Live dispatch acceptance | `feat/F-005-live-dispatch-acceptance` | P0 |
| F-010 Pre-flight hardening | `feat/F-010-preflight-hardening` | P0 |
| *(start)* F-006 Predictor + fallback | `feat/F-006-predictor-fallback` | P0 |
| *(start)* F-018 E2E journeys | `test/F-018-e2e-playwright-journeys` | P1 |

**Exit criteria**
- [ ] Approved allocation reaches ARRIVED under deterministic stepping; identical key+body replay verified
- [ ] Executor coverage ≥ 90 % with permanent / transient / expired paths tested
- [ ] Pre-flight property tests: no plan breaks any of the 9 rules, disrupted-route events or in-flight headroom

**Demo:** approve a recommendation, step the simulator, watch it arrive; replay the same request.
**Risks:** simulator behavior differs from the docs (record it in `sim-findings.md`) · replay-after-depletion is an open question.

## S3 — Resilience & Scenarios · Sun 22 Nov
**Goal:** prove behavior under change and failure: predictor fallback, the fault matrix, and the brief's crisis scenarios with do-nothing vs policy numbers.

| Feature | Branch | Pri |
|---|---|:--:|
| F-006 Predictor + breaker + fallback *(finish)* | `feat/F-006-predictor-fallback` | P0 |
| F-007 Acceptance scenario suite | `test/F-007-acceptance-scenario-suite` | P0 |
| F-008 Fault-handling matrix | `feat/F-008-fault-handling-matrix` | P0 |
| *(start)* F-009 Finite supply & rationing | `feat/F-009-finite-supply-rationing` | P1 |

**Exit criteria**
- [ ] Predictor service with breaker + in-process fallback; FALLBACK banner visible and self-clearing
- [ ] Every row of the resilience matrix has a test or recorded run and a visible degraded state
- [ ] Acceptance suite covers delay, spike, depot constraint, route disruption, station outage, combined

**Demo:** kill the predictor, inject faults, watch banners and automatic recovery; show scenario results.
**Risks:** acceptance tests slow or flaky if they rely on wall-clock time (use `/admin/step`).

## S4 — Scarcity, Deploy & Observe · Mon 23 – Tue 24 Nov
**Goal:** add finite-supply rationing, deploy to Vercel/Render, ship dashboards and the load test, close security waivers; stretch only if ahead.

| Feature | Branch | Pri |
|---|---|:--:|
| F-009 Finite supply & rationing | `feat/F-009-finite-supply-rationing` | P1 |
| F-012 Deploy to Vercel + Render | `chore/F-012-deploy-vercel-render` | P1 |
| F-017 Grafana dashboards & alert rules | `feat/F-017-grafana-dashboards` | P1 |
| F-011 Load test (k6) | `test/F-011-load-test-k6` | P1 |
| F-013 Operator identity & hardening | `feat/F-013-operator-identity-hardening` | P1 |
| F-018 E2E journeys *(finish)* | `test/F-018-e2e-playwright-journeys` | P1 |
| F-014 LP policy & bake-off · F-015 What-if · F-016 LLM explanations · F-020 SQL migrations | see `BACKLOG.md` | **P2 — cut first** |

**Exit criteria**
- [ ] Cover/rationing logic and isolation-risk flags live; acceptance shows fewer unmet liters than the plain heuristic
- [ ] Deployed stack passes `deploy-verify`; rollback rehearsed once
- [ ] k6 report with measured p50/p95/p99, throughput, error rate
- [ ] Grafana dashboards provisioned; operator identity and token hardening merged

**Demo:** the deployed app, Grafana, the k6 report.
**Risks:** Render free-tier sleep and 30-day DB expiry (decide on ≈ $27/mo or "wake before demo") · schema must be applied on boot for managed Postgres.

## S5 — Freeze, Evidence & Delivery · Wed 25 – Thu 26 Nov
**Goal:** feature freeze at **18:00 on 25 Nov**; evidence pack; demo rehearsal from a clean clone; tag `v1.0.0`; deliver on 26 Nov.

| Feature | Branch | Pri |
|---|---|:--:|
| F-019 Demo runbook & evidence pack | `docs/F-019-demo-runbook-evidence-pack` | P1 |
| Bug/regression fixes only after 18:00 (2 approvals) | `fix/F-###-…` / `hotfix/F-###-…` | — |

**Exit criteria**
- [ ] Freeze observed (bug fixes only, 2 approvals)
- [ ] Evidence pack: tests, load test, scenario/bake-off results, resilience demo notes
- [ ] Cold start from a clean clone with `docker compose up` works; demo rehearsed
- [ ] Tag `v1.0.0` created; final report delivered

**Demo:** the 14-step story from the brief (normal ops -> dashboard -> demand rises -> risk -> prediction -> recommendation -> inspect -> simulate -> crisis -> adapt -> failure injected -> monitoring detects -> fallback/recovery -> operations continue).

---

## Cut order when behind
1. F-014, F-015, F-016, F-020 (P2) → 2. SSE-to-browser and other polish → 3. extra Grafana panels → 4. F-013's per-operator tokens (keep the startup-refuses-default-token rule). **Never cut:** F-005, F-010, F-006, F-007, F-008, F-012 (or its documented fallback), F-019.

## Daily rhythm (per sprint day)
1. **Morning:** `bash scripts/plan.sh where` · pick the next feature · `bash scripts/plan.sh set F-### in_progress --owner "<you>"` · in the code repo `make feature ID=F-### NAME=<kebab>`.
2. **During:** follow `FEATURE_IMPLEMENTATION_PLAN.md`; record blockers immediately (`plan.sh blocker add "..." --feature F-###`).
3. **End of day:** `plan.sh set F-### review|done --pr <url>` · `plan.sh note add "<tomorrow>" --kind next` · `bash scripts/eod.sh` → paste `reports/daily/YYYY-MM-DD.update.txt` to your mentor · commit `reports/` and `planning/`.
4. **Last day of a sprint:** `bash scripts/report.sh sprint --sprint S#` (also produced by `eod.sh`) · fill the retrospective block.
