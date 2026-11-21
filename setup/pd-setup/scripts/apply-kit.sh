#!/usr/bin/env bash
# Apply the starter kit + process docs + skills from the hub to the CODE repo, on its own branch (feature F-002).
#
#   bash scripts/apply-kit.sh              create branch chore/F-002-ci-hardening in the code repo, copy files, commit
#   bash scripts/apply-kit.sh --dry-run    show what would be copied/overwritten, change nothing
#   bash scripts/apply-kit.sh --branch NAME   use another branch name
#   bash scripts/apply-kit.sh --no-commit  copy and stage but do not commit
#
# It never pushes, never touches .env, and refuses to run on a dirty working tree.
# Mapping (hub -> code repo):
#   starter-kit/**              -> repo root (.github/, .importlinter, .gitleaks.toml, requirements-ci.txt, scripts/, deploy/, docs/features, docs/adr)
#   starter-kit/Makefile.additions -> appended to Makefile (once, marker-guarded)
#   systemdesign/*.md           -> docs/design/
#   implementation/*.md         -> docs/process/
#   claude/CLAUDE.md, SKILLS.md -> CLAUDE.md, SKILLS.md (repo root)
#   claude/skills/*             -> .claude/skills/

set -o pipefail
HUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/_py.sh
source "$HUB/scripts/_py.sh"

DRY=0; COMMIT=1; BRANCH="chore/F-002-ci-hardening"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1;;
    --no-commit) COMMIT=0;;
    --branch) shift; BRANCH="${1:-}";;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
  shift
done

find_python || { echo "error: no working Python 3.9+ (run scripts/setup.sh)" >&2; exit 1; }
CODE_REL="$("${PY[@]}" -c "import json;c=json.load(open('$HUB/planning/config.json',encoding='utf-8'));print(next(r for r in c['repos'] if r.get('primary'))['path'])")"
CODE="$HUB/$CODE_REL"

[ -d "$CODE/.git" ] || { echo "error: code repo not found at $CODE (run: bash scripts/setup.sh --code)" >&2; exit 1; }
[ -d "$HUB/starter-kit" ] || { echo "error: $HUB/starter-kit is missing" >&2; exit 1; }
[ -z "$(git -C "$CODE" status --porcelain)" ] || { echo "error: code repo working tree is not clean; commit or stash first" >&2; exit 1; }
[[ "$BRANCH" =~ ^(feat|fix|refactor|chore|docs|test|hotfix)/F-[0-9]{3}-[a-z0-9-]+$ ]] || { echo "error: branch name must look like chore/F-002-ci-hardening" >&2; exit 1; }

