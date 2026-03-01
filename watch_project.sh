#!/bin/bash
set -euo pipefail

WATCH_DIR="/home/guidda/.openclaw/workspace/project"
TARGET_CHAT="1261506890"
CHANNEL="telegram"

send_msg() {
  local text="$1"
  openclaw message send \
    --channel "$CHANNEL" \
    --target "$TARGET_CHAT" \
    --message "$text" >/dev/null 2>&1 || true
}

trim_file() {
  local f="$1"
  # Keep message short for telegram limits
  if command -v jq >/dev/null 2>&1; then
    jq -c . "$f" 2>/dev/null | head -c 2800
  else
    head -c 2800 "$f"
  fi
}

send_msg "[watch_project] 감시 시작: $WATCH_DIR"

# Initial snapshot
find "$WATCH_DIR" -type f -name "*.json" | while read -r file; do
  payload="$(trim_file "$file")"
  send_msg "[watch_project][초기] $file\n$payload"
done

# Watch ongoing changes
inotifywait -m -r \
  -e close_write,create,move \
  --format '%w%f' \
  "$WATCH_DIR" | while read -r path; do
  case "$path" in
    *.json)
      payload="$(trim_file "$path")"
      send_msg "[watch_project][변경] $path\n$payload"
      ;;
  esac
done
