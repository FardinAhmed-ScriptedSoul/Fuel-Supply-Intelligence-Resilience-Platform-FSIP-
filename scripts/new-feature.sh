#!/usr/bin/env bash
# Create a feature branch + spec doc skeleton.
# Usage: scripts/new-feature.sh F-005 predictor-fallback [feat|fix|refactor|chore|docs|test|hotfix]
set -euo pipefail

fail() { echo "error: $*" >&2; exit 1; }
usage() { echo "usage: $0 F-### kebab-name [type]   (type: feat|fix|refactor|chore|docs|test|hotfix, default feat)"; exit 2; }

ID="${1:-}"; NAME="${2:-}"; TYPE="${3:-feat}"
[[ -n "$ID" && -n "$NAME" ]] || usage
[[ "$ID" =~ ^F-[0-9]{3}$ ]] || fail "ID must look like F-005"
[[ "$NAME" =~ ^[a-z0-9]+(-[a-z0-9]+){0,5}$ ]] || fail "NAME must be kebab-case, max 6 words (e.g. predictor-fallback)"
case "$TYPE" in feat|fix|refactor|chore|docs|test|hotfix) ;; *) fail "unknown type '$TYPE'";; esac

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not inside a git repository"
[[ -z "$(git status --porcelain)" ]] || fail "working tree not clean; commit or stash first"

BASE="${BASE_BRANCH:-main}"
BRANCH="${TYPE}/${ID}-${NAME}"
DOC="docs/features/${ID}-${NAME}.md"
TEMPLATE="docs/features/_TEMPLATE.md"
[[ -f "$TEMPLATE" ]] || fail "missing $TEMPLATE (copy the starter kit first)"

if git remote get-url origin >/dev/null 2>&1; then
  git fetch origin --prune
  START="origin/${BASE}"
  git rev-parse --verify --quiet "$START" >/dev/null || fail "no $START"
else
  echo "note: no 'origin' remote; branching from local $BASE" >&2
  START="$BASE"
  git rev-parse --verify --quiet "$START" >/dev/null || fail "no local branch $BASE"
fi

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then fail "branch ${BRANCH} already exists"; fi
if ls docs/features/${ID}-*.md >/dev/null 2>&1; then fail "a spec for ${ID} already exists"; fi

# read the template BEFORE switching branches (the base branch may not contain it yet)
TEMPLATE_BODY="$(cat "$TEMPLATE")"
git checkout -q -b "$BRANCH" "$START"
mkdir -p "$(dirname "$DOC")"
printf '%s\n' "$TEMPLATE_BODY" | sed -e "s|__ID__|${ID}|g" -e "s|__NAME__|${NAME}|g" -e "s|__BRANCH__|${BRANCH}|g" \
    -e "s|__DATE__|$(date +%F)|g" > "$DOC"
git add "$DOC"
git commit -q -m "docs(${ID}): add feature spec skeleton"

cat <<MSG
Created branch: ${BRANCH}
Spec skeleton:  ${DOC}

Next:
  1. Fill sections 1-5 of the spec (goal, acceptance criteria, design, failure modes).
  2. Write failing tests first (red), then implement (green).
  3. make pre-pr   -> paste evidence into section 7 of the spec
  4. git push -u origin ${BRANCH} && open a PR (template will load)
MSG
