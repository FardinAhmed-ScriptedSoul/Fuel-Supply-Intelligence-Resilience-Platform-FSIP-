# CLAUDE.md — Fuel Supply Intelligence & Resilience Platform

Project memory for Claude Code. Rules are imperative; the *why* lives in `docs/`. Keep this file short — if a rule needs a paragraph, it belongs in a doc or a skill.

## What this is
An operator-facing decision-support platform on top of the organizer's **BUP Fuel Supply Simulator**: observe → detect → predict → decide → (human approves) → dispatch → monitor → recover. Deadline **Thu 2026-11-26**. Everything is **simulated** — never imply real-world fuel data or real dispatch.

## Source of truth (read before designing anything)
- `docs/FINAL_SYSTEM_DESIGN.md` — locked decisions `D1–D22`, resilience contract, plan
- `docs/ARCHITECTURE.md` — diagrams, sequences, schema
- `docs/PIPELINE.md` — build/test/CI/CD (when present)
- `SKILLS.md` — which skill to use for what
- If code and docs disagree: **stop and flag it.** Changing a decision = short ADR in `docs/adr/NNN-title.md` + update the register.

## Stack
Python 3.12 · FastAPI (async) · pydantic v2 · SQLAlchemy 2 async + Alembic + asyncpg · **PostgreSQL 18** · SciPy (HiGHS LP) + numpy · httpx · tenacity · prometheus-client · structlog · pytest + hypothesis + testcontainers + respx · React 18 + TypeScript + Vite · TanStack Query · Tailwind · Recharts · React Flow · Vitest + RTL + MSW · Playwright · k6 · Docker Compose · GitHub Actions · Vercel (web) + Render (api).
No Redis in v1 (D6). No new service, datastore, or framework without an ADR.

## Commands (Makefile — created in the Day-1 scaffold; if a target is missing, add it, don't invent a one-off)
`make up | down | logs` · `make test-unit | test-int | test-e2e | test-acc | test` · `make lint | typecheck | gen-api` · `make smoke | load | bakeoff | sim-reset`

## Repo layout
```
backend/app/{shared,network,forecast,decision,ops}/{domain,application,adapters}
backend/app/{main.py,worker.py,composition.py}     # composition.py = the only wiring point
libs/forecast_core/                                 # pure forecast library (used by predictor + in-process fallback)
predictor/   web/   deploy/{compose,grafana,prometheus,k6}/   docs/   .github/workflows/
```

## Architecture rules
- Layers per module: `adapters/in → application → domain ← adapters/out`. **`domain` imports no FastAPI/SQLAlchemy/httpx.**
- Modules talk only via ports or read models; never import another module's adapters or ORM models (`import-linter` enforces).
- Dependencies are injected from `composition.py`. **No module-level mutable globals, no classic Singleton.** One `httpx.AsyncClient`/engine/breaker registry per process, created at startup.
- Repositories are per aggregate with query-shaped methods; no generic `Repository[T]` CRUD wrapper.
- Policies are `AllocationPolicy` strategies chosen by config, never by `if` chains in handlers.
- Write domain logic **before** persistence; pure functions first (`forecast`, `plan`, `check`).

## Simulator rules (gotchas — all verified in the integration guide)
- Never modify the simulator; judges run the published image. Base URL only via `SIMULATOR_BASE_URL`.
- **REST is truth, SSE is a hint.** After any SSE event, gap, or reconnect → refetch via REST (no `Last-Event-ID`; queue drops silently after 200).
- Parse **both** error envelopes: faults `{"error":{…}}`, domain errors `{"detail":{"code":…}}`; `stream_disconnect` nests under `detail`.
- `X-Simulator-Stale: true` ⇒ mark snapshot STALE, drop caches, **block approve/dispatch**.
- `POST /v1/allocations`: key `rec-<uuid>-i<n>` (≤150 chars). **Same key + changed body ⇒ 409; cancel does not free a key.** Accept replay as **200 or 201**.
- Always **pre-flight** (fresh GET depot/station/route + re-check the 9 validation rules) before POST. Inventory excludes in-transit and scheduled supply.
- Always pass `limit` to `/v1/demand-history` (≤ 2000); 12 rows/tick.
- Read tick length from `/v1/instance`; never hard-code minutes. Two clocks: wall seconds (ingestion, timeouts) vs sim ticks (horizons, validity).
- `/admin/*` is for tests, rehearsal and organizers. Production code paths never depend on it (dev passthrough is behind `DEV_TOOLS_ENABLED`).
- Deterministic tests: simulator `paused`, `/admin/reset`, drive time with `/admin/step`.

