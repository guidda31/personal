#!/usr/bin/env python3
import os
import subprocess
import requests


def send_telegram(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Primary: direct Telegram Bot API
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=8)
            return True
        except Exception:
            pass

    # Fallback: OpenClaw message CLI (uses connected channel)
    target = os.getenv("OPENCLAW_NOTIFY_TARGET", "1261506890").strip()
    try:
        subprocess.run(
            [
                "openclaw",
                "message",
                "send",
                "--channel",
                "telegram",
                "--target",
                target,
                "--message",
                text,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return True
    except Exception:
        return False
