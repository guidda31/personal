#!/usr/bin/env bash
set -euo pipefail

cd /home/guidda/.openclaw/workspace/kis-openapi

# runner.py loads .env via python-dotenv when available
# --run enables real order path, --confirm required for real mode
python3 runner.py --run --confirm REAL_ORDER
