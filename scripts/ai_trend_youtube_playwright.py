#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import urllib.parse
from collections import Counter
from datetime import datetime

from playwright.sync_api import sync_playwright

TARGET = os.getenv("AI_TREND_TARGET", "1261506890")
CHANNEL = os.getenv("AI_TREND_CHANNEL", "telegram")
ACCOUNT = os.getenv("AI_TREND_ACCOUNT", "telegram-bot-2")
OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "/home/guidda/.nvm/versions/node/v22.22.0/bin/openclaw")
QUERIES = ["ai", "인공지능", "ai 에이전트", "생성형 ai", "llm"]

STOPWORDS = {
    "official", "video", "mv", "live", "feat", "ft", "shorts", "youtube", "music",
    "the", "and", "with", "from", "this", "that", "you", "your", "for",
    "공식", "뮤직비디오", "라이브", "티저", "예고", "쇼츠", "브이로그", "리액션",
    "지금", "재생", "조회수", "전", "새", "동영상", "뉴스",
}


def send(msg: str):
    subprocess.run(
        [
            OPENCLAW_BIN, "message", "send",
            "--channel", CHANNEL,
            "--account", ACCOUNT,
            "--target", TARGET,
            "--message", msg,
        ],
        check=False,
    )


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    tokens = [t.strip() for t in text.split() if len(t.strip()) >= 2]
    out = []
    for t in tokens:
        if t in STOPWORDS:
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


def build_report(keywords: list[str], videos: list[tuple[str, str]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    lines = [
        f"[AI 트렌드 데일리 | {now}]",
        "YouTube 공개 검색결과 기반 키워드 TOP10",
    ]
    for i, k in enumerate(keywords[:10], 1):
        lines.append(f"{i}. {k}")

    lines.append("")
    lines.append("중요 영상(상위 5)")
    for i, (title, link) in enumerate(videos[:5], 1):
        lines.append(f"- {i}) {title}")
        lines.append(f"  {link}")

    lines.append("")
    lines.append("우선순위 3")
    for k in keywords[:3]:
        lines.append(f"- {k}")

    lines.append("")
    lines.append("※ 개인 검색기록이 아닌 YouTube 공개 검색결과 기준")
    return "\n".join(lines)


def collect_titles(page, query: str) -> list[tuple[str, str]]:
    q = urllib.parse.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={q}&sp=CAI%253D"  # upload date
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)

    videos: list[tuple[str, str]] = []
    seen = set()
    loc = page.locator("ytd-video-renderer a#video-title")
    cnt = min(loc.count(), 12)
    for i in range(cnt):
        el = loc.nth(i)
        txt = (el.inner_text() or "").strip()
        href = (el.get_attribute("href") or "").strip()
        if not txt:
            continue
        if href.startswith("/"):
            href = f"https://www.youtube.com{href}"
        if not href.startswith("http"):
            continue
        key = (txt, href)
        if key in seen:
            continue
        seen.add(key)
        videos.append(key)
    return videos


def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()

            all_videos: list[tuple[str, str]] = []
            seen = set()
            for q in QUERIES:
                for v in collect_titles(page, q):
                    if v not in seen:
                        seen.add(v)
                        all_videos.append(v)

            browser.close()

        if not all_videos:
            send("🚨 AI 트렌드 수집 실패: YouTube 공개 검색결과 제목 추출 0건")
            return 2

        counter = Counter()
        for t, _ in all_videos[:40]:
            counter.update(tokenize(t))

        keywords = [k for k, _ in counter.most_common(15)]
        if not keywords:
            send("🚨 AI 트렌드 수집 실패: 키워드 추출 0건")
            return 3

        send(build_report(keywords, all_videos))
        return 0
    except Exception as e:
        send(f"🚨 AI 트렌드 수집 실패(Playwright 공개검색): {str(e)[:220]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
