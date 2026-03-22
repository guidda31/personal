#!/usr/bin/env bash
set -euo pipefail

# OpenClaw OAuth refresh failure watchdog
# - Checks recent gateway logs for OAuth refresh errors
# - Sends Telegram alert via OpenClaw message command (no model call required)

TARGET_TELEGRAM_ID="1261506890"
LOCK_FILE="/tmp/openclaw_auth_watchdog.lock"
STATE_DIR="/home/guidda/.openclaw/workspace/tmp"
LAST_HASH_FILE="$STATE_DIR/openclaw_auth_watchdog.last"
mkdir -p "$STATE_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

LOG_CHUNK="$(openclaw logs --plain --limit 500 2>/dev/null || true)"
if [[ -z "$LOG_CHUNK" ]]; then
  exit 0
fi

# Match auth refresh failures for codex provider
MATCHES="$(printf '%s\n' "$LOG_CHUNK" | grep -Ei 'oauth token refresh failed|failed to refresh oauth token|openai-codex.*status":401|model_fallback_decision.*"reason":"auth"' || true)"
if [[ -z "$MATCHES" ]]; then
  exit 0
fi

# Use tail of matches as fingerprint to avoid duplicate spam
FINGERPRINT="$(printf '%s\n' "$MATCHES" | tail -n 5 | sha256sum | awk '{print $1}')"
LAST=""
if [[ -f "$LAST_HASH_FILE" ]]; then
  LAST="$(cat "$LAST_HASH_FILE" 2>/dev/null || true)"
fi

if [[ "$FINGERPRINT" == "$LAST" ]]; then
  exit 0
fi

echo "$FINGERPRINT" > "$LAST_HASH_FILE"

LAST_LINE="$(printf '%s\n' "$MATCHES" | tail -n 1)"
MSG="🚨 OpenClaw 인증 끊김 감지 (Codex OAuth 실패)\n즉시 재인증 필요\n로그: ${LAST_LINE}"

openclaw message send --channel telegram --target "$TARGET_TELEGRAM_ID" --message "$MSG" >/dev/null 2>&1 || true
