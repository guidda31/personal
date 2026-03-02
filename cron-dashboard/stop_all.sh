#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" || true
pkill -f "vite --host 0.0.0.0 --port 5173" || true

echo "stopped backend/frontend (if running)"
