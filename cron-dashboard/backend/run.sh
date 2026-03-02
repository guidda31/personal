#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
