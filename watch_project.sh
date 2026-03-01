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

format_payload() {
  local f="$1"
  if ! command -v jq >/dev/null 2>&1; then
    head -c 2500 "$f"
    return
  fi

  jq -r '
    def v: if . == null then "-" else tostring end;
    if type=="object" then
      [
        "task/report: " + ((.taskId // .reportId // .docId // "-")|tostring),
        "role: " + ((.role // .fromRole // "-")|tostring) + " -> " + ((.toRole // "-")|tostring),
        "title: " + ((.title // "-")|tostring),
        "status: " + ((.status // "-")|tostring),
        "summary: " + ((.summary // .objective // .notes // "-")|tostring),
        (if (.nextActions? and (.nextActions|length>0)) then "next: " + (.nextActions|join(" | ")) else empty end),
        (if (.issues? and (.issues|length>0)) then "issues: " + (.issues|join(" | ")) else empty end)
      ] | map(select(length>0)) | join("\n")
    else
      tostring
    end
  ' "$f" 2>/dev/null | head -c 2800
}

send_msg "[watch_project] 감시 시작: $WATCH_DIR"

# Initial snapshot
find "$WATCH_DIR" -type f -name "*.json" | while read -r file; do
  payload="$(format_payload "$file")"
  send_msg "[프로젝트/초기]\n파일: $file\n$payload"
done

# Watch ongoing changes
inotifywait -m -r \
  -e close_write,create,move \
  --format '%w%f' \
  "$WATCH_DIR" | while read -r path; do
  case "$path" in
    *.json)
      payload="$(format_payload "$path")"
      send_msg "[프로젝트/변경]\n파일: $path\n$payload"
      ;;
  esac
done
