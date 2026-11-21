#!/usr/bin/env bash
# Feature status / blockers / notes. Usage: scripts/plan.sh where | list | set F-001 in_progress | blocker add "..." | note add "..." --kind next
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_py.sh
source "$here/_py.sh"
find_python || { echo "error: no working Python 3.9+ found. Run: bash scripts/setup.sh" >&2; exit 1; }
exec "${PY[@]}" "$here/devtools/plan.py" "$@"
