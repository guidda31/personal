#!/usr/bin/env python3
"""
Simple walk-forward sanity backtest for invest-monitor v2 score.
Metric: next-day up/down hit-rate when signal prob >= threshold.
"""
from engine import get_top_volume, get_daily_bars, probability_score


def build_universe(n_each: int = 20):
    raw = get_top_volume("KOSPI", n_each) + get_top_volume("KOSDAQ", n_each)
    etf_kw = ["KODEX", "TIGER", "KOSEF", "ARIRANG", "KBSTAR", "HANARO", "ACE", "SOL", "ETN", "레버리지", "인버스"]
    return [r for r in raw if not any(k.upper() in r["name"].upper() for k in etf_kw)]


def main():
    universe = build_universe(30)
    threshold = 58.0
    total = 0
    hit = 0

    for u in universe:
        bars = get_daily_bars(u["code"], pages=10)
        # bars: latest -> old
        if len(bars) < 40:
            continue

        # walk-forward over recent 15 sessions
        for i in range(0, 15):
            # slice so that index i is "today" in historical frame
            window = bars[i : i + 35]
            if len(window) < 25:
                continue
            prob, _ = probability_score(window)
            if prob < threshold:
                continue
            # next day return in that frame: day i vs i+1 (latest-first)
            today_close = window[0].close
            next_close = window[1].close
            ret = (today_close - next_close) / next_close * 100
            total += 1
            if ret > 0:
                hit += 1

    if total == 0:
        print("No qualified signals in backtest window.")
        return

    hr = hit / total * 100
    print(f"Signals: {total}")
    print(f"Hit-rate: {hr:.2f}% (threshold={threshold:.1f})")


if __name__ == "__main__":
    main()
