#!/usr/bin/env bash
# Engineering reports.
#   scripts/report.sh daily                  today's report  -> reports/daily/YYYY-MM-DD.md
#   scripts/report.sh update                 short message   -> reports/daily/YYYY-MM-DD.update.txt
#   scripts/report.sh all                    daily + update (+ sprint report on the sprint's last day)
#   scripts/report.sh sprint --sprint S1     sprint report   -> reports/sprint/S1.md
# Flags: --date YYYY-MM-DD|yesterday   --with-tests   --no-gh   --stdout
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_py.sh
source "$here/_py.sh"
find_python || { echo "error: no working Python 3.9+ found. Run: bash scripts/setup.sh" >&2; exit 1; }
cmd="${1:-all}"; [[ $# -gt 0 ]] && shift
exec "${PY[@]}" "$here/devtools/report.py" "$cmd" "$@"
