#!/usr/bin/env python3
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

UA = "Mozilla/5.0"


def fetch_text(url: str, encoding: str = "utf-8") -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=10) as r:
        data = r.read()
    return data.decode(encoding, "ignore")


def get_stock_price(code: str) -> int | None:
    # Use daily price table and pick the most recent row.
    html = fetch_text(f"https://finance.naver.com/item/sise_day.naver?code={code}", encoding="euc-kr")
    m = re.search(
        r'<td align="center"><span class="tah p10 gray03">\d{4}\.\d{2}\.\d{2}</span></td>\s*'
        r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>',
        html,
        re.S,
    )
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def get_usdkrw() -> tuple[float | None, str | None]:
    html = fetch_text("https://finance.naver.com/marketindex/", encoding="euc-kr")
    m = re.search(r'미국 USD.*?value">([^<]+)<.*?change">([^<]+)<', html, re.S)
    if not m:
        return None, None
    price = float(m.group(1).replace(",", "").strip())
    chg = m.group(2).strip()
    return price, chg


def pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100


def scenario(cur: int, target: int, stop: int) -> str:
    up = pct(target, cur)
    down = pct(stop, cur)
    if up >= 10 and down >= -5:
        return "공격형(상승여력 큼, 손절폭 제한)"
    if up >= 6 and down >= -7:
        return "균형형(기대수익/리스크 균형)"
    return "보수형(리스크 관리 우선)"


def main() -> None:
    base = Path(__file__).resolve().parent
    cfg = json.loads((base / "config.json").read_text(encoding="utf-8"))

    now = datetime.now().strftime("%Y-%m-%d(%a) %H:%M KST")
    fx, fx_chg = get_usdkrw()

    print(f"[기준일시: {now}]")
    if fx is not None:
        print(f"USD/KRW: {fx:,.2f} ({fx_chg})")
    print()
    print("관심 종목 모니터링")

    for i, s in enumerate(cfg["symbols"], start=1):
        cur = get_stock_price(s["code"])
        if cur is None:
            print(f"{i}) {s['name']}({s['market']}/{s['code']}) - 시세 조회 실패")
            continue

        target = int(s["target_price"])
        stop = int(s["stop_price"])
        up = pct(target, cur)
        down = pct(stop, cur)

        print(f"{i}) {s['name']} ({s['market']}/{s['code']})")
        print(f"   - 현재가: {cur:,}원")
        print(f"   - 목표가: {target:,}원 ({up:+.2f}%)")
        print(f"   - 손절가: {stop:,}원 ({down:+.2f}%)")
        print(f"   - 시나리오: {scenario(cur, target, stop)}")


if __name__ == "__main__":
    main()