## Resilience rules
- **Every external call has a timeout, a retry policy, a breaker, and a defined degraded behavior** (see resilience contract in the design doc). No bare `httpx.get`.
- Invalid input ⇒ reject + alert + keep previous snapshot. Never "fix up" malformed data silently.
- Fallbacks are code paths exercised in tests (predictor down ⇒ in-process baseline + heuristic; LLM down ⇒ template; DB down ⇒ read-only last snapshot).
- Transient (503/timeout) ⇒ retry same key + same body. Permanent (409) ⇒ FAILED + alert + re-plan. Never blind-retry a 409.

## Intelligence rules
- **The LLM never decides, never writes.** It explains structured output behind `LLMPort`, schema-validated, cached, with template fallback.
- Every recommendation carries: signals, constraints checked, alternatives, expected impact, confidence, `valid_until_tick`.
- Low confidence ⇒ `review_required`. **All** dispatch requires a human `Decision` row — there is no auto-dispatch path.
- Any new policy must be comparable in `make bakeoff` (same seed, second simulator instance).

## Testing rules (4 levels, every feature)
- **Unit** (pure domain; hypothesis property: "no plan violates the 9 rules") → **Integration** (real Postgres 18 + real simulator container; `respx` only for edge faults) → **E2E** (Playwright on compose) → **Acceptance** (brief scenarios as Given/When/Then via `/admin/events|faults`).
- A feature is done only when all four levels cover it and the DoD below passes. Flaky test = bug; fix or delete with an ADR, never `skip` quietly.
- Reset state between acceptance scenarios (`/admin/reset`). Tests assert exact values where the world is deterministic.

## Frontend rules
- Components never call `fetch`; use feature hooks. Types come from the OpenAPI (`make gen-api`); no hand-written API types.
- Always render state banners (`LIVE | STALE | FALLBACK ACTIVE | APPROVALS DISABLED`) and the permanent **SIMULATED DATA** tag.
- Operator console = calm and dense. Motion communicates state change only (new alert, status change); ≤ ~200 ms; honor `prefers-reduced-motion`; never animate values that refresh on every poll.
- Design/motion work goes through the skills in `SKILLS.md` (Impeccable for design review, Emil Kowalski's skills for motion).

## Code style
- Python: `ruff` + `mypy --strict` on `domain/` and `application/`; type hints everywhere; async I/O; `structlog` (no `print`); errors as typed domain errors mapped to `application/problem+json`.
- TypeScript: `strict`, ESLint, no `any`, no default exports for components.
- Config via environment only, documented in `.env.example`. Names in `FINAL_SYSTEM_DESIGN.md` §8 (`SIM_TIMEOUT_S`, `BREAKER_*`, `INGEST_INTERVAL_S`, `REC_VALID_TICKS`, `RUN_WORKER_IN_PROCESS`, `DEV_TOOLS_ENABLED`, `SIMULATOR_BASE_URL`).

## Security
No secrets in git (use `.env`, GitHub/Render/Vercel secret stores). Validate all inbound data with pydantic. Operator token on mutating routes (constant-time compare). Strict CORS allow-list. Never proxy simulator `/admin` in production. Non-root containers.

## Git & PRs
Trunk-based; branch `feat/<slice>-<topic>`; never push to `main`. Small PRs (≲ 400 lines), conventional commits, 1 review. Agree the OpenAPI contract before parallel FE/BE work on a slice.
**Definition of Done:** code + unit + integration green → E2E journey updated → acceptance scenario passes → metrics/logs added → OpenAPI/docs updated → preview deployed → smoke green.

## Do not
- Edit the simulator, hard-code tick length or entity ids, or bypass the outbox with an inline POST.
- Count in-transit or scheduled stock as inventory.
- Put LLM output in a decision path, or add auto-approval.
- Swallow exceptions, add unbounded retries, or call a dependency without timeout + breaker.
- Add dependencies, services, or Redis casually; disable or skip tests; commit `.env` or keys.

## When unsure
Prefer the simplest design that satisfies the requirement (7-day deadline). Ask before changing a locked decision; otherwise decide, note the assumption in the PR, and continue. Report progress daily: done / doing / blockers / next.
