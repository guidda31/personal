#!/usr/bin/env bash
set -euo pipefail

# OpenClaw OAuth refresh failure watchdog
# - Checks recent gateway logs for OAuth refresh errors
# - Sends Telegram alert via OpenClaw message command (no model call required)

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/guidda/.nvm/versions/node/v22.22.0/bin/openclaw}"
TARGET_TELEGRAM_ID="1261506890"
PREFERRED_ACCOUNT="telegram-bot-2"
FALLBACK_ACCOUNT="default"
LOCK_FILE="/tmp/openclaw_auth_watchdog.lock"
STATE_DIR="/home/guidda/.openclaw/workspace/tmp"
LAST_HASH_FILE="$STATE_DIR/openclaw_auth_watchdog.last"
mkdir -p "$STATE_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

# Prefer direct gateway log file (works even when CLI RPC scope/token is unavailable in cron)
LOG_FILE="/tmp/openclaw/openclaw-$(date +%F).log"
LOG_CHUNK=""
if [[ -f "$LOG_FILE" ]]; then
  LOG_CHUNK="$(tail -n 2000 "$LOG_FILE" 2>/dev/null || true)"
fi

# Fallback to CLI logs API
if [[ -z "$LOG_CHUNK" ]]; then
  LOG_CHUNK="$("$OPENCLAW_BIN" logs --plain --limit 2000 2>/dev/null || true)"
fi

if [[ -z "$LOG_CHUNK" ]]; then
  echo "[$(date '+%F %T')] watchdog: no logs available" >> "$STATE_DIR/openclaw_auth_watchdog.log"
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
SHORT_LINE="$(printf '%s' "$LAST_LINE" | tr '\n' ' ' | tail -c 700)"
MSG="🚨 OpenClaw 인증 끊김 감지 (Codex OAuth 실패)\n즉시 재인증 필요\n로그: ${SHORT_LINE}"
SEND_LOG="$STATE_DIR/openclaw_auth_watchdog.send.log"

send_alert() {
  local account="$1"
  echo "[$(date '+%F %T')] send attempt via account=${account}" >> "$SEND_LOG"
  if [[ "$account" == "default" ]]; then
    "$OPENCLAW_BIN" message send --channel telegram --target "$TARGET_TELEGRAM_ID" --message "$MSG"
  else
    "$OPENCLAW_BIN" message send --channel telegram --account "$account" --target "$TARGET_TELEGRAM_ID" --message "$MSG"
  fi
}

if send_alert "$PREFERRED_ACCOUNT" >>"$SEND_LOG" 2>&1; then
  echo "[$(date '+%F %T')] watchdog: alert sent via $PREFERRED_ACCOUNT" >> "$STATE_DIR/openclaw_auth_watchdog.log"
else
  sleep 3
  if send_alert "$FALLBACK_ACCOUNT" >>"$SEND_LOG" 2>&1; then
    echo "[$(date '+%F %T')] watchdog: alert sent via $FALLBACK_ACCOUNT (fallback)" >> "$STATE_DIR/openclaw_auth_watchdog.log"
  else
    echo "[$(date '+%F %T')] watchdog: alert send failed (preferred=$PREFERRED_ACCOUNT fallback=$FALLBACK_ACCOUNT; see $SEND_LOG)" >> "$STATE_DIR/openclaw_auth_watchdog.log"
  fi
fi
