#!/usr/bin/env bash
# One-command workstation setup for the Fuel Supply Intelligence & Resilience Platform.
# Primary target: Windows + Git Bash (winget). Also works on macOS (Homebrew) and Ubuntu/Debian (apt).
#
#   bash scripts/setup.sh                 report what is missing, ask, then install it
#   bash scripts/setup.sh --check         only report (no changes)
#   bash scripts/setup.sh --yes           no confirmation prompt
#   bash scripts/setup.sh --dry-run       print every command instead of running it
#   bash scripts/setup.sh --code          also clone + prepare the code repo (venv, pip, npm ci, .env)
#   bash scripts/setup.sh --reference     also clone the read-only reference repo
#   bash scripts/setup.sh --skills        also install agent skills (find-skills, Emil Kowalski, Impeccable)
#   bash scripts/setup.sh --docker        also try to install Docker (needs admin + WSL2/virtualization; may need a restart)
#   bash scripts/setup.sh --no-claude     skip the Claude Code CLI
#
# Safe to re-run: it installs only what is missing, never overwrites .env, never uses `docker compose down -v`.
# NOTE (Windows): a freshly installed tool is not on PATH in the *current* Git Bash window.
#       Close and reopen Git Bash, then run `bash scripts/setup.sh --check` again.

set -o pipefail

HUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY=0; ASSUME_YES=0; DRY_RUN=0; DO_CODE=0; DO_REF=0; DO_SKILLS=0; DO_DOCKER=0; NO_CLAUDE=0

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1;;
    --yes|-y) ASSUME_YES=1;;
    --dry-run) DRY_RUN=1;;
    --code) DO_CODE=1;;
    --reference) DO_REF=1;;
    --skills) DO_SKILLS=1;;
    --docker) DO_DOCKER=1;;
    --no-claude) NO_CLAUDE=1;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2;;
  esac
done

# --------------------------------------------------------------------------- output helpers
if [ -t 1 ]; then G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; Z=$'\033[0m'; else G=; Y=; R=; B=; Z=; fi
say()  { printf '%s\n' "$*"; }
head1(){ printf '\n%s== %s ==%s\n' "$B" "$*" "$Z"; }
ok()   { printf '  %s[ok]%s      %s\n' "$G" "$Z" "$*"; }
warn() { printf '  %s[warn]%s    %s\n' "$Y" "$Z" "$*"; }
bad()  { printf '  %s[missing]%s %s\n' "$R" "$Z" "$*"; }
run()  { if [ "$DRY_RUN" -eq 1 ]; then printf '  + %s\n' "$*"; return 0; fi; printf '  + %s\n' "$*"; "$@"; }

# --------------------------------------------------------------------------- platform
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) OS=windows;;
  Darwin) OS=macos;;
  Linux) OS=linux;;
  *) OS=unknown;;
esac
PM=none
if [ "$OS" = windows ] && command -v winget >/dev/null 2>&1; then PM=winget
elif [ "$OS" = macos ] && command -v brew >/dev/null 2>&1; then PM=brew
elif [ "$OS" = linux ] && command -v apt-get >/dev/null 2>&1; then PM=apt; fi

SUDO=""
if [ "$OS" = linux ] && [ "$(id -u 2>/dev/null)" != 0 ]; then SUDO="sudo"; fi

# --------------------------------------------------------------------------- version helpers
ver_ge() { # ver_ge have want  -> 0 when have >= want
  [ "$1" = "$2" ] && return 0
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}
first_ver() { grep -Eo '[0-9]+(\.[0-9]+)+' | head -n1; }

PYBIN=()   # chosen interpreter (array so "py -3.12" works)
pick_python() {
  local cand v best="" bestv=""
  for cand in "python3.12" "python3" "python" "py -3.12" "py -3"; do
    # shellcheck disable=SC2086
    v="$($cand --version 2>&1 | first_ver)"
    [ -z "$v" ] && continue
    # shellcheck disable=SC2086
    $cand -c 'import sys' >/dev/null 2>&1 || continue   # rejects the Windows Store stub
    if [ -z "$bestv" ] || ! ver_ge "$bestv" "$v"; then best="$cand"; bestv="$v"; fi
  done
  # shellcheck disable=SC2206
  [ -n "$best" ] && PYBIN=($best)
  PYVER="$bestv"
}

