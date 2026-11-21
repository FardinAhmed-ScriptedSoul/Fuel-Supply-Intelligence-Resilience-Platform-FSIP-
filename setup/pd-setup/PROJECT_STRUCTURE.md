# PROJECT STRUCTURE — the hub (`pd/`) and the code repo

| | |
|---|---|
| **Status** | v1.0 · 2026-11-20 |
| **Decision** | `pd/` is a **hub** (docs, planning, reports, tooling). The product code lives in the **trunk code repo** (the colleague repo `thunderstorm009/fuel_simulator`), cloned into `pd/code/` and **never committed into the hub**. |

## 1. Why a hub plus a separate code repo (and not one big repo)

| Option | Verdict | Why |
|---|---|---|
| **A. Hub + trunk code repo cloned under `code/` (chosen)** | ✔ | 9 people already collaborate in the trunk repo; its PRs, CI and branch protection are where the team works. The hub keeps *your* planning, daily reports and docs without disturbing anyone, and nothing in it can break the product build. Docs reach the code repo through reviewed PRs (`scripts/apply-kit.sh`). |
| B. Copy the trunk's code into `pd/` | ✘ | You would lose its history and ownership, duplicate CI, and fork the team's work. |
| C. Git submodule | ✘ (for now) | Windows + submodules + 9 people = friction for no benefit; a plain gitignored clone is simpler. |
| D. Put everything in the code repo | ✘ | Daily reports, personal planning and scratch evidence would pollute the product repo and PR history. |

**Config:** `planning/config.json` holds the code repo path and URL. If you later decide the code lives in `pd/` itself, set `"path": "."` and every script keeps working.

## 2. The hub

```
pd/                                  <- your repo, branch `docs` today
├── README.md                        hub quickstart (daily routine, commands)
├── PROJECT_STRUCTURE.md             this file
├── CLAUDE.md                        short rules for agent sessions opened in the HUB
├── Makefile                         convenience targets (setup, report, plan, apply-kit ...)
├── .gitignore  .gitattributes  .editorconfig  .vscode/    hygiene (LF endings for *.sh, VS Code defaults)
│
├── problem/                         the brief - READ ONLY (never edit)
│   ├── BUP_CSE_FEST_2026_Participant_Facing_Hackathon_Draft.pdf
│   ├── BUP_Fuel_Supply_Simulator_Integration_Guide_Final.pdf
│   └── statement.md
│
├── systemdesign/                    architecture, decided
│   ├── FINAL_SYSTEM_DESIGN.md       locked decisions D1-D22, resilience contract, plan
│   ├── ARCHITECTURE.md              diagrams, sequences, as-built mapping
│   └── archive/PROPOSED_SYSTEM_DESIGN.md   superseded proposal (kept for the reasoning)
│
├── implementation/                  HOW we build (copied to the code repo's docs/process/)
│   ├── SPRINTS.md                   the 5-sprint plan (human-readable)
│   ├── BACKLOG.md                   features, branches, acceptance criteria
│   ├── FEATURE_IMPLEMENTATION_PLAN.md   the per-feature playbook (branch -> tests -> gates -> merge)
│   ├── SECURITY_AND_REVIEW_POLICY.md
│   └── PIPELINE.md
│
├── claude/                          agent configuration (copied to the code repo)
│   ├── CLAUDE.md                    -> code repo root (Claude Code reads it there)
│   ├── SKILLS.md                    -> code repo root
│   └── skills/<name>/SKILL.md       project skills -> code repo .claude/skills/   (first: simulator-contract)
│
├── starter-kit/                     files that land in the code repo root (F-002)
│   ├── .github/{workflows,ISSUE_TEMPLATE,pull_request_template.md,CODEOWNERS,dependabot.yml,branch-protection.json}
│   ├── .importlinter  .gitleaks.toml  requirements-ci.txt  Makefile.additions
│   ├── scripts/{new-feature.sh,pre-pr-check.sh}
│   ├── docs/{features/_TEMPLATE.md,adr/_TEMPLATE.md}
│   └── deploy/{render.yaml,k6/load.js}
│
├── planning/                        machine-readable plan - the scripts' source of truth
│   ├── config.json                  repos, report options
│   ├── sprints.json                 S1-S5 dates, goals, exit criteria, milestones
│   ├── backlog.json                 20 features: id, branch, priority, sprint, dependencies
│   └── status.json                  live status, history, blockers, notes   (YOU update this)
│
├── scripts/                         tooling
│   ├── setup.sh                     installs everything (idempotent)
│   ├── apply-kit.sh                 puts the kit + docs into the code repo on branch chore/F-002-ci-hardening
│   ├── plan.sh                      update status / blockers / notes
│   ├── report.sh                    daily / update / sprint reports
│   ├── eod.sh                       end-of-day: reports + copy the update message
│   └── devtools/{common.py,plan.py,report.py}     Python standard library only
│
├── reports/                         GENERATED (committed - it is your audit trail)
│   ├── daily/YYYY-MM-DD.md  YYYY-MM-DD.update.txt
│   └── sprint/S1.md ... S5.md
│
├── evidence/                        screenshots, recordings, exported test output (moved to the code repo's docs/evidence at the end)
│
└── code/                            GITIGNORED working clones
    ├── fuel-platform/               trunk code repo  (clone of thunderstorm009/fuel_simulator)
    └── ref-fsip/                    read-only reference (IamAsif53/Fuel-Management-System)
```

