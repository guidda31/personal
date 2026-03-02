#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
TMP_DIR="$BASE/../tmp"
mkdir -p "$TMP_DIR"

is_listening() {
  local port="$1"
  ss -ltn "( sport = :$port )" | grep -q ":$port"
}

# backend
if is_listening 8000; then
  echo "[backend] already listening on :8000"
else
  (
    cd "$BASE/backend"
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > "$TMP_DIR/cron_dashboard_backend.log" 2>&1 &
    echo $! > "$TMP_DIR/cron_dashboard_backend.pid"
  )
  sleep 1
  if is_listening 8000; then
    echo "[backend] started"
  else
    echo "[backend] failed to start (check $TMP_DIR/cron_dashboard_backend.log)"
  fi
fi

# frontend
if is_listening 5173; then
  echo "[frontend] already listening on :5173"
else
  (
    cd "$BASE/frontend"
    nohup npm run dev -- --host 0.0.0.0 --port 5173 \
      > "$TMP_DIR/cron_dashboard_frontend.log" 2>&1 &
    echo $! > "$TMP_DIR/cron_dashboard_frontend.pid"
  )
  sleep 1
  if is_listening 5173; then
    echo "[frontend] started"
  else
    echo "[frontend] failed to start (check $TMP_DIR/cron_dashboard_frontend.log)"
  fi
fi

echo "Dashboard FE:  http://127.0.0.1:5173"
echo "Dashboard API: http://127.0.0.1:8000"
