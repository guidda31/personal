#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"

sudo cp "$BASE/cron-dashboard-backend.service" /etc/systemd/system/
sudo cp "$BASE/cron-dashboard-frontend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cron-dashboard-backend.service
sudo systemctl enable --now cron-dashboard-frontend.service

sudo systemctl status --no-pager cron-dashboard-backend.service | head -n 20
sudo systemctl status --no-pager cron-dashboard-frontend.service | head -n 20
