#!/usr/bin/env bash
set -euo pipefail

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempt

  printf 'Checking %s\n' "$name"
  for attempt in {1..30}; do
    if curl --fail --silent --show-error --output /dev/null \
      --connect-timeout 2 --max-time 5 "$url" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done

  printf 'ERROR: %s did not return a successful HTTP response: %s\n' "$name" "$url" >&2
  return 1
}

frontend_address="$(docker compose port frontend 80)"
if [[ -z "$frontend_address" ]]; then
  printf 'ERROR: frontend host port is not published\n' >&2
  exit 1
fi
frontend_port="${frontend_address##*:}"

wait_for_http "simulator" "http://localhost:8000/v1/health"
wait_for_http "API liveness" "http://localhost:8101/health"
wait_for_http "API state and database" "http://localhost:8101/api/state"
wait_for_http "worker" "http://localhost:8102/health"
wait_for_http "predictor" "http://localhost:8103/health"
wait_for_http "frontend" "http://localhost:${frontend_port}/"
wait_for_http "Prometheus" "http://localhost:9090/-/healthy"
wait_for_http "Grafana" "http://localhost:3000/api/health"

printf 'PASS: all Compose service smoke checks returned successful HTTP responses\n'
