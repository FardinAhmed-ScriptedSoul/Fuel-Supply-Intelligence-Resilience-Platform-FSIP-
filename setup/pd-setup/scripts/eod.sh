#!/usr/bin/env bash
# End-of-day routine: generate today's report + short update (+ sprint report on a sprint's last day),
# print the update text and copy it to the clipboard when a clipboard tool exists.
#   bash scripts/eod.sh                run tests too (slower, adds test/coverage numbers)
#   bash scripts/eod.sh --no-tests     skip the local pytest run
#   bash scripts/eod.sh --date yesterday|YYYY-MM-DD
set -o pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hub="$(cd "$here/.." && pwd)"
want="today"; tests=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-tests) tests=();;
    --with-tests) tests=(--with-tests);;
    --date) shift; want="${1:-today}";;
    -h|--help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
  shift
done
# default: run tests unless --no-tests was given explicitly
case " $* " in *" --no-tests "*) tests=();; *) tests=(--with-tests);; esac

case "$want" in
  today) day="$(date +%F)";;
  yesterday) day="$(date -d yesterday +%F 2>/dev/null || date -v-1d +%F)";;
  *) day="$want";;
esac

bash "$here/report.sh" all --date "$want" "${tests[@]}" || exit $?
txt="$hub/reports/daily/$day.update.txt"
if [ -f "$txt" ]; then
  echo; echo "-------- update message ($txt) --------"; cat "$txt"
  for clip in clip pbcopy "xclip -selection clipboard" wl-copy; do
    # shellcheck disable=SC2086
    if command -v ${clip%% *} >/dev/null 2>&1; then $clip < "$txt" && echo "(copied to clipboard)"; break; fi
  done
fi
echo; echo "Stage for commit:  git add reports planning && git commit -m \"docs: daily report $day\""
