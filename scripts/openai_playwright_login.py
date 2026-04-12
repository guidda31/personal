#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright
import signal
import sys
import time

PROFILE_DIR = Path("/home/guidda/.openclaw/workspace/tmp/pw-openai-auth-profile")
CHROME = "/home/guidda/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
TARGET_URL = "https://chatgpt.com/auth/login"

running = True

def stop(*_args):
    global running
    running = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

PROFILE_DIR.mkdir(parents=True, exist_ok=True)
print(f"[playwright-login] profile={PROFILE_DIR}", flush=True)
print(f"[playwright-login] opening={TARGET_URL}", flush=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        executable_path=CHROME,
        headless=False,
        ignore_default_args=["--enable-automation"],
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    print(f"[playwright-login] ready url={page.url}", flush=True)
    print("[playwright-login] leave this process running while you sign in.", flush=True)

    while running:
        if page.is_closed():
            break
        time.sleep(1)

    print("[playwright-login] closing", flush=True)
    ctx.close()
