#!/usr/bin/env bash
set -euo pipefail

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "[OK] $name"
  else
    echo "[FAIL] $name"
  fi
}

check "Backend 8000 listening" bash -lc "ss -ltn '( sport = :8000 )' | awk 'NR>1 && \$1==\"LISTEN\" {print}' | grep -q ':8000'"
check "Frontend 5173 listening" bash -lc "ss -ltn '( sport = :5173 )' | awk 'NR>1 && \$1==\"LISTEN\" {print}' | grep -q ':5173'"
check_api() {
  local name="$1"; local url="$2"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
  if [[ "$code" == "200" || "$code" == "401" ]]; then
    echo "[OK] $name (http $code)"
  else
    echo "[FAIL] $name (http $code)"
  fi
}

check_api "API summary" "http://127.0.0.1:8000/api/cron/summary"
check_api "API jobs" "http://127.0.0.1:8000/api/cron/jobs"

echo "Healthcheck done"
