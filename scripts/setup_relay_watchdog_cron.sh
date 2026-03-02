#!/usr/bin/env bash
set -euo pipefail

LINE='*/2 * * * * /usr/bin/env bash -lc "/home/guidda/.openclaw/workspace/scripts/gateway_relay_watchdog.sh" #openclaw-relay-watchdog'

TMP_FILE="$(mktemp)"
crontab -l 2>/dev/null > "$TMP_FILE" || true

grep -Fq "#openclaw-relay-watchdog" "$TMP_FILE" || echo "$LINE" >> "$TMP_FILE"
crontab "$TMP_FILE"
rm -f "$TMP_FILE"

echo "[OK] relay watchdog cron installed"
crontab -l | grep -F "openclaw-relay-watchdog" || true
