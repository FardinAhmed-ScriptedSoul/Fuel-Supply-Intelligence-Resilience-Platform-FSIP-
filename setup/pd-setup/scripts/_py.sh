#!/usr/bin/env bash
# Sourced helper: finds a REAL Python >= 3.9 and sets the array PY. On Windows the bare `python`
# is often the Microsoft Store stub, so every candidate is executed before it is trusted.
find_python() {
  local cand
  for cand in "python3" "python" "py -3"; do
    # shellcheck disable=SC2086
    if $cand -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      # shellcheck disable=SC2206,SC2034
      PY=($cand)
      return 0
    fi
  done
  return 1
}
