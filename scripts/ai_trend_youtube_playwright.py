#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime

from playwright.sync_api import sync_playwright

TARGET = os.getenv("AI_TREND_TARGET", "1261506890")
CHANNEL = os.getenv("AI_TREND_CHANNEL", "telegram")
PROFILE_DIR = os.getenv("AI_TREND_PW_PROFILE", "/home/guidda/.openclaw/workspace/tmp/pw-youtube-profile")
URL = "https://www.youtube.com/feed/history"


def send(msg: str):
    subprocess.run(
        [
            "openclaw",
            "message",
            "send",
            "--channel",
            CHANNEL,
            "--target",
            TARGET,
            "--message",
            msg,
        ],
        check=False,
    )


def build_report(terms: list[str]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    top = terms[:10]
    lines = [f"[AI 트렌드 데일리 | {now}]", "YouTube 검색기록 기반 키워드 TOP10"]
    for i, t in enumerate(top, 1):
        lines.append(f"{i}. {t}")
    if not top:
        lines.append("- 검색기록 키워드 추출 실패")
    return "\n".join(lines)


def extract_terms_from_html(html: str) -> list[str]:
    found = re.findall(r"/results\\?search_query=([^\"&]+)", html)
    terms: list[str] = []
    seen = set()
    for x in found:
        t = urllib.parse.unquote_plus(x).strip()
        if not t:
            continue
        if len(t) > 80:
            continue
        # exclude obvious UI noise
        if t.lower() in {"youtube", "music", "news", "shorts"}:
            continue
        if t in seen:
            continue
        seen.add(t)
        terms.append(t)
    return terms


def main():
    os.makedirs(PROFILE_DIR, exist_ok=True)
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=True,
                args=["--no-sandbox"],
            )
            page = context.new_page()
            page.goto(URL, wait_until="domcontentloaded", timeout=90000)

            # try switch to search history tab if visible
            for txt in ["검색 기록", "Search history"]:
                loc = page.get_by_role("link", name=txt)
                if loc.count() > 0:
                    loc.first.click(timeout=3000)
                    page.wait_for_timeout(1500)
                    break

            html = page.content()
            title = page.title().lower()
            url = page.url.lower()
            context.close()

        if "signin" in url or "로그인" in title or "sign in" in title:
            send("🚨 AI 트렌드 수집 실패: YouTube 로그인 세션 없음(Playwright)\n1회 수동 로그인 필요")
            return 1

        terms = extract_terms_from_html(html)
        if not terms:
            send("🚨 AI 트렌드 수집 실패: 검색기록 키워드 추출 0건")
            return 2

        send(build_report(terms))
        return 0
    except Exception as e:
        send(f"🚨 AI 트렌드 수집 실패(Playwright): {str(e)[:240]}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
