#!/usr/bin/env bash
# Local gate that mirrors CI. Usage: scripts/pre-pr-check.sh [--fast] [--no-int]
#   --fast    backend only (skip web build/tests and docker compose)
#   --no-int  skip integration tests
set -uo pipefail

FAST=0; NOINT=0
for a in "$@"; do
  case "$a" in
    --fast) FAST=1;;
    --no-int) NOINT=1;;
    *) echo "unknown flag $a"; exit 2;;
  esac
done

export PYTHONPATH="backend:backend/shared:intel/predictor${PYTHONPATH:+:$PYTHONPATH}"
NAMES=(); RESULTS=()
record() { NAMES+=("$1"); RESULTS+=("$2"); }
run() {
  local name="$1"; shift
  echo; echo "=== $name ==="
  if "$@"; then record "$name" PASS; else record "$name" FAIL; fi
}
skip() { record "$1" "SKIP ($2)"; }
have() { command -v "$1" >/dev/null 2>&1; }

# 1. branch + spec hygiene
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [[ "$branch" =~ ^(feat|fix|refactor|chore|docs|test|hotfix)/F-[0-9]{3}-[a-z0-9-]+$ ]]; then
  record "branch name" PASS
  id="$(echo "$branch" | sed -E 's|^[a-z]+/(F-[0-9]{3})-.*|\1|')"
  if ls docs/features/${id}-*.md >/dev/null 2>&1; then record "feature spec exists" PASS
  else record "feature spec exists" "FAIL (docs/features/${id}-*.md missing)"; fi
else
  record "branch name" "FAIL ($branch; expected type/F-###-kebab-name)"
fi

# 2. python static checks
run "ruff check" ruff check .
run "ruff format --check" ruff format --check .
if have lint-imports; then run "architecture contracts" lint-imports
else skip "architecture contracts" "pip install -r requirements-ci.txt"; fi

# 3. tests
run "unit + scenario tests" python -m pytest tests/unit tests/scenarios -q
if [[ $NOINT -eq 1 ]]; then skip "integration tests" "--no-int"
else run "integration tests" python -m pytest tests/integration -q; fi
if [[ -d tests/acceptance ]]; then
  if [[ -n "${ACCEPTANCE:-}" ]]; then run "acceptance tests" python -m pytest tests/acceptance -q
  else skip "acceptance tests" "set ACCEPTANCE=1 with the stack running"; fi
fi

# 4. security
run "bandit rules (ruff S)" ruff check --select S --ignore S311 --exclude tests backend intel
if have pip-audit; then run "pip-audit" pip-audit -r requirements.txt
else skip "pip-audit" "not installed"; fi
if have gitleaks; then run "gitleaks" gitleaks detect --no-banner --redact --config .gitleaks.toml
else skip "gitleaks" "not installed (CI runs it)"; fi
if [[ -f .env ]]; then
  if git check-ignore -q .env; then record ".env is git-ignored" PASS
  else record ".env is git-ignored" "FAIL (.env would be committed)"; fi
fi

# 5. web + compose
if [[ $FAST -eq 1 ]]; then
  skip "web typecheck/test/build" "--fast"; skip "docker compose config" "--fast"
else
  if [[ -d web ]] && have npm; then
    run "web typecheck" npm --prefix web run typecheck
    run "web unit tests" npm --prefix web run test
    run "web build" npm --prefix web run build
    run "npm audit (high)" npm --prefix web audit --omit=dev --audit-level=high
  else skip "web checks" "npm or web/ missing"; fi
  if have docker; then run "docker compose config" docker compose config -q
  else skip "docker compose config" "docker missing"; fi
fi

echo; echo "================ pre-PR summary ================"
fail=0
for i in "${!NAMES[@]}"; do
  printf '%-30s %s\n' "${NAMES[$i]}" "${RESULTS[$i]}"
  [[ "${RESULTS[$i]}" == FAIL* ]] && fail=1
done
echo "================================================"
if [[ $fail -eq 1 ]]; then echo "RESULT: FAIL - fix the items above before opening a PR"; exit 1; fi
echo "RESULT: OK - paste this summary into the PR / spec evidence section"
