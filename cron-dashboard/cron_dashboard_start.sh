#!/usr/bin/env bash
set -euo pipefail

PORT="${CRON_DASHBOARD_PORT:-8088}"
HOST="${CRON_DASHBOARD_HOST:-0.0.0.0}"
LOG_DIR="/home/guidda/.openclaw/workspace/tmp"
PID_FILE="$LOG_DIR/cron_dashboard.pid"
LOG_FILE="$LOG_DIR/cron_dashboard.log"

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "already running (pid $(cat "$PID_FILE"))"
  exit 0
fi

nohup env CRON_DASHBOARD_PORT="$PORT" CRON_DASHBOARD_HOST="$HOST" \
  node /home/guidda/.openclaw/workspace/cron-dashboard/cron_dashboard_server.js \
  >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "started pid $(cat "$PID_FILE") on http://$HOST:$PORT"
