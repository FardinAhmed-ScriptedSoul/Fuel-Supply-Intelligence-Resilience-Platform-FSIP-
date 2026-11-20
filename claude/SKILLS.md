# SKILLS.md — Skill set for the Fuel Supply Intelligence & Resilience Platform

| | |
|---|---|
| **Purpose** | Which skills we use, for which phase of work, how to find more *on demand*, and which project-specific skills we write ourselves |
| **Companions** | `CLAUDE.md` (always-on rules) · `FINAL_SYSTEM_DESIGN.md` · `ARCHITECTURE.md` |
| **Evidence labels** | ✅ **verified** = confirmed via search or present in this environment on 2026-11-20 · ⚠ **candidate** = plausible, discover/verify with `find-skills` before relying on it |

---

## 1. Mental model

- **`CLAUDE.md` = rules that always apply** (loaded every session). **A skill = knowledge loaded only when its description matches the task** (progressive disclosure).
- So: put *"never do X"* in `CLAUDE.md`; put *"how to do Y well"* in a skill.
- Every installed skill's name + description costs context on every session. **Budget: ≤ ~8 active skills per workspace.** More skills ⇒ more mis-triggering, not more capability.
- Skills committed to the repo (`.claude/skills/` or the agent's equivalent) reach all teammates. Treat adding one like adding a dependency: via PR, with review.

---

## 2. Discovery instead of manual installing: `find-skills`

You described a skill that, given the skill you need, finds appropriate ones. That is **`find-skills`** from the open skills ecosystem (✅ verified: published at `skills.sh/vercel-labs/skills/find-skills`; it drives the Skills CLI).

**Install once**
```bash
npx skills add vercel-labs/skills@find-skills        # per skills.sh convention: owner/repo@skill
npx skills list                                       # confirm it landed in the folder your agent reads
```
(If the exact form errors, copy the install command shown on the skills.sh page for `find-skills`.)

**Use it by describing the need**
```text
Use find-skills: I need a skill for load testing a FastAPI service with k6.
Use find-skills: React dashboard polling performance (stack: Vite, TanStack Query).
Use find-skills: GitHub Actions workflow with a Postgres service container.
```
Under the hood it runs `npx skills find <query>`, then should present each hit with what it does, the install command, and a skills.sh link. Other CLI verbs (✅): `npx skills add <owner/repo@skill>`, `npx skills check`, `npx skills update`, `npx skills init <name>` (scaffold your own).

### Vetting checklist (required before any install)
Third-party skills are instructions (sometimes scripts) your agent will follow with your repo and shell access. `find-skills` itself says not to recommend on search results alone. We therefore require:

| Check | Bar |
|---|---|
| Source | Prefer official orgs (Anthropic, Vercel, the tool's own vendor) or the named author |
| Popularity | Prefer ≥ ~1K installs; treat repos with < ~100 stars with skepticism (the skill's own guidance) |
| Read it | Open `SKILL.md` and any `scripts/` **before** install — look for network calls, `curl | sh`, credential access, broad file writes |
| Scope | Does it overlap a skill we already have? (see precedence in §4) Reject duplicates |
| Pin | Record `owner/repo@skill` + commit/version in §6 |
| PR | Installing into a shared folder happens in a PR with one reviewer |

---

## 3. Skill set by area

### 3.1 Design, UI and motion (frontend)

| Skill | Status | Install | Use it for | Don't use it for |
|---|---|---|---|---|
| **Impeccable** (`pbakaus/impeccable`) | ✅ | `npx impeccable install` · alt: `npx skills add pbakaus/impeccable` · Claude Code plugin: `/plugin marketplace add pbakaus/impeccable` | Design authority: `/impeccable init` (sets design context), then `critique`, `audit`, `polish`, `harden`, `typeset`, `layout`, `colorize`, `adapt`, `clarify`, `distill`, `animate`, `optimize`; also `npx impeccable detect src/` to scan for AI-generated-design anti-patterns | `delight` and `overdrive` — an operations console should be calm, not flashy |
| **Emil Kowalski skills** (`emilkowalski/skills`) | ✅ | `npx skills add emilkowalski/skills` | `emil-design-eng` (broad design-engineering/motion judgment), `animate` (build an animation with sound curve/duration/properties), `review-animations` (strict review of motion code), `apple-design`, `ask-sonner` (toast troubleshooting — useful for approve/reject feedback) | Page-level visual design (that is Impeccable's job) |
| **frontend-design** (Anthropic) | ✅ present in this claude.ai environment; Impeccable states it builds on this skill | built in | Quick UI generation in claude.ai chat sessions | Claude Code repo work — Impeccable supersedes it; don't run both on the same task |
| React performance/best practices (`vercel-labs/agent-skills`) | ⚠ name varies in docs (`react-best-practices` / `vercel-react-best-practices`) | via `find-skills` | Review of data-fetching/render patterns in the SPA | Next.js-specific advice (we are a Vite SPA, D12) |

**Our motion/design rules for this product** (the skills implement them; we decide them): the console is dense and calm; motion only signals state change (new alert, status transition, approval result); ≈ ≤ 200 ms for UI feedback; honor `prefers-reduced-motion`; never animate numbers that refresh on each 2–5 s poll; color is for *risk state*, not decoration; the **SIMULATED DATA** tag and state banners are never animated away.

### 3.2 Testing

| Need | Skill | Status | Notes |
|---|---|---|---|
| Browser E2E / UI verification | Playwright-oriented skill (e.g., Anthropic's `webapp-testing` in `anthropics/skills`) | ⚠ verify | Pair with our Playwright suite on compose |
| Test-first workflow, systematic debugging | A TDD / debugging skill (e.g., the "superpowers" set) | ⚠ verify | Matches our rule: domain tests before persistence |
| Property-based and API-contract testing | none verified | ⚠ query: `hypothesis property testing python` | Otherwise rely on `CLAUDE.md` + our own skill (§5) |

### 3.3 Backend, data, delivery

| Need | How to get it | Status |
|---|---|---|
| FastAPI / pydantic / async patterns | `find-skills`: `fastapi async pydantic` | ⚠ |
| PostgreSQL 18 / schema & query review | `find-skills`: `postgres schema performance` | ⚠ |
| Docker / compose hardening | `find-skills`: `dockerfile multi-stage compose` | ⚠ |
| GitHub Actions authoring | `find-skills`: `github actions ci postgres service` | ⚠ |
| k6 load testing | `find-skills`: `k6 load testing` | ⚠ |
| Prometheus/Grafana dashboards | `find-skills`: `prometheus grafana dashboards` | ⚠ |
| Security review | `find-skills`: `security audit python fastapi` | ⚠ |

For each ⚠ row: run the query, apply the §2 checklist, and only then add the result to §6. If nothing passes, we rely on `CLAUDE.md` + our own skills — that is an acceptable outcome.

### 3.4 Deliverables (documents)

| Skill | Status | Use |
|---|---|---|
| `docx`, `pdf`, `pptx`, `xlsx` | ✅ present in this claude.ai environment | Final report, demo deck, evidence packs (load-test tables, bake-off results) |
| `skill-creator` | ✅ present here | Authoring/evaluating our own skills (§5) |

---

## 4. Precedence and conflicts

1. `CLAUDE.md` rules override any skill.
2. **One design authority:** Impeccable. Emil's skills handle *motion only*. `frontend-design` only in claude.ai chat.
3. If two skills disagree, the more specific one wins (`review-animations` beats `polish` on motion questions); record the resolution in a PR comment.
4. A skill that suggests breaking a locked decision (`D1–D22`) is ignored unless an ADR is opened.

---

## 5. Project-specific skills we write ourselves (highest value)

Generic skills know React and Postgres; **only we know this simulator.** These encode knowledge that otherwise lives in the head of whoever read the guide. Create with `skill-creator` (or `npx skills init <name>`), keep each `SKILL.md` short, put long reference in `references/`.

| Skill (folder) | Triggers when… | Contains |
|---|---|---|
| `simulator-contract` | touching the gateway, ingestion, dispatch, error handling | Endpoint list, both error envelopes, stale header, idempotency rules (200 vs 201 replay, cancel doesn't free key), the 9 validation rules in order, `demand-history` limit, SSE caveats, admin endpoints for tests |
| `fuel-domain-rules` | writing forecast/optimizer/constraint code | World constants (regions, depots, stations, routes, profiles, hour factors), invariants (in-transit ≠ inventory), formulas (baseline demand, time-to-stockout), worked examples |
| `acceptance-scenarios` | writing/running acceptance tests | Given/When/Then template, `/admin/events|faults` payloads, reset/step recipe, scenario catalog (shipment delay, demand spike, depot constraint, route disruption, combined, predictor down, malformed data, traffic spike) and pass criteria |
| `demo-runbook` | preparing or rehearsing the demo | The 14-step story, fault-injection order, expected UI states, rollback and reset commands |
| `pr-checklist` | opening/reviewing a PR | Definition of Done, 4-level test evidence, ADR trigger conditions |

**Skeleton (copy into `.claude/skills/simulator-contract/SKILL.md`)**
```markdown
---
name: simulator-contract
description: Use when writing or reviewing code that calls the BUP Fuel Supply Simulator (ingestion, SimulatorGateway, dispatch, error handling, admin-driven tests). Covers error envelopes, idempotency, validation order, stale data, and time model.
---
# Simulator contract
## Non-negotiables
- REST is truth; SSE is a hint → refetch after any event or gap.
- Parse both error shapes: {"error":…} (faults) and {"detail":{"code":…}} (domain).
- Idempotency: same key + same body replays (200 or 201); changed body → 409; cancel never frees a key.
## Validation order (first failure wins)
idempotency → not found → route mismatch → depot closed → station closed → route disrupted
→ route capacity → insufficient inventory → dispatch capacity → destination capacity
## Reference
See references/endpoints.md and references/faults.md for payloads and examples.
```

Rule of thumb: if the same correction is made twice in code review, it becomes a line in `CLAUDE.md` (if a rule) or a section of one of these skills (if know-how).

---

## 6. Installed-skills register (keep current; ≤ ~8 active)

| Skill | Source | Pinned version/commit | Scope | Installed by | Date |
|---|---|---|---|---|---|
| find-skills | `vercel-labs/skills` | _fill at install_ | user/global | | |
| impeccable | `pbakaus/impeccable` | _fill_ | project | | |
| emil-design-eng, animate, review-animations | `emilkowalski/skills` | _fill_ | project | | |
| simulator-contract, fuel-domain-rules, acceptance-scenarios, demo-runbook, pr-checklist | this repo | n/a | project | | |

---

## 7. Skill → pipeline phase map

| Phase | Skills in play |
|---|---|
| Design & docs | `skill-creator` (own skills), docx/pdf/pptx for deliverables |
| Backend slice | `simulator-contract`, `fuel-domain-rules`, FastAPI/Postgres skills if vetted |
| Frontend slice | Impeccable (`init` once, then `critique`/`harden`/`polish`), Emil (`animate`, `review-animations`), React best-practices if vetted |
| Test | `acceptance-scenarios`, TDD/Playwright skills if vetted |
| PR | `pr-checklist`, Impeccable `detect` in CI optionally |
| Demo | `demo-runbook` |

**Day-1 action list:** (1) install `find-skills`; (2) install Impeccable + Emil's skills in a PR; (3) scaffold the five project skills from §5 (start with `simulator-contract`); (4) run the §3.2–3.3 discovery queries and fill the register.