**Your current folders map 1:1** (`claude/`, `implementation/`, `problem/`, `systemdesign/`); the new ones are `planning/`, `reports/`, `evidence/`, `starter-kit/`, `scripts/`, `code/`.

## 3. The code repo after F-002 (what the team sees)

```
fuel-platform/
├── CLAUDE.md  SKILLS.md  README.md  Makefile  docker-compose.yml  .env.example
├── .github/            workflows (ci, nightly, deploy-verify), PR template, CODEOWNERS, dependabot, branch protection JSON
├── .claude/skills/     project skills (simulator-contract ...)
├── .importlinter  .gitleaks.toml  requirements*.txt  pyproject.toml
├── backend/{shared/core, api, worker}    intel/predictor    web/    observability/    deploy/
├── tests/{unit,integration,scenarios,acceptance}        web/e2e/
├── scripts/            smoke.sh, new-feature.sh, pre-pr-check.sh
└── docs/
    ├── design/         FINAL_SYSTEM_DESIGN.md, ARCHITECTURE.md
    ├── process/        SPRINTS, BACKLOG, FEATURE_IMPLEMENTATION_PLAN, SECURITY_AND_REVIEW_POLICY, PIPELINE
    ├── features/       one spec per feature (F-###-name.md)      adr/   decisions
    ├── PROGRESS.md  sim-findings.md  simulator-contract.md  risk-register.md ...   (already in the trunk)
    └── evidence/       final proof pack
```

## 4. Where things go (quick rules)

| I produce... | It goes in... |
|---|---|
| A design/process doc | the hub (`systemdesign/` or `implementation/`), then `apply-kit.sh` copies it to the code repo |
| Product code, tests, CI | the **code repo only**, on a feature branch `type/F-###-name` |
| A feature spec | code repo `docs/features/F-###-name.md` (created by `make feature`) |
| Daily/sprint reports | hub `reports/` (generated) |
| Status, blockers, decisions of the day | `scripts/plan.sh ...` (feeds the reports) |
| Screenshots / recordings / raw test output | hub `evidence/` first; curated copies to the code repo's `docs/evidence/` before delivery |
| A skill we write | hub `claude/skills/<name>/` -> code repo `.claude/skills/` |

## 5. Branches (hub vs code repo)
- **Hub:** `main` is stable docs; today you are on `docs`. Merge to `main` when the docs are reviewed. Daily reports can be committed straight to `docs` (they are generated, single author).
- **Code repo:** trunk-based with `main` protected; every change is a branch `type/F-###-kebab-name` -> PR -> squash merge (details: `implementation/FEATURE_IMPLEMENTATION_PLAN.md`).

## 6. What is committed vs ignored
| Committed (hub) | Ignored (hub) |
|---|---|
| everything above except the right column | `code/` (clones) · `.venv/` · `node_modules/` · caches · `*.env` / `.env` (but `.env.example` is allowed) · OS/editor junk |
