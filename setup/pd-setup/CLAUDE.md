# CLAUDE.md — project hub (pd/)

This is the **hub**, not the product code. Product rules live in `claude/CLAUDE.md` (copied to the code repo root by `scripts/apply-kit.sh`). Open Claude Code **inside `code/fuel-platform`** for coding sessions; use this hub for docs, planning and reports.

## Rules in the hub
- `problem/` is read-only. Never edit the brief.
- Design/process docs: `systemdesign/`, `implementation/`, `claude/`. A change to a locked decision needs an ADR in the code repo's `docs/adr/` and an update of `systemdesign/FINAL_SYSTEM_DESIGN.md`.
- `planning/*.json` drive the scripts. Change status with `bash scripts/plan.sh ...`, not by hand; edit dates/scope only in `planning/sprints.json` and `planning/backlog.json` (keep `implementation/BACKLOG.md` in sync).
- `reports/` is generated: never hand-edit; add context with `plan.sh note|blocker` and regenerate (`bash scripts/report.sh all`).
- Never commit secrets, `.env`, `code/` or `.venv/`. Never run `docker compose down -v` without an explicit human instruction.
- Scripts must stay LF, shellcheck-clean, and runnable from Git Bash on Windows; Python tools use the standard library only.
- Report numbers must come from real data (git, gh, test runs). Never invent metrics; list gaps instead.
