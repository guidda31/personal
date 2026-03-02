#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/guidda/.openclaw/workspace"
LEGACY="$ROOT/cron-dashboard/cron_dashboard_server.js"

if [[ -f "$LEGACY" ]]; then
  mv "$LEGACY" "$ROOT/cron-dashboard/_legacy_cron_dashboard_server.js"
  echo "moved legacy server -> _legacy_cron_dashboard_server.js"
else
  echo "legacy server not found (already moved)"
fi

# remove old autostart that references node legacy server (if exists)
TMP=$(mktemp)
crontab -l 2>/dev/null | sed '/cron-dashboard-autostart/d' > "$TMP" || true
crontab "$TMP"
rm -f "$TMP"

echo "removed old cron-dashboard-autostart entry"
