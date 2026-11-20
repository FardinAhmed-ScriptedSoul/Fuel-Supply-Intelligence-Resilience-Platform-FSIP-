# SECURITY AND REVIEW POLICY

| | |
|---|---|
| **Status** | v1.0 · 2026-11-20 · lives at `docs/process/SECURITY_AND_REVIEW_POLICY.md` |
| **Applies to** | every PR, human- or agent-authored |
| **Principle** | Proportionate to a 6-day simulated-data hackathon: **gates, not ceremony.** Everything here is either automated, a checklist item, or a named approval. |
| **Companions** | `FEATURE_IMPLEMENTATION_PLAN.md` (phases 6–8) · `PIPELINE.md` (the automated gates) · `CLAUDE.md` |

---

## 1. Scope and guardrails
- Operates **only** against the BUP Fuel Supply Simulator. No real fuel infrastructure, purchases, dispatches, credentials, or private systems.
- Simulated results are always **labeled SIMULATED** in the UI and docs.
- **Human review of consequential decisions is structural:** no code path dispatches without a persisted operator decision.
- No personal data is collected or stored. Not enterprise-grade security — but no hard-coded secrets, validated inputs, handled failures, documented config, restricted sensitive actions (brief §19).

---

## 2. Threat model (lite)

**Assets:** operator actions (approve/reject), the dispatch path to the simulator, `OPERATOR_TOKEN`, API keys (LLM), database contents, demo availability.
**Trust boundaries:** browser ⇄ API · worker ⇄ simulator · API/worker ⇄ database · API/worker ⇄ predictor · app ⇄ LLM provider · CI ⇄ cloud (Vercel/Render).

| Threat (STRIDE) | Where | Control | Verified by |
|---|---|---|---|
| **S**poofing: unauthenticated approval | `POST /api/recommendations/{id}/approve\|reject`, `/api/chaos/*` | Bearer `OPERATOR_TOKEN`, constant-time compare, startup refuses empty/`change-me` token outside local | integration test: 401/403 without token |
| **T**ampering: altered shipment body/idempotency replay with changed body | executor ⇄ simulator | stored `request_body` is immutable; stable key per shipment; same key ⇒ same body; simulator returns 409 on mismatch | unit + scenario test |
| **T**ampering: SQL injection | `backend/api`, `backend/worker/store.py` | asyncpg **parameterized** queries only (`$1…`), no string-built SQL | `ruff S608` + review |
| **R**epudiation: "who approved this?" | `decisions` table | every approve/reject stored with actor label, timestamp, reason (see F-013 for per-operator identity) | integration test |
| **I**nformation disclosure: secrets/stack traces in logs or errors | all services | env-only secrets, log redaction, `application/problem+json` without internals | review checklist §3 |
| **D**enial of service: traffic spike / slow dependency | API, simulator calls | rate limiting, timeouts, circuit breaker, cached read models, last-known-good | load test + fault tests |
| **E**levation: demo/chaos endpoints in production | `/api/chaos/*`, dev passthrough | disabled unless `DEV_TOOLS_ENABLED=true`, token-gated, never in cloud env | config test |
| **Poisoned input**: malformed/stale simulator data | ingestion | strict validation; reject + alert + keep last good; `X-Simulator-Stale` blocks dispatch | scenario tests with captured samples |
| **Prompt injection / unsafe LLM output** | explanation feature | LLM receives only structured data we generate (free text from the simulator = data, never instructions); no tools; output schema-validated; template fallback | unit test with hostile strings |
| **Supply chain**: vulnerable/malicious dependency or skill | `requirements.txt`, `web/package.json`, agent skills | pinned versions, audit gates, vetting (§9), skill vetting per `SKILLS.md` §2 | CI audits |

---

## 3. Per-feature security checklist (Phase 6; tick in the spec **and** the PR)

**3.1 Input and output**
- [ ] Every external input (HTTP body/query/path, simulator payload, predictor reply, LLM output, env var) is validated at the boundary with a strict schema; unknown/invalid ⇒ rejected, not "fixed up".
- [ ] Operator-facing request models forbid extra fields; numeric ranges and enum values are bounded (e.g., quantity > 0 and ≤ route max).
- [ ] Error responses expose a `code` and message, **never** stack traces, SQL, tokens, or internal hostnames.

**3.2 Authentication and authorization**
- [ ] Every state-changing route requires the operator token; read routes are intentionally public-to-viewer and return no secrets.
- [ ] Token comparison uses `hmac.compare_digest`; token only in the `Authorization: Bearer` header — never in URLs, logs, or the SPA bundle.
- [ ] No new "debug", "chaos", or admin route without `DEV_TOOLS_ENABLED` gating **and** token auth.

**3.3 Data and persistence**
- [ ] Queries are parameterized; no string-built SQL.
- [ ] Schema changes are additive and idempotent (`CREATE … IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`); verified on **PostgreSQL 18** in CI.
- [ ] Nothing sensitive (tokens, keys) is stored in the database or snapshots.

