#!/usr/bin/env python3
import json
from pathlib import Path

from engine import (
    atr_14,
    get_daily_bars,
    get_top_volume,
    get_usdkrw,
    now_kst,
    percent,
    probability_score,
    scenario_label,
    target_stop_from_atr,
)


def auto_candidates(total: int = 50) -> list[dict]:
    half = total // 2
    raw = get_top_volume("KOSPI", 220) + get_top_volume("KOSDAQ", 220)
    etf_kw = ["KODEX", "TIGER", "KOSEF", "ARIRANG", "KBSTAR", "HANARO", "ACE", "SOL", "ETN", "레버리지", "인버스"]
    picks = [p for p in raw if not any(k.upper() in p["name"].upper() for k in etf_kw)]
    kospi = [p for p in picks if p["market"] == "KOSPI"][:half]
    kosdaq = [p for p in picks if p["market"] == "KOSDAQ"][: total - len(kospi)]
    return (kospi + kosdaq)[:total]


def load_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "config.json"
    if not cfg_path.exists():
        return {"risk_profile": "neutral", "auto_count": 50}
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_cfg()
    risk = cfg.get("risk_profile", "neutral")
    total = int(cfg.get("auto_count", 50))

    fx, fx_chg = get_usdkrw()
    cands = auto_candidates(total)

    scored = []
    for c in cands:
        bars = get_daily_bars(c["code"], pages=8)
        if len(bars) < 25:
            continue
        cur = bars[0].close
        atr = atr_14(bars)
        prob, details = probability_score(bars, name=c["name"], usdkrw=fx, usdkrw_chg_text=fx_chg)
        target, stop, regime = target_stop_from_atr(cur, atr, style=risk)
        scored.append(
            {
                **c,
                "cur": int(round(cur)),
                "prob": prob,
                "target": target,
                "stop": stop,
                "up_pct": round(percent(target, cur), 2),
                "down_pct": round(percent(stop, cur), 2),
                "details": details,
                "regime": regime,
            }
        )

    scored.sort(key=lambda x: x["prob"], reverse=True)

    print(f"[기준일시: {now_kst()}]")
    print(f"모드: invest-monitor v2 / 성향: {risk} / 후보: {len(scored)}")
    if fx is not None:
        print(f"USD/KRW: {fx:,.2f} ({fx_chg})")
    print()
    print("상위 10개 실행 후보 (확률 점수 순)")

    for i, s in enumerate(scored[:10], start=1):
        d = s["details"]
        print(f"{i}) {s['name']} ({s['market']}/{s['code']})")
        print(f"   - 현재가: {s['cur']:,}원")
        print(f"   - 상승확률 점수: {s['prob']:.2f}%")
        print(f"   - 목표가: {s['target']:,}원 ({s['up_pct']:+.2f}%)")
        print(f"   - 손절가: {s['stop']:,}원 ({s['down_pct']:+.2f}%)")
        print(f"   - 시나리오: {scenario_label(s['prob'], d['rsi14'], d['vol_ratio'], s['regime'], d['theme'])}")
        print(
            f"   - 근거: mom3 {d['mom_3']:+.2f}%, mom5 {d['mom_5']:+.2f}%, "
            f"RSI {d['rsi14']:.1f}, 거래량비 {d['vol_ratio']:.2f}x, 테마보정 {d['theme_adj']:+.3f}"
        )


if __name__ == "__main__":
    main()
