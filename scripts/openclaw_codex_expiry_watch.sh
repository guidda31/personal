#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/guidda/.nvm/versions/node/v22.22.0/bin/openclaw}"
AUTH_FILE="/home/guidda/.openclaw/agents/main/agent/auth-profiles.json"
PROFILE_NAME="openai-codex:default"
TARGET_TELEGRAM_ID="1261506890"
PREFERRED_ACCOUNT="telegram-bot-2"
FALLBACK_ACCOUNT="default"
STATE_DIR="/home/guidda/.openclaw/workspace/tmp"
STATE_FILE="$STATE_DIR/openclaw_codex_expiry_watch.state.json"
LOG_FILE="$STATE_DIR/openclaw_codex_expiry_watch.log"
SEND_LOG="$STATE_DIR/openclaw_codex_expiry_watch.send.log"
LOCK_FILE="/tmp/openclaw_codex_expiry_watch.lock"

mkdir -p "$STATE_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "[$(date '+%F %T')] expiry-watch: openclaw binary missing at $OPENCLAW_BIN" >> "$LOG_FILE"
  exit 1
fi

INFO_LINE="$({ python3 - <<'PY'
import json, os, sys
from datetime import datetime, timezone, timedelta

AUTH_FILE = "/home/guidda/.openclaw/agents/main/agent/auth-profiles.json"
PROFILE_NAME = "openai-codex:default"
KST = timezone(timedelta(hours=9))

if not os.path.exists(AUTH_FILE):
    print("ERR\tmissing auth file: %s" % AUTH_FILE)
    sys.exit(0)

try:
    with open(AUTH_FILE, encoding="utf-8") as f:
        data = json.load(f)
    prof = (data.get("profiles") or {}).get(PROFILE_NAME) or {}
    expires_ms = int(prof.get("expires") or 0)
    if not expires_ms:
        print("ERR\tmissing expires for %s" % PROFILE_NAME)
        sys.exit(0)

    now = datetime.now(KST)
    expiry = datetime.fromtimestamp(expires_ms / 1000, tz=KST)
    seconds_left = int((expiry - now).total_seconds())
    days_left = (expiry.date() - now.date()).days

    if seconds_left <= 0:
        stage = "expired"
    elif days_left <= 0:
        stage = "d0"
    elif days_left == 1:
        stage = "d1"
    elif days_left == 2:
        stage = "d2"
    else:
        stage = "none"

    print("OK\t%s\t%d\t%d\t%d\t%s" % (
        stage,
        seconds_left,
        days_left,
        expires_ms,
        expiry.strftime("%Y-%m-%d %H:%M:%S KST"),
    ))
except Exception as e:
    print("ERR\t%s" % str(e).replace("\t", " "))
PY
} )"

if [[ -z "$INFO_LINE" ]]; then
  echo "[$(date '+%F %T')] expiry-watch: failed to compute expiry info" >> "$LOG_FILE"
  exit 1
fi

IFS=$'\t' read -r STATUS STAGE SECONDS_LEFT DAYS_LEFT EXPIRES_MS EXPIRES_KST <<< "$INFO_LINE"

if [[ "$STATUS" != "OK" ]]; then
  echo "[$(date '+%F %T')] expiry-watch: ${STAGE:-unknown error}" >> "$LOG_FILE"
  exit 1
fi

if [[ "$STAGE" == "none" ]]; then
  echo "[$(date '+%F %T')] expiry-watch: no alert needed" >> "$LOG_FILE"
  exit 0
fi

LAST_KEY=""
if [[ -f "$STATE_FILE" ]]; then
  LAST_KEY="$(cat "$STATE_FILE" 2>/dev/null || true)"
fi
CURRENT_KEY="${EXPIRES_MS}:${STAGE}"
if [[ "$LAST_KEY" == "$CURRENT_KEY" ]]; then
  echo "[$(date '+%F %T')] expiry-watch: duplicate stage suppressed ($CURRENT_KEY)" >> "$LOG_FILE"
  exit 0
fi

case "$STAGE" in
  d2)
    MSG="⏰ Codex 인증 만료 2일 전\n만료 예정: ${EXPIRES_KST}\n자동 갱신 신뢰가 낮아 미리 재인증 권장"
    ;;
  d1)
    MSG="⚠️ Codex 인증 만료 1일 전\n만료 예정: ${EXPIRES_KST}\n오늘 안에 재인증 권장"
    ;;
  d0)
    MSG="🚨 Codex 인증 오늘 만료 예정\n만료 예정: ${EXPIRES_KST}\n지금 재인증 권장"
    ;;
  expired)
    MSG="🚨 Codex 인증 만료됨\n만료 시각: ${EXPIRES_KST}\n즉시 재인증 필요"
    ;;
  *)
    echo "[$(date '+%F %T')] expiry-watch: unknown stage $STAGE" >> "$LOG_FILE"
    exit 1
    ;;
esac

send_alert() {
  local account="$1"
  echo "[$(date '+%F %T')] send attempt via account=${account} stage=${STAGE}" >> "$SEND_LOG"
  if [[ "$account" == "default" ]]; then
    "$OPENCLAW_BIN" message send --channel telegram --target "$TARGET_TELEGRAM_ID" --message "$MSG"
  else
    "$OPENCLAW_BIN" message send --channel telegram --account "$account" --target "$TARGET_TELEGRAM_ID" --message "$MSG"
  fi
}

if send_alert "$PREFERRED_ACCOUNT" >>"$SEND_LOG" 2>&1; then
  echo "$CURRENT_KEY" > "$STATE_FILE"
  echo "[$(date '+%F %T')] expiry-watch: alert sent via $PREFERRED_ACCOUNT (days_left=$DAYS_LEFT seconds_left=$SECONDS_LEFT expires=$EXPIRES_KST)" >> "$LOG_FILE"
  exit 0
fi

sleep 2
if send_alert "$FALLBACK_ACCOUNT" >>"$SEND_LOG" 2>&1; then
  echo "$CURRENT_KEY" > "$STATE_FILE"
  echo "[$(date '+%F %T')] expiry-watch: alert sent via $FALLBACK_ACCOUNT fallback (days_left=$DAYS_LEFT seconds_left=$SECONDS_LEFT expires=$EXPIRES_KST)" >> "$LOG_FILE"
  exit 0
fi

echo "[$(date '+%F %T')] expiry-watch: alert send failed (stage=$STAGE expires=$EXPIRES_KST)" >> "$LOG_FILE"
exit 1