**3.4 Secrets and configuration**
- [ ] No secret in code, tests, fixtures, docs, or screenshots; `.env` is git-ignored; `.env.example` holds placeholders only.
- [ ] New env vars are documented in `.env.example` with safe defaults; production secrets live only in GitHub/Render/Vercel secret stores.

**3.5 Network and outbound calls**
- [ ] Outbound URLs come from env configuration only (`SIM_BASE_URL`, `PREDICTOR_URL`, LLM base URL) — **never** from user input (no SSRF).
- [ ] Every outbound call has a timeout, bounded retries with jitter, and a breaker.
- [ ] CORS allows only the configured frontend origin.

**3.6 Dependencies and containers**
- [ ] No new dependency — or it passed §9 vetting and is pinned.
- [ ] Containers run as non-root, no `:latest` for runtime images, no secrets baked into images.

**3.7 LLM features (if touched)**
- [ ] Prompt contains only structured fields generated by us; no secrets; free text treated as data.
- [ ] Output is parsed against a schema; failures fall back to the template; calls are timeout-bound, cached, and cost-capped.
- [ ] The LLM never decides, dispatches, or calls tools.

**3.8 Logging and observability**
- [ ] Logs are structured, carry request/tick/recommendation IDs, and are redacted (no token, no Authorization header, no full request bodies containing secrets).

---

## 4. Automated gates

