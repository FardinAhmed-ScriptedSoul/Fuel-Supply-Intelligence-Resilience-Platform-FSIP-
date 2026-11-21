# CLAUDE.md — Fuel Supply Intelligence & Resilience Platform

Project memory for Claude Code. **Goes at the root of the code repo.** Rules are imperative; the *why* lives in `docs/`. Keep this file short — a rule that needs a paragraph belongs in a doc or a skill.
*(v1.1 — aligned to the trunk repo's real layout and env names.)*

## What this is
An operator-facing decision-support platform on top of the organizer's **BUP Fuel Supply Simulator**: observe → detect → predict → decide → **(human approves)** → dispatch → monitor → recover. Deadline **Thu 2026-11-26**; feature freeze **Wed 2026-11-25 18:00**. Everything is **simulated** — never imply real fuel data or real dispatch.

## Source of truth (read before designing or coding)
- `docs/design/FINAL_SYSTEM_DESIGN.md` — locked decisions `D1–D22`, resilience contract, time model
- `docs/design/ARCHITECTURE.md` — diagrams, sequences, as-built mapping
- `docs/process/FEATURE_IMPLEMENTATION_PLAN.md` — **how every feature is built** (follow it)
- `docs/process/SECURITY_AND_REVIEW_POLICY.md` · `docs/process/PIPELINE.md` · `docs/process/BACKLOG.md`
- `docs/sim-findings.md`, `docs/simulator-contract.md` — what the simulator really does · `docs/PROGRESS.md` — evidence log
- `SKILLS.md` — which skill for what
- If code and docs disagree: **stop and flag it.** Changing a locked decision = ADR in `docs/adr/NNN-title.md`.

## Stack (as built)
Python 3.12 · FastAPI · pydantic v2 · **asyncpg + plain SQL (`backend/api/db.sql`)** · **PostgreSQL 18** (target; F-001) · httpx · numpy/SciPy · prometheus-client · pytest (+hypothesis, respx, pytest-cov) · import-linter · ruff · React 18 + TypeScript + Vite · TanStack Query · Tailwind · Recharts · Vitest · Playwright (F-018) · k6 · Docker Compose · GitHub Actions · Vercel (web) + Render (api/worker).
No Redis, no new service/datastore/framework without an ADR (D6).

## Repo layout
```
backend/shared/core/   pure logic (models, world, forecast, risk, validator, explain, policies/) + sim_client.py (the simulator client)
backend/api/           FastAPI read API + operator approve/reject  — reads the DATABASE ONLY
backend/worker/        simulator I/O, ingest, SSE, forecast/recommend jobs, executor (the only simulator writer)
intel/predictor/       predictor service (skeleton → F-006)
web/                   React app          observability/   Prometheus + Grafana
tests/{unit,integration,scenarios,acceptance}/     web/e2e/ (Playwright)     docs/    scripts/    deploy/
```

## Commands
`make up | down | logs | smoke` · `make test-unit | test-int | test-acc | test-e2e` · `make lint | lint-arch | security` · `make feature ID=F-### NAME=<kebab> [TYPE=feat]` · `make pre-pr` / `pre-pr-fast` · `make sim-reset | sim-step | sim-pause` · `make load`
Never use `docker compose down -v` unless a human asked (it deletes local DB/Grafana data).

## Workflow (mandatory — details in the feature plan)
1. One feature = one backlog ID = one branch `<type>/F-###-kebab-name` = one spec `docs/features/F-###-*.md` = one PR. Create with `make feature`.
2. Spec first → **failing tests first** → implement → **all four test levels** (unit, integration, E2E, acceptance) → resilience + observability → security pass → `make pre-pr` → PR (template) → review → squash merge → verify deploy → `docs/PROGRESS.md`.
3. Evidence = real command output pasted in the spec/PR. Never claim a gate passed without output.
4. An agent **never approves, merges, or deploys its own PR.**

## Architecture rules (enforced by `.importlinter`; run `make lint-arch`)
- `core` pure modules (`models, world, forecast, risk, validator, explain, policies`) import **no** fastapi/asyncpg/httpx/api/worker. *(Known violation: `core.models` imports `httpx` → F-004.)*
- `api` never imports `worker` or `core.sim_client` (the API reads the database only). `worker` never imports `api`.
- Dependencies are wired at startup, not via module globals; no classic Singleton. One `httpx` client/DB pool/breaker per process.
- Write pure logic first (`forecast`, `plan`, `check`), adapters after. Policies are `AllocationPolicy` strategies chosen by config, never `if` chains.
- Config only via environment; add to `.env.example` with a safe placeholder.

## Simulator rules (gotchas)
- Never modify the simulator. Base URL only via `SIM_BASE_URL`. Read tick length from `/v1/instance`; never hard-code minutes.
- **REST is truth, SSE is a hint** → refetch after any event/gap/reconnect (no `Last-Event-ID`; queue drops silently after 200).
- Parse **both** error envelopes: faults `{"error":{…}}`, domain errors `{"detail":{"code":…}}` (`stream_disconnect` nests under `detail`).
- `X-Simulator-Stale: true` ⇒ mark snapshot STALE, drop caches, **block approve/dispatch**.
- `POST /v1/allocations`: one stable idempotency key per shipment (≤150 chars); **same key ⇒ same body, always**; changed body ⇒ new key; replay may return **200 or 201**; cancel does **not** free a key.
- **Pre-flight before every POST:** fresh GET of depot/station/route + the simulator's 9 rules **+ scheduled/active `route_disruption` events covering the departure tick + in-flight headroom at the destination + depot inventory net of other approved-unsent shipments** (F-010). A shipment that fails at departure loses its fuel *[doc; verify]*.
- In-transit and scheduled supply are **never** inventory. Always pass `limit` (≤ 2000) to `/v1/demand-history` (12 rows/tick).
- Facts to **re-verify** before relying on them: supply ends at tick 212; Tongi and Cox's Bazar are single-route; do-nothing first stockout ≈ tick 66.
- `/admin/*` is for tests, harnesses and demo rehearsal — never in production code paths. Deterministic tests: paused simulator → `/admin/reset` → inject → `/admin/step`; never sleep-wait for ticks.

## Resilience rules
- **Every external call: timeout + bounded retry with jitter + circuit breaker + defined degraded behavior.** No bare `httpx.get`.
- Invalid input ⇒ reject + alert + keep the last good snapshot. Never silently "fix" malformed data.
- Fallbacks are code paths with tests: predictor down ⇒ in-process baseline + heuristic; LLM down ⇒ template; DB down ⇒ read-only last snapshot.
- Transient (503/timeout) ⇒ retry with the **same** key and body. Permanent (409) ⇒ FAILED + alert + re-plan. Never blind-retry a 409.
- Degraded states are **visible** (UI banner, `/health`, metric) and recover automatically.

## Intelligence rules
- **The LLM never decides, never writes, never calls tools.** It explains structured output behind a port, schema-validated, cached, with template fallback.
- Every recommendation carries signals, constraints checked, alternatives, expected impact, confidence, `valid_until_tick`. Low confidence ⇒ `review_required`.
- **No dispatch without a persisted human decision.** No auto-submit path exists; do not add one.
- A new policy must be comparable in the bake-off (same seed, second simulator instance).

## Testing rules
- Four levels, every feature (plan §4). Dispatch path = all four, **mandatory**. Coverage: new/changed lines ≥ 85 %; dispatch path ≥ 90 %; never lower the baseline (82 % on 2026-11-20).
- Flaky test = defect (fix or delete via ADR; never silent `skip`). Use real captured samples (`docs/sim-samples/`), not invented payloads. Assert behavior, not implementation.

## Frontend rules
- Components never call `fetch` — feature hooks do. Always show the state banners (`LIVE | STALE | FALLBACK ACTIVE | APPROVALS DISABLED`) and the permanent **SIMULATED DATA** tag.
- Calm, dense operator console. Motion only for state change; ≤ ~200 ms; honor `prefers-reduced-motion`; never animate values refreshed on every poll. Use the design/motion skills in `SKILLS.md`.

## Style
Python: `ruff` (check + format), type hints, async I/O, structured logs (no `print`), typed errors. TypeScript: `strict`, no `any`. Conventional commits `type(F-###): summary`; PR ≲ 400 lines; squash merge.

## Security (details: `SECURITY_AND_REVIEW_POLICY.md`)
No secrets in git/logs. Validate every inbound payload. Operator token on mutating routes (`hmac.compare_digest`). Parameterized SQL only. Outbound URLs from env only. `/api/chaos/*` off unless `DEV_TOOLS_ENABLED=true`. Never proxy simulator `/admin` in production. Non-root containers. New dependency ⇒ ask first and vet it.

## Forbidden without an explicit human instruction in this session
`docker compose down -v` · `git push --force` (except `--force-with-lease` on your own feature branch) · `git reset --hard` on shared branches · deleting branches you did not create · `rm -rf` outside build/cache dirs · editing `.env` · running against anything but the simulator · skipping/disabling tests · pushing to `main` · weakening a safety invariant.

## When unsure
Choose the simplest option that keeps acceptance criteria true, log it under "Deviations" in the spec, and continue; if it touches a locked decision or safety invariant, **stop and ask**. Report daily: done / doing / blockers / next.
