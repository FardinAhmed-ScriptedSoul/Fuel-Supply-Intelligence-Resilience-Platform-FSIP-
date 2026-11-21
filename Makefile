# Hub convenience targets. Every target just calls a script, so `make` is optional on Windows.
.PHONY: help setup check code skills apply-kit kit-dry where list report update sprint eod selftest

help:
	@echo "setup check code skills | apply-kit kit-dry | where list | report update sprint eod | selftest"

setup:    ; bash scripts/setup.sh
check:    ; bash scripts/setup.sh --check
code:     ; bash scripts/setup.sh --code
skills:   ; bash scripts/setup.sh --skills
apply-kit: ; bash scripts/apply-kit.sh
kit-dry:  ; bash scripts/apply-kit.sh --dry-run
where:    ; bash scripts/plan.sh where
list:     ; bash scripts/plan.sh list
report:   ; bash scripts/report.sh daily
update:   ; bash scripts/report.sh update
sprint:   ; bash scripts/report.sh sprint
eod:      ; bash scripts/eod.sh

selftest:
	bash scripts/plan.sh where
	bash scripts/report.sh daily --stdout --no-gh | head -20

# --- fuel-platform kit additions ---
# Append to the existing Makefile (keep the existing up/down/test/lint/smoke targets).
SIM_URL ?= http://localhost:8000
PYPATH  := backend:backend/shared:intel/predictor

.PHONY: feature pre-pr pre-pr-fast test-unit test-int test-acc test-e2e lint-arch security load sim-reset sim-step sim-pause

feature: ## make feature ID=F-005 NAME=predictor-fallback [TYPE=feat]
	@./scripts/new-feature.sh $(ID) $(NAME) $(or $(TYPE),feat)

pre-pr: ## full local gate before opening a PR
	@./scripts/pre-pr-check.sh

pre-pr-fast: ## backend-only gate (no web build, no compose)
	@./scripts/pre-pr-check.sh --fast

test-unit: ## unit + scenario-contract tests
	pytest tests/unit tests/scenarios -q

test-int: ## integration tests (needs DATABASE_URL / SIM_BASE_URL for the DB ones)
	pytest tests/integration -q

test-acc: ## acceptance scenarios (needs the stack: make up)
	pytest tests/acceptance -q

test-e2e: ## Playwright journeys (needs the stack: make up)
	npm --prefix web run e2e

lint-arch: ## import-linter architecture contracts
	PYTHONPATH=$(PYPATH) lint-imports

security: ## local security gates
	ruff check --select S --ignore S311 --exclude tests backend intel
	pip-audit -r requirements.txt
	npm --prefix web audit --omit=dev --audit-level=high

load: ## k6 load test (script: deploy/k6/load.js)
	docker run --rm --network host -v $$PWD/deploy/k6:/scripts grafana/k6 run /scripts/load.js

sim-reset: ## deterministic tests: wipe simulator state
	curl -fsS -X POST $(SIM_URL)/admin/reset

sim-step: ## advance one tick
	curl -fsS -X POST $(SIM_URL)/admin/step

sim-pause:
	curl -fsS -X POST $(SIM_URL)/admin/pause