| Gate | Tool | Runs | Blocks merge? |
|---|---|---|---|
| Secret scan | gitleaks (`.gitleaks.toml`) | CI `security` job + pre-PR if installed | **Yes** |
| Static security rules | `ruff --select S` (bandit rules; `S311` ignored: retry jitter isn't security) | CI + `make security` | **Yes** |
| Python dependency audit | `pip-audit -r requirements.txt` | CI + `make security` | **Yes** once the waiver in §5 expires (currently `continue-on-error`) |
| Node dependency audit | `npm audit --omit=dev --audit-level=high` | CI + `make security` | **Yes** |
| Architecture contracts | import-linter (`.importlinter`) | CI `backend` job | **Yes** |
| Dependency updates | Dependabot (pip, npm, actions, docker) weekly | GitHub | PRs reviewed like any other |
| Optional: CodeQL | GitHub code scanning (default setup) | GitHub | **Yes** if enabled |
| Optional: image scan | Trivy on built images | nightly | No (report) |

**Measured baseline (2026-11-20, colleague repo):** `ruff S` → 1 finding (`S311`, benign); `npm audit` (prod) → 0; **`pip-audit` → 14 advisories in `starlette 0.46.2`** (pulled by `fastapi 0.115.12`; fix versions up to 1.3.1) — remediation tracked as **F-003**.

---

## 5. Findings, severity, and waivers

| Severity | Examples | Action | Time limit |
|---|---|---|---|
| **Critical** | leaked secret, auth bypass on approve/dispatch, RCE, injection | stop work; fix or revert immediately; rotate secrets | same day, blocks everything |
| **High** | reachable vulnerable dependency, missing authz on a mutating route, internals leaked in errors | block the PR; fix in the PR | before merge |
| **Medium** | missing rate limit, weak validation, non-reachable vulnerable dep | fix in PR or open a tracked issue | within the sprint / before freeze |
| **Low** | hardening ideas, benign scanner noise | note; fix opportunistically | — |

**Waiver** (the only way to merge with an open High/Medium): a line in the PR **and** in `docs/risk-register.md` with *finding · why acceptable · owner · expiry date · tracking ID*. Waivers expire at the latest at **feature freeze (Wed 2026-11-25 18:00)**. Expired waiver ⇒ the gate becomes blocking.

**Active waivers**
| Finding | Owner | Expires | Tracking |
|---|---|---|---|
| `pip-audit`: starlette advisories (14) | backend lead | on merge of F-003, no later than Tue 2026-11-24 | F-003 |

---

## 6. Review policy

### 6.1 Roles
| Role | Responsibility |
|---|---|
| **Author** (human or agent) | small PR, complete template, evidence, responds to review within the SLA |
| **Reviewer** | someone who did **not** write the code; reads the diff, runs it when risk warrants, applies the checklist |
| **Code owner** | named in `.github/CODEOWNERS` for safety-critical paths; at least one must approve changes there |
| **Release owner** (rotating, one per day) | merges queue discipline, watches deploy verification, calls revert |

### 6.2 Required approvals
| Change | Approvals |
|---|---|
| Normal feature / fix / docs / chore | **1** |
| **Dispatch path** (`executor`, `validator`, idempotency, approval flow), security-sensitive code, auth, `sim_client`, CI/CD or deploy config, DB schema, locked-decision ADRs | **2**, one of them a code owner |
| Hotfix to `main` | **2** (fast lane, SLA 30 min), post-merge review follow-up within a day |
| After feature freeze (Wed 2026-11-25 18:00) | **2** and only for bug/regression fixes |

### 6.3 PR rules
- **Size:** ≲ 400 changed lines excluding lockfiles/generated files; larger ⇒ split or justify in the PR.
- **Template** fully filled; CI green **before** requesting review.
- **SLA (hackathon):** first review response within **2 working hours**; author responds to comments within 2 hours; a PR untouched for 4 hours is escalated to the release owner.
- **Rotation:** reviewers rotate so every module has at least two people who know it (cross-review is how we avoid a single point of knowledge).

### 6.4 Reviewer checklist
1. **Correct & scoped:** does it do what the acceptance criteria say — and only that?
2. **Tests:** are acceptance criteria each proven by a test? Do tests assert behavior? Right levels for the change type (plan §4.3)? Coverage on changed lines ≥ 85 % (dispatch path ≥ 90 %)?
3. **Safety invariants intact** (plan §8): human decision, fresh re-validation, stale blocks dispatch, in-transit ≠ inventory, idempotency, headroom accounting.
4. **Resilience:** timeout + retry + breaker + degraded behavior for each new external call; recovery shown.
5. **Security:** §3 checklist ticked and plausible; no secrets; authz on mutations; parameterized SQL.
6. **Observability:** metrics/logs added; degraded state visible to the operator.
7. **Architecture:** `.importlinter` kept; no new layer violations; no new dependency without justification.
8. **Simplicity:** the simplest design that works; no speculative abstraction; readable names.
9. **Docs/evidence:** spec updated, real output pasted, PROGRESS entry, `.env.example` updated.

### 6.5 Comment conventions
- Prefix: **`blocker:`** (must fix) · **`question:`** · **`suggestion:`** · **`nit:`** (optional). Only `blocker:` stops approval.
- Be specific and kind: say what and why, offer a fix. Resolve every thread before merge (branch protection enforces it).

### 6.6 Agent-authored code
- A human **reads the whole diff** before approving — "the agent said it passes" is not review.
- An agent **never approves, merges, or deploys** its own PR. A *second agent review pass* is encouraged as an extra check and never counts as an approval.
- Agent PRs must include the session end report (plan §7) and the evidence table.
- Anything touching a safety invariant gets the 2-approval path even if small.

---

## 7. Merge, branches, freeze, hotfix
- **Branch protection on `main`** (`.github/branch-protection.json`): PR required · required checks `backend`, `db-integration`, `frontend`, `security`, `compose-smoke` · up-to-date branch required · linear history · conversations resolved · no force-push, no deletion · applies to admins.
- **Merge = squash**; title `type(F-###): summary`; delete the branch.
- **Never merge red.** Red `main` ⇒ revert first, investigate second.
- **Hotfix:** `hotfix/F-###-name`, fast lane (§6.2), include a regression test, post-mortem note in `docs/PROGRESS.md`.
- **Feature freeze: Wed 2026-11-25 18:00.** After that: bug/regression fixes only, 2 approvals, demo rehearsal on a tagged commit; the delivery tag is created Thu morning.
- **Release tags:** `sprint-N` at sprint ends; `v1.0.0` for the submission.

---

## 8. Secrets and incident handling
- **Where secrets live:** local `.env` (git-ignored) · GitHub Actions secrets/variables · Render env vars (`sync: false`) · Vercel env vars. Never in chat, issues, screenshots, or commits.
- **Rotation:** change `OPERATOR_TOKEN` (≥ 32 random chars) for any shared environment before the demo; rotate any key that appeared anywhere it shouldn't.
- **If a secret leaks:** (1) revoke/rotate it immediately, (2) remove it from the repo *and* history if pushed (`git filter-repo`/GitHub support), (3) check logs for use, (4) write a 3-line note in `docs/risk-register.md`. Rotation comes first — deleting the commit is not remediation.
- **Local defaults** (`change-me`, `fuel-local`, Grafana demo password) are for local compose only; startup should refuse the default token when `ENV` is not `local` (backlog F-013).

---

## 9. Dependency and skill policy
1. **Pin** exact versions (already the repo's practice). No unpinned `latest` for runtime images or libraries.
2. **Adding** a dependency requires: why the standard library/existing deps aren't enough · maintainer/activity check · license compatible (MIT/BSD/Apache preferred) · `pip-audit`/`npm audit` clean · note in the PR.
3. **Updating** a pinned security-relevant package (FastAPI/Starlette, asyncpg, pydantic, httpx) must run the full test pyramid; never mix a bump with feature work.
4. **Agent skills** are code with shell access: follow `SKILLS.md` §2 (source, installs, read `SKILL.md` and scripts, pin, install via PR).
5. Dependabot PRs follow the normal review path (1 approval; 2 for the packages in rule 3).

---

## 10. Data, privacy, auditability
- **Data:** only simulator data and our derived artifacts (snapshots, forecasts, recommendations, decisions, audit). No PII. Retention: prune old snapshots; the audit trail (`decisions`, integration events) is kept for the whole run.
- **Auditability:** every dispatch is traceable *recommendation → decision (actor, time, reason) → stored request body + idempotency key → simulator allocation id → outcome*. With a single shared token the actor is a self-declared label (`X-Operator-Name`) — documented limitation; per-operator tokens are backlog F-013.
- **Explainability duty:** every recommendation stores signals, constraints checked, alternatives, expected impact, and confidence so a reviewer can reconstruct *why*.
