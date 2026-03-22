#!/usr/bin/env python3
import os
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.getenv("AI_TREND_PW_PROFILE", "/home/guidda/.openclaw/workspace/tmp/pw-youtube-profile")
URL = "https://www.youtube.com/feed/history"

print("[AI-TREND] YouTube 로그인 세션 설정 시작")
print(f"- profile: {PROFILE_DIR}")
print("- 브라우저 창이 열리면 YouTube 로그인 후 Enter를 누르세요.")

os.makedirs(PROFILE_DIR, exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        args=["--no-sandbox"],
    )
    page = context.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=90000)
    input("\n로그인 완료 후 여기 터미널에서 Enter 누르기 > ")
    print("[AI-TREND] 세션 저장 완료")
    context.close()
