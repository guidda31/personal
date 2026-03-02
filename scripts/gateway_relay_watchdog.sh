#!/usr/bin/env bash
set -euo pipefail

# OpenClaw Gateway + Chrome Relay watchdog
# - Detects gateway down / relay-detached states
# - Sends Telegram alert ONLY on state change (anti-spam)

ACCOUNT_ID="telegram-bot-2"
CHANNEL="telegram"
TARGET_CHAT="1261506890"
STATE_DIR="${HOME}/.openclaw/workspace/tmp"
STATE_FILE="${STATE_DIR}/relay_watchdog_state"
LOCK_FILE="/tmp/gateway_relay_watchdog.lock"

mkdir -p "${STATE_DIR}"

send_msg() {
  local text="$1"
  openclaw message send \
    --account "${ACCOUNT_ID}" \
    --channel "${CHANNEL}" \
    --target "${TARGET_CHAT}" \
    --message "$text" >/dev/null
}

get_prev_state() {
  [[ -f "${STATE_FILE}" ]] && cat "${STATE_FILE}" || echo "UNKNOWN"
}

set_state() {
  local s="$1"
  printf '%s' "$s" > "${STATE_FILE}"
}

main() {
  exec 9>"${LOCK_FILE}"
  flock -n 9 || exit 0

  local prev curr tabs_count tabs_json
  prev="$(get_prev_state)"

  # 1) Gateway health
  if ! openclaw gateway status >/dev/null 2>&1; then
    curr="GW_DOWN"
    if [[ "$prev" != "$curr" ]]; then
      send_msg "⚠️ OpenClaw gateway 접속 불가 상태입니다. 자동 복구 확인 필요."
      set_state "$curr"
    fi
    exit 0
  fi

  # 2) Relay attachment health (chrome profile tabs)
  tabs_json="$(openclaw browser tabs --browser-profile chrome --json 2>/dev/null || true)"
  tabs_count="$(node -e 'try{const o=JSON.parse(process.argv[1]||"{}");console.log(Array.isArray(o.tabs)?o.tabs.length:0)}catch(e){console.log(0)}' "$tabs_json" 2>/dev/null || echo 0)"

  if [[ "$tabs_count" =~ ^[0-9]+$ ]] && [[ "$tabs_count" -gt 0 ]]; then
    curr="ATTACHED"
    if [[ "$prev" != "$curr" ]]; then
      send_msg "✅ OpenClaw gateway/Relay 정상 복구됨 (연결 탭 ${tabs_count}개)."
      set_state "$curr"
    fi
  else
    curr="DETACHED"
    if [[ "$prev" != "$curr" ]]; then
      send_msg "⚠️ OpenClaw Browser Relay 탭 연결이 없습니다. Chrome에서 릴레이 아이콘 클릭해 badge ON 해주세요."
      set_state "$curr"
    fi
  fi
}

main "$@"