say() { printf '%s\n' "$*"; }
# plan: "src|dest" pairs (files only)
PLAN=()
add_tree() { # srcdir destprefix
  local src="$1" dest="$2" f rel
  [ -d "$src" ] || return 0
  while IFS= read -r -d '' f; do
    rel="${f#"$src"/}"
    PLAN+=("$f|$dest$rel")
  done < <(find "$src" -type f ! -name 'Makefile.additions' ! -name '.gitkeep' -print0)
}
add_tree "$HUB/starter-kit" ""
for f in "$HUB"/systemdesign/*.md;    do [ -f "$f" ] && PLAN+=("$f|docs/design/$(basename "$f")"); done
for f in "$HUB"/implementation/*.md;  do [ -f "$f" ] && PLAN+=("$f|docs/process/$(basename "$f")"); done
[ -f "$HUB/claude/CLAUDE.md" ] && PLAN+=("$HUB/claude/CLAUDE.md|CLAUDE.md")
[ -f "$HUB/claude/SKILLS.md" ] && PLAN+=("$HUB/claude/SKILLS.md|SKILLS.md")
add_tree "$HUB/claude/skills" ".claude/skills/"

say "Code repo: $CODE"
say "Branch:    $BRANCH"
NEW=0; CHANGED=0; SAME=0
for pair in "${PLAN[@]}"; do
  src="${pair%%|*}"; dest="${pair#*|}"
  if [ ! -e "$CODE/$dest" ]; then NEW=$((NEW+1)); say "  + new        $dest"
  elif cmp -s "$src" "$CODE/$dest"; then SAME=$((SAME+1))
  else CHANGED=$((CHANGED+1)); say "  ~ overwrite  $dest"; fi
done
say "Summary: $NEW new, $CHANGED overwritten, $SAME identical."
HAS_MARK=0; grep -q "fuel-platform kit additions" "$CODE/Makefile" 2>/dev/null && HAS_MARK=1
[ -f "$HUB/starter-kit/Makefile.additions" ] && { [ "$HAS_MARK" -eq 1 ] && say "Makefile: kit targets already present." || say "Makefile: kit targets will be appended."; }
[ "$DRY" -eq 1 ] && { say "(dry-run: nothing changed)"; exit 0; }

# --- branch
if git -C "$CODE" remote get-url origin >/dev/null 2>&1; then
  git -C "$CODE" fetch origin --prune || echo "warn: fetch failed; using local refs" >&2
  base="origin/main"; git -C "$CODE" rev-parse --verify --quiet "$base" >/dev/null || base="main"
else base="main"; fi
git -C "$CODE" rev-parse --verify --quiet "$base" >/dev/null || { echo "error: cannot find base branch $base" >&2; exit 1; }
if git -C "$CODE" show-ref --verify --quiet "refs/heads/$BRANCH"; then echo "error: branch $BRANCH already exists" >&2; exit 1; fi
git -C "$CODE" checkout -q -b "$BRANCH" "$base" || exit 1

# --- copy
for pair in "${PLAN[@]}"; do
  src="${pair%%|*}"; dest="${pair#*|}"
  mkdir -p "$(dirname "$CODE/$dest")"
  cp "$src" "$CODE/$dest"
done
if [ -f "$HUB/starter-kit/Makefile.additions" ] && [ "$HAS_MARK" -eq 0 ]; then
  { printf '\n# --- fuel-platform kit additions (from the hub starter kit) ---\n'; cat "$HUB/starter-kit/Makefile.additions"; } >> "$CODE/Makefile"
fi

# feature spec for F-002 from the template (placeholders filled)
SPEC="docs/features/F-002-ci-hardening.md"
if [ -f "$CODE/docs/features/_TEMPLATE.md" ] && [ ! -f "$CODE/$SPEC" ]; then
  sed -e 's|__ID__|F-002|g' -e 's|__NAME__|ci-hardening|g' -e "s|__BRANCH__|$BRANCH|g" -e "s|__DATE__|$(date +%F)|g" \
    "$CODE/docs/features/_TEMPLATE.md" > "$CODE/$SPEC"
fi
chmod +x "$CODE"/scripts/*.sh 2>/dev/null

git -C "$CODE" add -A
# Windows does not track the executable bit; record it explicitly
git -C "$CODE" update-index --chmod=+x scripts/new-feature.sh scripts/pre-pr-check.sh 2>/dev/null

if [ "$COMMIT" -eq 1 ]; then
  if git -C "$CODE" commit -q -m "chore(F-002): adopt starter kit, process docs and skills"; then say "Committed on $BRANCH."
  else echo "error: commit failed (is git user.name/user.email set?). Files are staged." >&2; exit 1; fi
else say "Staged (not committed)."; fi

REPO_SLUG="$(git -C "$CODE" remote get-url origin 2>/dev/null | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
cat <<MSG

Next (manual, F-002):
  1. Review the diff:      git -C $CODE_REL diff --stat $base...HEAD
  2. Edit .github/CODEOWNERS - replace every @REPLACE_* placeholder with real handles.
  3. pyproject.toml: set ruff target-version to py312; add pytest markers: db, sim, acceptance, slow.
  4. Fix the flaky wall-clock test tests/unit/test_risk.py::test_all_twelve_pairs_complete_under_fifty_milliseconds.
  5. Run:                  cd $CODE_REL && make pre-pr-fast
  6. Push + open the PR:   git push -u origin $BRANCH
  7. After the PR is merged, enable branch protection (needs admin rights on the repo):
       gh api -X PUT repos/${REPO_SLUG:-OWNER/REPO}/branches/main/protection --input .github/branch-protection.json
  8. Record progress:      bash scripts/plan.sh set F-002 review --pr <PR URL>
MSG
