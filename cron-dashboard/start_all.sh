#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
TMP_DIR="$BASE/../tmp"
mkdir -p "$TMP_DIR"

# load optional env files
[[ -f "$BASE/backend/.env" ]] && set -a && . "$BASE/backend/.env" && set +a
[[ -f "$BASE/frontend/.env" ]] && set -a && . "$BASE/frontend/.env" && set +a

is_listening() {
  local port="$1"
  ss -ltn "( sport = :$port )" | awk 'NR>1 && $1=="LISTEN" {print}' | grep -q ":$port"
}

if is_listening 8000; then
  # health probe first (avoid stale listener confusion)
  if curl -fsS --max-time 2 http://127.0.0.1:8000/api/cron/summary >/dev/null 2>&1; then
    echo "[backend] already healthy on :8000"
  else
    echo "[backend] unhealthy listener detected, restarting"
    pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" || true
    sleep 1
    (
      cd "$BASE/backend"
      nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$TMP_DIR/cron_dashboard_backend.log" 2>&1 &
      echo $! > "$TMP_DIR/cron_dashboard_backend.pid"
    )
  fi
else
  (
    cd "$BASE/backend"
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$TMP_DIR/cron_dashboard_backend.log" 2>&1 &
    echo $! > "$TMP_DIR/cron_dashboard_backend.pid"
  )
fi
sleep 1
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:8000/api/cron/summary || true)
if is_listening 8000 && { [[ "$code" == "200" ]] || [[ "$code" == "401" ]]; }; then
  echo "[backend] started/healthy (http $code)"
else
  echo "[backend] failed to start (check $TMP_DIR/cron_dashboard_backend.log)"
fi

if is_listening 5173; then
  echo "[frontend] already listening on :5173"
else
  (
    cd "$BASE/frontend"
    nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$TMP_DIR/cron_dashboard_frontend.log" 2>&1 &
    echo $! > "$TMP_DIR/cron_dashboard_frontend.pid"
  )
  sleep 1
  is_listening 5173 && echo "[frontend] started" || echo "[frontend] failed to start"
fi

echo "Dashboard FE:  http://127.0.0.1:5173"
echo "Dashboard API: http://127.0.0.1:8000"