tool_version() {
  case "$1" in
    python) pick_python; printf '%s' "$PYVER";;
    git)    git --version 2>/dev/null | first_ver;;
    docker) docker --version 2>/dev/null | first_ver;;
    k6)     k6 version 2>/dev/null | first_ver;;
    gitleaks) gitleaks version 2>/dev/null | first_ver;;
    *)      "$1" --version 2>/dev/null | head -n1 | first_ver;;
  esac
}

# id|label|required(req/opt)|min version|winget id|brew pkg (cask: prefix)|apt packages ('-' = manual)|manual hint
TOOLS=(
  "git|Git|req|2.30|Git.Git|git|git|"
  "python|Python 3.12+|req|3.12|Python.Python.3.12|python@3.12|python3 python3-venv python3-pip|Linux: ensure python3.12 (deadsnakes or pyenv) if your distro is older"
  "node|Node.js 22+ (LTS) with npm|req|22|OpenJS.NodeJS.LTS|node@22|-|Linux: install via nvm or NodeSource (https://nodejs.org)"
  "gh|GitHub CLI (gh)|req|2.0|GitHub.cli|gh|gh|then run: gh auth login"
  "docker|Docker (with Compose v2)|req|20.10|Docker.DockerDesktop|cask:docker|docker.io docker-compose-v2|Install Docker Desktop (needs WSL2/virtualization, may need a restart): https://www.docker.com/products/docker-desktop/"
  "make|GNU make (optional)|opt|3.80|ezwinports.make|make|make|optional: every script also runs directly; or use choco install make"
  "k6|k6 load testing (optional)|opt|0.40|k6.k6|k6|-|https://grafana.com/docs/k6/latest/set-up/install-k6/ (CI runs k6 in Docker anyway)"
  "gitleaks|gitleaks secret scan (optional)|opt|8.0|Gitleaks.Gitleaks|gitleaks|-|https://github.com/gitleaks/gitleaks (CI runs it anyway)"
  "jq|jq (optional)|opt|1.6|jqlang.jq|jq|jq|"
  "claude|Claude Code CLI|opt|0.0|Anthropic.ClaudeCode|cask:claude-code|-|Linux/macOS/WSL: curl -fsSL https://claude.ai/install.sh | bash"
)

R_STATUS=(); R_VER=()

check_all() {
  local i id label req min v
  head1 "Platform"
  say "  OS: $OS   package manager: $PM   shell: bash ${BASH_VERSION%%(*}   hub: $HUB"
  [ "$PM" = none ] && warn "no supported package manager found (Windows: winget; macOS: brew; Linux: apt) - tools will be reported only"
  head1 "Tools"
  for i in "${!TOOLS[@]}"; do
    IFS='|' read -r id label req min _ _ _ _ <<<"${TOOLS[$i]}"
    [ "$id" = claude ] && [ "$NO_CLAUDE" -eq 1 ] && { R_STATUS[$i]=skip; R_VER[$i]=""; continue; }
    v="$(tool_version "$id")"
    R_VER[$i]="$v"
    if [ -z "$v" ]; then
      R_STATUS[$i]=missing; bad "$label ($req)"
    elif ! ver_ge "$v" "$min"; then
      R_STATUS[$i]=old; warn "$label: found $v, need >= $min"
    else
      R_STATUS[$i]=ok; ok "$label $v"
    fi
  done
  # extras that are not separate packages
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then ok "docker compose v2: $(docker compose version --short 2>/dev/null)"
    else warn "docker found but 'docker compose' (v2) is not available"; fi
    if docker info >/dev/null 2>&1; then ok "docker daemon is running"; else warn "docker daemon is not running - start Docker Desktop"; fi
  fi
  if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then ok "gh is logged in"; else warn "gh is not logged in - run: gh auth login   (needed for PR/CI data in reports)"; fi
  fi
  head1 "Git identity and line endings"
  [ -n "$(git config --global user.name 2>/dev/null)" ] && ok "git user.name = $(git config --global user.name)" || warn "set it: git config --global user.name \"Your Name\""
  [ -n "$(git config --global user.email 2>/dev/null)" ] && ok "git user.email is set" || warn "set it: git config --global user.email you@example.com"
  if [ "$OS" = windows ]; then
    say "  core.autocrlf = $(git config --global core.autocrlf 2>/dev/null || echo unset)  (the repo's .gitattributes forces LF for *.sh, so scripts keep working)"
    [ "$(git config --global core.longpaths 2>/dev/null)" = true ] && ok "core.longpaths = true" || warn "recommended on Windows: git config --global core.longpaths true"
  fi
}

