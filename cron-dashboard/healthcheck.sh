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
check "API summary" bash -lc "curl -fsS http://127.0.0.1:8000/api/cron/summary"
check "API jobs" bash -lc "curl -fsS http://127.0.0.1:8000/api/cron/jobs"

echo "Healthcheck done"
