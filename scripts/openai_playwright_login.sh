#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=:0
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

exec python3 /home/guidda/.openclaw/workspace/scripts/openai_playwright_login.py
