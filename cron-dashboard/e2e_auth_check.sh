#!/usr/bin/env bash
set -euo pipefail

API="${1:-http://127.0.0.1:8000}"
USER="${CRON_DASHBOARD_AUTH_USER:-}"
PASS="${CRON_DASHBOARD_AUTH_PASS:-}"

echo "[1] no-auth request"
code_noauth=$(curl -s -o /tmp/cron_api_noauth.json -w "%{http_code}" "$API/api/cron/summary" || true)
echo "status=$code_noauth"

if [[ -n "$USER" && -n "$PASS" ]]; then
  echo "[2] auth request"
  code_auth=$(curl -s -u "$USER:$PASS" -o /tmp/cron_api_auth.json -w "%{http_code}" "$API/api/cron/summary" || true)
  echo "status=$code_auth"
  if [[ "$code_auth" == "200" ]]; then
    echo "auth check: OK"
  else
    echo "auth check: FAIL"
  fi
else
  echo "[2] skipped (CRON_DASHBOARD_AUTH_USER/PASS not set)"
fi
