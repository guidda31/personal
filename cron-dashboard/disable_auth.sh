#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"

cat > "$BASE/backend/.env" <<EOF
CRON_DB_USER=guidda
CRON_DB_PASS=!q1w2e3r4t5
CRON_DB_HOST=127.0.0.1
CRON_DB_PORT=3306
CRON_DB_NAME=internal_db
CRON_DASHBOARD_AUTH_USER=
CRON_DASHBOARD_AUTH_PASS=
EOF

cat > "$BASE/frontend/.env" <<EOF
VITE_API_BASE=
VITE_AUTH_USER=
VITE_AUTH_PASS=
EOF

echo "Auth disabled in env files. restart with: $BASE/stop_all.sh && $BASE/start_all.sh"