# --------------------------------------------------------------------------- installers
NEED_RESTART=0
install_tool() { # index
  local i="$1" id label req min wg brew apt hint
  IFS='|' read -r id label req min wg brew apt hint <<<"${TOOLS[$i]}"
  case "$PM" in
    winget)
      run winget install --id "$wg" -e --silent --accept-package-agreements --accept-source-agreements \
        && NEED_RESTART=1 || warn "winget could not install $label ($wg). ${hint:-}";;
    brew)
      if [[ "$brew" == cask:* ]]; then run brew install --cask "${brew#cask:}" || warn "brew failed for $label"
      else run brew install "$brew" || warn "brew failed for $label"; fi;;
    apt)
      if [ "$apt" = "-" ]; then
        if [ "$id" = claude ]; then run bash -c 'curl -fsSL https://claude.ai/install.sh | bash' || warn "Claude Code install failed"
        else warn "$label has no apt package here. ${hint}"; fi
      else
        # shellcheck disable=SC2086
        run $SUDO apt-get install -y $apt || warn "apt failed for $label"
      fi;;
    *) warn "cannot auto-install $label. ${hint}";;
  esac
}

install_missing() {
  local i id req st todo=()
  for i in "${!TOOLS[@]}"; do
    IFS='|' read -r id _ req _ _ _ _ _ <<<"${TOOLS[$i]}"
    st="${R_STATUS[$i]}"
    [ "$st" = ok ] || [ "$st" = skip ] && continue
    [ "$id" = docker ] && [ "$DO_DOCKER" -eq 0 ] && continue          # Docker only with --docker
    todo+=("$i")
  done
  if [ "${#todo[@]}" -eq 0 ]; then say; ok "nothing to install"; return 0; fi
  head1 "Install plan"
  for i in "${todo[@]}"; do IFS='|' read -r id label _ _ _ _ _ _ <<<"${TOOLS[$i]}"; say "  - $label (${R_STATUS[$i]})"; done
  [ "$DO_DOCKER" -eq 0 ] && say "  (Docker is never installed unless you pass --docker)"
  if [ "$PM" = none ]; then warn "no package manager - nothing will be installed automatically"; return 0; fi
  if [ "$ASSUME_YES" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
    if [ ! -t 0 ]; then say "  Not interactive: re-run with --yes to install."; return 0; fi
    read -r -p "  Install the tools above with $PM? [y/N] " ans
    case "$ans" in y|Y|yes|YES) ;; *) say "  Skipped."; return 0;; esac
  fi
  head1 "Installing"
  [ "$PM" = apt ] && [ "$DRY_RUN" -eq 0 ] && run $SUDO apt-get update
  for i in "${todo[@]}"; do install_tool "$i"; done
}

# --------------------------------------------------------------------------- code repo, skills
config_value() { # python expression over parsed planning/config.json
  pick_python
  [ "${#PYBIN[@]}" -eq 0 ] && return 1
  "${PYBIN[@]}" - "$HUB/planning/config.json" "$1" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
expr = sys.argv[2]
code = next((r for r in cfg["repos"] if r.get("primary")), {})
ref = (cfg.get("reference_repos") or [{}])[0]
print(eval(expr, {"code": code, "ref": ref, "cfg": cfg}))
PY
}

clone_if_missing() { # url path
  local url="$1" path="$2"
  if [ -d "$path/.git" ]; then ok "already cloned: $path"; return 0; fi
  mkdir -p "$(dirname "$path")"
  run git clone "$url" "$path" || { warn "clone failed (access? network?) - $url"; return 1; }
}

