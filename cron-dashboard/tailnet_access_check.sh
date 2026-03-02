#!/usr/bin/env bash
set -euo pipefail

TAIL_IP="$(tailscale ip -4 | head -n1)"
if [[ -z "$TAIL_IP" ]]; then
  echo "[FAIL] tailscale ip not found"
  exit 1
fi

echo "[INFO] Tailnet IP: $TAIL_IP"

code_local=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173 || true)
code_tail=$(curl -s -o /dev/null -w "%{http_code}" "http://$TAIL_IP:5173" || true)

echo "[CHECK] Local FE 127.0.0.1:5173 -> HTTP $code_local"
echo "[CHECK] Tailnet FE $TAIL_IP:5173 -> HTTP $code_tail"

if [[ "$code_local" == "200" && "$code_tail" == "200" ]]; then
  echo "[OK] Tailnet IP direct access is healthy"
  echo "Use this URL from your tailnet devices: http://$TAIL_IP:5173"
else
  echo "[WARN] One or more checks failed"
  exit 2
fi
