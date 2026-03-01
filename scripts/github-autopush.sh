#!/usr/bin/env bash
set -euo pipefail

REPO="/home/guidda/.openclaw/workspace"
cd "$REPO"

# Ensure remote exists
if ! git remote get-url origin >/dev/null 2>&1; then
  exit 0
fi

# Skip if no changes
if [[ -z "$(git status --porcelain)" ]]; then
  exit 0
fi

# Stage everything (respecting .gitignore)
git add -A

# If staging produced no changes, stop
if git diff --cached --quiet; then
  exit 0
fi

TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"
git commit -m "auto: workspace sync ($TS)" >/dev/null 2>&1 || exit 0

# Push (will fail silently if auth missing)
git push origin master >/dev/null 2>&1 || true