prepare_code() {
  head1 "Code repo"
  command -v git >/dev/null 2>&1 || { bad "git is required"; return 1; }
  local url path; url="$(config_value 'code["url"]')"; path="$(config_value 'code["path"]')"
  [ -z "$url" ] && { warn "could not read planning/config.json (Python missing?)"; return 1; }
  local abs="$HUB/$path"
  clone_if_missing "$url" "$abs" || return 1
  [ "$DRY_RUN" -eq 1 ] && { say "  (dry-run: skipping venv/pip/npm steps)"; return 0; }
  pick_python
  if [ "${#PYBIN[@]}" -eq 0 ] || ! ver_ge "$PYVER" "3.12"; then warn "Python 3.12+ not available yet - skipping the virtualenv (re-run after installing/restarting the shell)"
  else
    if [ ! -d "$abs/.venv" ]; then run "${PYBIN[@]}" -m venv "$abs/.venv" || warn "venv creation failed"; else ok ".venv exists"; fi
    local vpy="$abs/.venv/bin/python"; [ -x "$abs/.venv/Scripts/python.exe" ] && vpy="$abs/.venv/Scripts/python.exe"
    if [ -x "$vpy" ]; then
      run "$vpy" -m pip install --quiet --upgrade pip
      [ -f "$abs/requirements-dev.txt" ] && run "$vpy" -m pip install --quiet -r "$abs/requirements-dev.txt"
      [ -f "$abs/requirements-ci.txt" ]  && run "$vpy" -m pip install --quiet -r "$abs/requirements-ci.txt" || true
    fi
  fi
  if [ -f "$abs/web/package-lock.json" ] && command -v npm >/dev/null 2>&1; then run npm ci --prefix "$abs/web" || warn "npm ci failed"
  else warn "skipping web dependencies (npm or web/package-lock.json missing)"; fi
  if [ -f "$abs/.env.example" ] && [ ! -f "$abs/.env" ]; then run cp "$abs/.env.example" "$abs/.env"; say "  created .env from .env.example (local defaults only; never commit it)"
  else [ -f "$abs/.env" ] && ok ".env already exists (left untouched)"; fi
}

prepare_reference() {
  head1 "Reference repo (read-only)"
  local url path; url="$(config_value 'ref.get("url","")')"; path="$(config_value 'ref.get("path","")')"
  [ -z "$url" ] && { say "  none configured"; return 0; }
  clone_if_missing "$url" "$HUB/$path"
}

install_skills() {
  head1 "Agent skills (vet each one - see claude/SKILLS.md section 2)"
  command -v npx >/dev/null 2>&1 || { warn "npx not found (install Node first)"; return 1; }
  say "  These tools may ask interactive questions (which agent/scope). Choose project scope for shared skills."
  run npx --yes skills add vercel-labs/skills@find-skills || warn "find-skills install failed - copy the exact command from https://skills.sh/vercel-labs/skills/find-skills"
  run npx --yes skills add emilkowalski/skills || warn "emilkowalski/skills install failed"
  run npx --yes impeccable install || warn "impeccable install failed - see https://github.com/pbakaus/impeccable"
  say "  Then record each skill's source and version in claude/SKILLS.md section 6."
}

# --------------------------------------------------------------------------- hub self-checks
hub_checks() {
  head1 "Hub self-checks"
  local f
  for f in planning/config.json planning/sprints.json planning/backlog.json planning/status.json scripts/devtools/report.py scripts/devtools/plan.py; do
    [ -f "$HUB/$f" ] && ok "$f" || bad "$f"
  done
  if grep -q $'\r' "$HUB/scripts/setup.sh" 2>/dev/null; then warn "scripts have CRLF line endings - run: git add --renormalize . (the .gitattributes enforces LF)"; fi
  pick_python
  if [ "${#PYBIN[@]}" -gt 0 ]; then "${PYBIN[@]}" "$HUB/scripts/devtools/plan.py" where >/dev/null 2>&1 && ok "plan/report tools run with ${PYBIN[*]} ($PYVER)" || warn "plan tool failed to run"
  else warn "no working Python found for the plan/report tools"; fi
}

summary() {
  head1 "Summary"
  local i id label req st v miss_req=0
  for i in "${!TOOLS[@]}"; do
    IFS='|' read -r id label req _ _ _ _ _ <<<"${TOOLS[$i]}"
    st="${R_STATUS[$i]}"; v="${R_VER[$i]}"
    [ "$st" = skip ] && continue
    printf '  %-34s %-8s %s\n' "$label" "$st" "$v"
    if [ "$req" = req ] && [ "$st" != ok ]; then miss_req=1; fi
  done
  if [ "$NEED_RESTART" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    say
    warn "Tools were installed. Close this Git Bash window, open a new one, and run:  bash scripts/setup.sh --check"
  fi
  say
  say "Next:  bash scripts/setup.sh --code   (clone + prepare the code repo)    bash scripts/plan.sh where    bash scripts/report.sh all"
  return "$miss_req"
}

# --------------------------------------------------------------------------- main
check_all
if [ "$CHECK_ONLY" -eq 0 ]; then install_missing; fi
if [ "$CHECK_ONLY" -eq 0 ]; then
  [ "$DO_CODE" -eq 1 ] && prepare_code
  [ "$DO_REF" -eq 1 ] && prepare_reference
  [ "$DO_SKILLS" -eq 1 ] && install_skills
fi
hub_checks
summary
exit $?
