#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"

# backend
if pgrep -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" >/dev/null; then
  echo "[backend] already running"
else
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$BASE/../tmp/cron_dashboard_backend.log" 2>&1 &
  echo $! > "$BASE/../tmp/cron_dashboard_backend.pid"
  echo "[backend] started"
fi

# frontend
if pgrep -f "vite --host 0.0.0.0 --port 5173" >/dev/null; then
  echo "[frontend] already running"
else
  cd "$BASE/frontend"
  nohup npm run dev -- --host 0.0.0.0 --port 5173 \
    > "$BASE/../tmp/cron_dashboard_frontend.log" 2>&1 &
  echo $! > "$BASE/../tmp/cron_dashboard_frontend.pid"
  echo "[frontend] started"
fi

echo "Dashboard FE: http://127.0.0.1:5173"
echo "Dashboard API: http://127.0.0.1:8000"
