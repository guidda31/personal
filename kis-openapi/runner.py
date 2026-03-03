#!/usr/bin/env python3
"""
KIS DayTrading Auto v1 (execution flow)
- Capital: 100% available cash
- Universe: KOSPI/KOSDAQ top liquid, ETF/ETN excluded
- Entry: once per day
- Stop: -10%
- Exit: force close before market end

Usage:
  python3 runner.py --dry-run
  python3 runner.py --run --confirm REAL_ORDER
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from client import KISClient, load_config_from_env
from notifier import send_telegram

STATE_FILE = Path("/home/guidda/.openclaw/workspace/kis-openapi/.daytrade_state.json")

UA = "Mozilla/5.0"


def fetch_text(url: str, encoding: str = "euc-kr") -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=10) as r:
        b = r.read()
    return b.decode(encoding, "ignore")


def top_volume_symbols(limit: int = 30) -> list[str]:
    out = []
    etf_kw = ["KODEX", "TIGER", "KOSEF", "ARIRANG", "KBSTAR", "HANARO", "ACE", "SOL", "ETN", "레버리지", "인버스"]
    # basic KRX hygiene filters by name
    bad_name_kw = ["스팩", "SPAC", "우", "우B", "우선주", "관리", "정리매매", "거래정지"]
    for sosok in ("0", "1"):
        html = fetch_text(f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}")
        for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
            m = re.search(r'<a href="/item/main\.naver\?code=(\d+)" class="tltle">([^<]+)</a>', tr)
            if not m:
                continue
            code, name = m.group(1), unescape(m.group(2)).strip()
            u = name.upper()
            if any(k.upper() in u for k in etf_kw):
                continue
            if any(k.upper() in u for k in bad_name_kw):
                continue
            out.append(code)
            if len(out) >= limit:
                return out
    return out


def now_kst() -> dt.datetime:
    return dt.datetime.now()


def log_event(kind: str, payload: dict, notify: bool = False):
    row = {
        "ts": now_kst().strftime("%Y-%m-%d %H:%M:%S KST"),
        "kind": kind,
        "payload": payload,
    }
    line = json.dumps(row, ensure_ascii=False)
    print(line)
    if notify:
        send_telegram(f"[KIS-AUTO] {kind}\n{json.dumps(payload, ensure_ascii=False)}")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "date": "",
            "entered": False,
            "symbol": "",
            "qty": 0,
            "avg_price": 0,
            "realized_pnl_pct": 0.0,
            "trading_disabled_today": False,
            "entry_legs_done": 0,
            "bot_managed": False,
        }
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_tradeable_quote(o: dict) -> tuple[bool, str]:
    # KIS fields may vary by account/product; use defensive checks
    warn = ""
    st = str(o.get("trht_yn", "")).upper()  # trading halt flag (Y/N in some APIs)
    if st == "Y":
        return False, "거래정지"

    # risk/admin indicators (conservative but avoid false positives)
    # NOTE: iscd_stat_cls_code often carries non-risk market state codes (e.g., 55/57),
    # so we do not hard-block on it here.
    for k in ("mrkt_warn_cls_code", "temp_stop_yn"):
        v = str(o.get(k, "")).strip().upper()
        # treat common normal codes as safe
        if v and v not in {"0", "00", "N", "NONE"}:
            return False, f"risk_flag:{k}={v}"

    cur = int(o.get("stck_prpr", "0") or 0)
    prev_close = int(o.get("stck_sdpr", "0") or 0)
    if cur <= 0 or prev_close <= 0:
        return False, "invalid_price"

    return True, warn


def pick_top_symbol(client: KISClient) -> tuple[str, float, dict]:
    # dynamic shortlist from top-volume universe + tradeability filters
    # keep shortlist small for timely execution in cron windows
    symbols = top_volume_symbols(limit=20)
    best = ("", -999.0, {})
    for s in symbols:
        d = client.get_domestic_quote(s)
        o = d.get("output", {})
        ok, reason = is_tradeable_quote(o)
        if not ok:
            log_event("candidate_skip", {"symbol": s, "reason": reason})
            continue
        try:
            rate = float(o.get("prdy_ctrt", "0"))
            vol_rate = float(o.get("prdy_vrss_vol_rate", "0"))
            score = rate * 0.65 + (vol_rate / 100.0) * 0.35
        except Exception:
            continue
        if score > best[1]:
            best = (s, score, o)
    return best


def calc_qty(all_cash: int, price: int) -> int:
    if price <= 0:
        return 0
    return all_cash // price


def tick_size(price: int) -> int:
    # Simplified KRX tick ladder
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1000


def round_to_tick(price: int) -> int:
    tk = tick_size(max(1, int(price)))
    return max(1, (int(price) // tk) * tk)


def clamp_order_price_by_krx_limit(price: int, prev_close: int) -> int:
    # KRX daily limit: ±30% from previous close
    if prev_close <= 0:
        return round_to_tick(price)
    lo = int(round(prev_close * 0.70))
    hi = int(round(prev_close * 1.30))
    p = min(max(int(price), lo), hi)
    return round_to_tick(p)


def is_continuous_session(t: dt.time) -> bool:
    # Avoid opening/closing call auction windows
    return dt.time(9, 1) <= t <= dt.time(15, 19)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except Exception:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default)).strip()))
    except Exception:
        return default


def parse_splits(s: str) -> list[float]:
    raw = [x.strip() for x in (s or "").split(",") if x.strip()]
    vals = []
    for x in raw:
        try:
            v = float(x)
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    if not vals:
        vals = [100.0]
    tot = sum(vals)
    return [v / tot for v in vals]


def volatility_regime_from_quote(o: dict) -> str:
    # Proxy regime from quote fields when minute bars are unavailable
    try:
        rate = abs(float(o.get("prdy_ctrt", "0") or 0))
    except Exception:
        rate = 0.0
    try:
        vol_rate = abs(float(o.get("prdy_vrss_vol_rate", "0") or 0))
    except Exception:
        vol_rate = 0.0
    score = rate + (vol_rate / 50.0)
    if score >= 8.0:
        return "high"
    if score >= 4.0:
        return "mid"
    return "low"


def position_fraction(regime: str) -> float:
    low = env_float("DT_POSITION_FRACTION_LOW", 1.0)
    mid = env_float("DT_POSITION_FRACTION_MID", 0.6)
    high = env_float("DT_POSITION_FRACTION_HIGH", 0.35)
    mp = {"low": low, "mid": mid, "high": high}
    v = mp.get(regime, mid)
    return max(0.05, min(1.0, v))


def daily_loss_guard(state: dict) -> bool:
    max_loss_pct = abs(env_float("DT_DAILY_MAX_LOSS_PCT", 2.5))
    realized = float(state.get("realized_pnl_pct", 0.0) or 0.0)
    return realized <= -max_loss_pct


def run_once(dry_run: bool, confirm: str | None):
    cfg = load_config_from_env()
    client = KISClient(cfg)
    t = now_kst().time()
    today = now_kst().strftime("%Y-%m-%d")

    state = load_state()
    if "bot_managed" not in state:
        state["bot_managed"] = False

    if state.get("date") != today:
        state = {
            "date": today,
            "entered": False,
            "symbol": "",
            "qty": 0,
            "avg_price": 0,
            "realized_pnl_pct": 0.0,
            "trading_disabled_today": False,
            "entry_legs_done": 0,
            "bot_managed": False,
        }

    # 1) Entry window (09:01~10:00, continuous session only)
    if not state["entered"] and dt.time(9, 1) <= t <= dt.time(10, 0) and is_continuous_session(t):
        if daily_loss_guard(state) or state.get("trading_disabled_today"):
            log_event("entry_skip", {"reason": "daily_loss_guard", "realized_pnl_pct": state.get("realized_pnl_pct", 0.0)}, notify=True)
            return

        log_event("entry_scan_start", {"window": "09:01-10:00", "mode": cfg.mode})
        symbol, score, q = pick_top_symbol(client)
        if not symbol:
            log_event("entry_skip", {"reason": "no tradeable candidate"}, notify=True)
            return

        raw_price = int(q.get("stck_prpr", "0") or 0)
        prev_close = int(q.get("stck_sdpr", "0") or 0)
        regime = volatility_regime_from_quote(q)
        frac = position_fraction(regime)

        b = client.get_balance()
        cash = int((b.get("output2") or [{}])[0].get("dnca_tot_amt", "0"))
        usable_cash = int(cash * frac)
        # hard cap per-symbol exposure (percent of available cash)
        max_symbol_exposure_pct = max(1.0, min(100.0, env_float("DT_MAX_SYMBOL_EXPOSURE_PCT", 40.0)))
        symbol_cap_cash = int(cash * (max_symbol_exposure_pct / 100.0))
        usable_cash = min(usable_cash, symbol_cap_cash)

        splits = parse_splits(os.getenv("DT_ENTRY_SPLITS", "40,35,25"))
        interval_sec = env_int("DT_ENTRY_SPLIT_INTERVAL_SEC", 45)

        total_qty = 0
        total_cost = 0

        log_event(
            "select",
            {
                "symbol": symbol,
                "score": score,
                "raw_price": raw_price,
                "prev_close": prev_close,
                "regime": regime,
                "position_fraction": frac,
                "cash": cash,
                "usable_cash": usable_cash,
                "max_symbol_exposure_pct": max_symbol_exposure_pct,
                "splits": splits,
            },
            notify=True,
        )

        for i, w in enumerate(splits, start=1):
            # refresh quote each leg
            q_now = client.get_domestic_quote(symbol).get("output", {})
            leg_raw = int(q_now.get("stck_prpr", "0") or raw_price)
            leg_prev = int(q_now.get("stck_sdpr", "0") or prev_close)
            leg_price = clamp_order_price_by_krx_limit(leg_raw, leg_prev)

            remaining_cash = max(0, usable_cash - total_cost)
            leg_budget = int(usable_cash * w)
            leg_budget = min(leg_budget, remaining_cash)
            leg_qty = calc_qty(leg_budget, leg_price)

            if leg_qty <= 0:
                log_event("buy_leg_skip", {"symbol": symbol, "leg": i, "reason": "qty=0", "budget": leg_budget, "price": leg_price})
                continue

            if dry_run:
                log_event("buy_dry_run", {"symbol": symbol, "leg": i, "qty": leg_qty, "price": leg_price}, notify=True)
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_buy(symbol=symbol, qty=leg_qty, price=leg_price, ord_dvsn="00")
                log_event("buy_submitted", {"symbol": symbol, "leg": i, "qty": leg_qty, "price": leg_price, "result": res}, notify=True)

            total_qty += leg_qty
            total_cost += leg_qty * leg_price
            state["entry_legs_done"] = i
            save_state(state)

            if i < len(splits):
                time.sleep(max(1, interval_sec))

        if total_qty > 0:
            avg_price = int(round(total_cost / total_qty))
            state.update({"entered": True, "symbol": symbol, "qty": total_qty, "avg_price": avg_price, "bot_managed": True})
            save_state(state)

    # 2) Risk/exit monitor
    if state["entered"] and not state.get("bot_managed", False):
        log_event("position_skip", {"reason": "non-bot position", "symbol": state.get("symbol", "")})
        return

    if state["entered"]:
        d = client.get_domestic_quote(state["symbol"])
        cur = int(d.get("output", {}).get("stck_prpr", "0") or 0)
        avg = int(state.get("avg_price", 0) or 0)
        qty = int(state.get("qty", 0) or 0)

        if avg > 0 and cur > 0:
            pnl = (cur - avg) / avg * 100
            prev_close = int(d.get("output", {}).get("stck_sdpr", "0") or 0)
            sell_price = clamp_order_price_by_krx_limit(cur, prev_close)
            log_event("monitor", {"symbol": state['symbol'], "cur": cur, "avg": avg, "pnl_pct": round(pnl, 2), "sell_price": sell_price})

            # stop loss -10%
            if pnl <= -10.0:
                if not is_continuous_session(t):
                    log_event("stoploss_wait", {"symbol": state['symbol'], "reason": "not continuous session"}, notify=True)
                else:
                    if dry_run:
                        log_event("stoploss_dry_run", {"symbol": state['symbol'], "qty": qty, "price": sell_price}, notify=True)
                    else:
                        if cfg.mode == "real" and confirm != "REAL_ORDER":
                            raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                        res = client.order_cash_sell(symbol=state["symbol"], qty=qty, price=sell_price, ord_dvsn="00")
                        log_event("stoploss_sell", {"result": res}, notify=True)

                    trade_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
                    state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + trade_pnl_pct
                    if daily_loss_guard(state):
                        state["trading_disabled_today"] = True
                        log_event("daily_stop_triggered", {"realized_pnl_pct": round(state['realized_pnl_pct'], 2)}, notify=True)

                    state.update({"entered": False, "qty": 0, "entry_legs_done": 0, "bot_managed": False})
                    save_state(state)

        # force close 15:15~15:19 (continuous only)
        if state["entered"] and dt.time(15, 15) <= t <= dt.time(15, 19) and is_continuous_session(t):
            prev_close = int(d.get("output", {}).get("stck_sdpr", "0") or 0)
            sell_price = clamp_order_price_by_krx_limit(cur, prev_close)
            if dry_run:
                log_event("eod_close_dry_run", {"symbol": state['symbol'], "qty": qty, "price": sell_price}, notify=True)
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_sell(symbol=state["symbol"], qty=qty, price=sell_price, ord_dvsn="00")
                log_event("eod_close_sell", {"result": res}, notify=True)

            trade_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
            state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + trade_pnl_pct
            if daily_loss_guard(state):
                state["trading_disabled_today"] = True
                log_event("daily_stop_triggered", {"realized_pnl_pct": round(state['realized_pnl_pct'], 2)}, notify=True)

            state.update({"entered": False, "qty": 0, "entry_legs_done": 0, "bot_managed": False})
            save_state(state)


def main():
    if load_dotenv:
        load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--confirm", default=None)
    p.add_argument("--loop", action="store_true", help="run loop every 30s")
    args = p.parse_args()

    if not args.dry_run and not args.run:
        args.dry_run = True

    if args.loop:
        while True:
            try:
                run_once(dry_run=args.dry_run, confirm=args.confirm)
            except Exception as e:
                log_event("error", {"message": str(e)}, notify=True)
            time.sleep(30)
    else:
        try:
            run_once(dry_run=args.dry_run, confirm=args.confirm)
        except Exception as e:
            log_event("error", {"message": str(e)}, notify=True)
            raise


if __name__ == "__main__":
    main()
