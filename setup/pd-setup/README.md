# Fuel Supply Intelligence & Resilience Platform — project hub

Docs, planning, reports and tooling for the BUP CSE Fest 2026 fuel-supply platform. **Deadline Thu 26 Nov 2026** (feature freeze Wed 25 Nov 18:00). The product code lives in the trunk repo cloned under `code/` — see [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

> **SIMULATED:** everything here operates on simulator data. No real fuel infrastructure is touched.

## 1. First-time setup (Git Bash on Windows)
```bash
bash scripts/setup.sh                 # report + install what is missing (winget); close and reopen Git Bash afterwards
bash scripts/setup.sh --check         # verify
bash scripts/setup.sh --code          # clone the trunk repo into code/fuel-platform, create .venv, install deps, create .env
bash scripts/setup.sh --skills        # optional: find-skills, Emil Kowalski, Impeccable (vet them first: claude/SKILLS.md)
gh auth login                         # once; lets reports include PRs and CI status
```
Docker Desktop is never installed unless you add `--docker` (it needs admin rights and WSL2); otherwise install it from docker.com.

## 2. Put the process into the code repo (feature F-002)
```bash
bash scripts/apply-kit.sh --dry-run   # see what would be copied
bash scripts/apply-kit.sh             # branch chore/F-002-ci-hardening + commit in code/fuel-platform (never pushes)
```
Then follow the "Next" list it prints (CODEOWNERS handles, pyproject tweaks, PR, branch protection).

## 3. Daily routine
```bash
bash scripts/plan.sh where                                     # sprint, day, days to freeze/deadline
bash scripts/plan.sh set F-001 in_progress --owner "<you>"     # when you start a feature
bash scripts/plan.sh blocker add "what blocks you" --feature F-001
bash scripts/plan.sh set F-001 done --pr <PR URL> --note "what was proven"
bash scripts/plan.sh note add "start F-005 first" --kind next  # tomorrow's plan (also: decision | risk | note)
bash scripts/eod.sh                                            # daily report + short update (copied to clipboard)
```
Outputs: `reports/daily/YYYY-MM-DD.md` (full), `reports/daily/YYYY-MM-DD.update.txt` (paste to your mentor — Completed / In progress / Blockers / Next), `reports/sprint/S#.md` (on a sprint's last day, or `bash scripts/report.sh sprint --sprint S2`).
Useful flags: `--no-tests` (faster), `--date yesterday`, `--no-gh`, `--stdout`.

## 4. Where things are
| Need | Open |
|---|---|
| The 5-sprint plan | [implementation/SPRINTS.md](implementation/SPRINTS.md) |
| What to build, in what order | [implementation/BACKLOG.md](implementation/BACKLOG.md) |
| How to build/test/merge a feature | [implementation/FEATURE_IMPLEMENTATION_PLAN.md](implementation/FEATURE_IMPLEMENTATION_PLAN.md) |
| Security and review rules | [implementation/SECURITY_AND_REVIEW_POLICY.md](implementation/SECURITY_AND_REVIEW_POLICY.md) |
| CI/CD, deploy, rollback | [implementation/PIPELINE.md](implementation/PIPELINE.md) |
| Locked design decisions | [systemdesign/FINAL_SYSTEM_DESIGN.md](systemdesign/FINAL_SYSTEM_DESIGN.md) |
| Diagrams and sequences | [systemdesign/ARCHITECTURE.md](systemdesign/ARCHITECTURE.md) |
| Agent rules and skills | [claude/CLAUDE.md](claude/CLAUDE.md), [claude/SKILLS.md](claude/SKILLS.md) |
| The brief | `problem/` |

## 5. Troubleshooting (Windows / Git Bash)
- **`$'\r': command not found`** — a script has CRLF endings. `.gitattributes` forces LF; run `git add --renormalize .` and re-checkout the file.
- **`python` opens the Microsoft Store** — the tools skip that stub automatically; install Python via `bash scripts/setup.sh` and reopen the shell. Turn off the Store aliases under *Settings → Apps → Advanced app settings → App execution aliases*.
- **Tool installed but "missing"** — Git Bash caches PATH; close and reopen it.
- **`make` not found** — optional; run the scripts directly, or `winget install ezwinports.make`.
- **PR/CI sections empty in reports** — `gh auth login`, or ignore (the report lists the gap at the bottom).
