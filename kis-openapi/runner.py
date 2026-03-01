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
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from client import KISClient, load_config_from_env

STATE_FILE = Path("/home/guidda/.openclaw/workspace/kis-openapi/.daytrade_state.json")

# For initial implementation, static shortlist (replace with screener in next sprint)
CANDIDATES = ["005930", "000660", "035420", "051910", "207940", "068270"]


def now_kst() -> dt.datetime:
    return dt.datetime.now()


def log_event(kind: str, payload: dict):
    row = {
        "ts": now_kst().strftime("%Y-%m-%d %H:%M:%S KST"),
        "kind": kind,
        "payload": payload,
    }
    print(json.dumps(row, ensure_ascii=False))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"date": "", "entered": False, "symbol": "", "qty": 0, "avg_price": 0}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_top_symbol(client: KISClient) -> tuple[str, float, dict]:
    # simplistic momentum score from quote fields
    best = ("", -999.0, {})
    for s in CANDIDATES:
        d = client.get_domestic_quote(s)
        o = d.get("output", {})
        try:
            rate = float(o.get("prdy_ctrt", "0"))
            vol_rate = float(o.get("prdy_vrss_vol_rate", "0"))
            score = rate * 0.7 + (vol_rate / 100.0) * 0.3
        except Exception:
            continue
        if score > best[1]:
            best = (s, score, o)
    return best


def calc_qty(all_cash: int, price: int) -> int:
    if price <= 0:
        return 0
    return all_cash // price


def run_once(dry_run: bool, confirm: str | None):
    cfg = load_config_from_env()
    client = KISClient(cfg)
    t = now_kst().time()
    today = now_kst().strftime("%Y-%m-%d")

    state = load_state()
    if state.get("date") != today:
        state = {"date": today, "entered": False, "symbol": "", "qty": 0, "avg_price": 0}

    # 1) Entry window (09:00~10:00)
    if not state["entered"] and dt.time(9, 0) <= t <= dt.time(10, 0):
        symbol, score, q = pick_top_symbol(client)
        price = int(q.get("stck_prpr", "0") or 0)
        b = client.get_balance()
        cash = int((b.get("output2") or [{}])[0].get("dnca_tot_amt", "0"))
        qty = calc_qty(cash, price)

        log_event("select", {"symbol": symbol, "score": score, "price": price, "cash": cash, "qty": qty})

        if qty > 0:
            if dry_run:
                log_event("buy_dry_run", {"symbol": symbol, "qty": qty, "price": price})
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_buy(symbol=symbol, qty=qty, price=price, ord_dvsn="00")
                log_event("buy_submitted", {"symbol": symbol, "qty": qty, "price": price, "result": res})
            state.update({"entered": True, "symbol": symbol, "qty": qty, "avg_price": price})
            save_state(state)

    # 2) Risk/exit monitor
    if state["entered"]:
        d = client.get_domestic_quote(state["symbol"])
        cur = int(d.get("output", {}).get("stck_prpr", "0") or 0)
        avg = int(state.get("avg_price", 0) or 0)
        qty = int(state.get("qty", 0) or 0)

        if avg > 0 and cur > 0:
            pnl = (cur - avg) / avg * 100
            log_event("monitor", {"symbol": state['symbol'], "cur": cur, "avg": avg, "pnl_pct": round(pnl, 2)})

            # stop loss -10%
            if pnl <= -10.0:
                if dry_run:
                    log_event("stoploss_dry_run", {"symbol": state['symbol'], "qty": qty, "price": cur})
                else:
                    if cfg.mode == "real" and confirm != "REAL_ORDER":
                        raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                    res = client.order_cash_sell(symbol=state["symbol"], qty=qty, price=cur, ord_dvsn="00")
                    log_event("stoploss_sell", {"result": res})
                state.update({"entered": False, "qty": 0})
                save_state(state)

        # force close 15:15+
        if state["entered"] and t >= dt.time(15, 15):
            if dry_run:
                log_event("eod_close_dry_run", {"symbol": state['symbol'], "qty": qty, "price": cur})
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_sell(symbol=state["symbol"], qty=qty, price=cur, ord_dvsn="00")
                log_event("eod_close_sell", {"result": res})
            state.update({"entered": False, "qty": 0})
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
            run_once(dry_run=args.dry_run, confirm=args.confirm)
            time.sleep(30)
    else:
        run_once(dry_run=args.dry_run, confirm=args.confirm)


if __name__ == "__main__":
    main()
