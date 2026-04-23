#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/guidda/.nvm/versions/node/v22.22.0/bin/openclaw}"
TARGET_TELEGRAM_ID="1261506890"
PREFERRED_ACCOUNT="telegram-bot-2"
FALLBACK_ACCOUNT="default"
STATE_DIR="/home/guidda/.openclaw/workspace/tmp"
RUN_LOG="$STATE_DIR/openclaw_codex_reauth.log"
SEND_LOG="$STATE_DIR/openclaw_codex_reauth_alert.log"
mkdir -p "$STATE_DIR"

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"
export OPENCLAW_GOOGLE_EMAIL="${OPENCLAW_GOOGLE_EMAIL:-guidda31@gmail.com}"

send_alert() {
  local msg="$1"
  local account="$2"
  echo "[$(date '+%F %T')] send attempt via account=${account}" >> "$SEND_LOG"
  if [[ "$account" == "default" ]]; then
    "$OPENCLAW_BIN" message send --channel telegram --target "$TARGET_TELEGRAM_ID" --message "$msg"
  else
    "$OPENCLAW_BIN" message send --channel telegram --account "$account" --target "$TARGET_TELEGRAM_ID" --message "$msg"
  fi
}

if /usr/bin/flock -n /tmp/openclaw_codex_reauth.lock bash /home/guidda/.openclaw/workspace/scripts/openclaw_codex_reauth_assisted.sh >> "$RUN_LOG" 2>&1; then
  echo "[$(date '+%F %T')] codex reauth: success" >> "$RUN_LOG"
  exit 0
fi

TAIL_OUT="$(tail -n 20 "$RUN_LOG" 2>/dev/null | tr '\n' ' ' | tail -c 900)"
MSG="🚨 OpenClaw Codex 재인증 자동 실행 실패\n시간: $(date '+%F %T')\n로그: ${TAIL_OUT}"

if send_alert "$MSG" "$PREFERRED_ACCOUNT" >>"$SEND_LOG" 2>&1; then
  echo "[$(date '+%F %T')] codex reauth: alert sent via $PREFERRED_ACCOUNT" >> "$RUN_LOG"
else
  sleep 3
  if send_alert "$MSG" "$FALLBACK_ACCOUNT" >>"$SEND_LOG" 2>&1; then
    echo "[$(date '+%F %T')] codex reauth: alert sent via $FALLBACK_ACCOUNT (fallback)" >> "$RUN_LOG"
  else
    echo "[$(date '+%F %T')] codex reauth: alert send failed" >> "$RUN_LOG"
  fi
fi

exit 1
