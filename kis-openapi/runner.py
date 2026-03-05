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
from functools import lru_cache
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
TRADE_LOG_FILE = Path("/home/guidda/.openclaw/workspace/kis-openapi/.daytrade_trades.jsonl")

UA = "Mozilla/5.0"


def fetch_text(url: str, encoding: str = "euc-kr") -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=10) as r:
        b = r.read()
    return b.decode(encoding, "ignore")


def top_volume_symbols(limit: int = 30) -> list[dict]:
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
            out.append({"code": code, "name": name})
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
            "entry_date": "",
            "defer_sell_next_day": False,
            "positions": [],
        }
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_legacy_fields_from_positions(state: dict):
    ps = state.get("positions") or []
    if ps:
        p = ps[0]
        state.update({
            "entered": True,
            "symbol": p.get("symbol", ""),
            "qty": int(p.get("qty", 0) or 0),
            "avg_price": int(p.get("avg_price", 0) or 0),
            "bot_managed": True,
            "entry_date": p.get("entry_date", ""),
            "defer_sell_next_day": bool(p.get("defer_sell_next_day", False)),
        })
    else:
        state.update({
            "entered": False,
            "symbol": "",
            "qty": 0,
            "avg_price": 0,
            "bot_managed": False,
            "entry_date": "",
            "defer_sell_next_day": False,
        })


def append_trade_history(side: str, symbol: str, qty: int, price: int, **extra):
    row = {
        "ts": now_kst().strftime("%Y-%m-%d %H:%M:%S KST"),
        "date": now_kst().strftime("%Y-%m-%d"),
        "side": side,
        "symbol": symbol,
        "qty": int(qty),
        "price": int(price),
    }
    row.update(extra or {})
    TRADE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRADE_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


@lru_cache(maxsize=1)
def load_sector_theme_db() -> dict:
    try:
        from sector_theme_db import SECTOR_THEME_DB
        return SECTOR_THEME_DB
    except Exception:
        return {"by_symbol": {}, "name_rules": []}


def infer_theme(symbol: str, name: str) -> str:
    db = load_sector_theme_db()
    by_symbol = db.get("by_symbol") or {}
    if symbol in by_symbol:
        return str(by_symbol.get(symbol) or "general")

    n = (name or "").lower()
    for rule in (db.get("name_rules") or []):
        theme = str(rule.get("theme") or "general")
        for kw in (rule.get("contains") or []):
            if str(kw).lower() in n:
                return theme

    return "general"


def pick_top_symbol(client: KISClient, exclude_symbols: set[str] | None = None, exclude_themes: set[str] | None = None) -> tuple[str, float, dict, str]:
    # dynamic shortlist from top-volume universe + tradeability filters
    # keep shortlist small for timely execution in cron windows
    symbols = top_volume_symbols(limit=20)
    excludes = exclude_symbols or set()
    ex_themes = exclude_themes or set()
    best = ("", -999.0, {}, "general")
    for item in symbols:
        s = item.get("code")
        nm = item.get("name", "")
        if s in excludes:
            continue
        theme = infer_theme(s, nm)
        if theme in ex_themes:
            continue
        d = client.get_domestic_quote(s)
        o = d.get("output", {})
        ok, reason = is_tradeable_quote(o)
        if not ok:
            log_event("candidate_skip", {"symbol": s, "reason": reason})
            continue
        # skip names already at upper limit when configured
        if str(os.getenv("DT_SKIP_UPPER_LIMIT_BUY", "1")).strip().lower() in {"1", "true", "yes", "y"}:
            cur = int(o.get("stck_prpr", "0") or 0)
            prev_close = int(o.get("stck_sdpr", "0") or 0)
            up = upper_limit_price(prev_close) if prev_close > 0 else 0
            if up > 0 and cur >= up:
                log_event("candidate_skip", {"symbol": s, "reason": "at_upper_limit"})
                continue
        try:
            rate = float(o.get("prdy_ctrt", "0"))
            vol_rate = float(o.get("prdy_vrss_vol_rate", "0"))
        except Exception:
            continue

        min_day_rate = env_float("DT_MIN_DAY_RATE", 1.0)
        max_day_rate = env_float("DT_MAX_DAY_RATE", 24.0)
        if rate < min_day_rate or rate > max_day_rate:
            log_event("candidate_skip", {"symbol": s, "reason": f"day_rate_out_of_range:{round(rate,2)}"})
            continue

        score = rate * 0.65 + (vol_rate / 100.0) * 0.35
        if score > best[1]:
            best = (s, score, o, theme)
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


def upper_limit_price(prev_close: int) -> int:
    if prev_close <= 0:
        return 0
    # Use floor-to-tick behavior to avoid false negatives around boundary prices.
    return round_to_tick(int(prev_close * 1.30))


def is_continuous_session(t: dt.time) -> bool:
    # Regular continuous session window
    return dt.time(9, 1) <= t <= dt.time(15, 20)


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


def env_time(name: str, default_hhmm: str) -> dt.time:
    raw = os.getenv(name, default_hhmm).strip()
    try:
        hh, mm = raw.split(':', 1)
        return dt.time(int(hh), int(mm))
    except Exception:
        hh, mm = default_hhmm.split(':', 1)
        return dt.time(int(hh), int(mm))


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


def should_hold_overnight(quote_output: dict, pnl_pct: float) -> bool:
    enabled = str(os.getenv("DT_HOLD_OVERNIGHT_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "y"}
    if not enabled:
        return False
    min_pnl = env_float("DT_HOLD_OVERNIGHT_MIN_PNL_PCT", 2.0)
    min_day_rate = env_float("DT_HOLD_OVERNIGHT_MIN_DAY_RATE", 10.0)
    try:
        day_rate = float(quote_output.get("prdy_ctrt", "0") or 0)
    except Exception:
        day_rate = 0.0
    return (pnl_pct >= min_pnl) and (day_rate >= min_day_rate)


def should_delay_eod_close(quote_output: dict, pnl_pct: float, now_t: dt.time) -> tuple[bool, str]:
    """In same-day liquidation policy, optionally delay sell from 15:15 toward close when momentum is strong."""
    enabled = str(os.getenv("DT_EOD_SMART_EXIT_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "y"}
    if not enabled:
        return False, "disabled"

    force_time = env_time("DT_EOD_FORCE_CLOSE_TIME", "15:19")
    if now_t >= force_time:
        return False, "force_close_time"

    try:
        day_rate = float(quote_output.get("prdy_ctrt", "0") or 0)
    except Exception:
        day_rate = 0.0

    strong_day_rate = env_float("DT_EOD_DELAY_MIN_DAY_RATE", 8.0)
    strong_pnl = env_float("DT_EOD_DELAY_MIN_PNL_PCT", 1.0)

    if day_rate >= strong_day_rate and pnl_pct >= strong_pnl:
        return True, f"strong_momentum(day_rate={round(day_rate,2)},pnl={round(pnl_pct,2)})"

    return False, "weak_or_neutral"


def available_cash_for_buy(balance: dict) -> int:
    o2 = (balance.get("output2") or [{}])[0]
    dnca = int(float(o2.get("dnca_tot_amt", "0") or 0))
    thdt_buy = int(float(o2.get("thdt_buy_amt", "0") or 0))
    # guard against orderable overestimation: subtract today's executed buys
    remain = max(0, dnca - thdt_buy)
    # small buffer for fees/tax/rounding
    buffer_w = env_int("DT_CASH_BUFFER_W", 1000)
    return max(0, remain - max(0, buffer_w))


def run_once(dry_run: bool, confirm: str | None):
    cfg = load_config_from_env()
    client = KISClient(cfg)
    t = now_kst().time()
    today = now_kst().strftime("%Y-%m-%d")

    state = load_state()
    if "bot_managed" not in state:
        state["bot_managed"] = False
    if "entry_date" not in state:
        state["entry_date"] = ""
    if "defer_sell_next_day" not in state:
        state["defer_sell_next_day"] = False
    if "positions" not in state:
        state["positions"] = []
    # migrate legacy single-position state into positions[]
    if not state.get("positions") and state.get("entered") and state.get("bot_managed") and state.get("symbol"):
        state["positions"] = [{
            "symbol": state.get("symbol"),
            "qty": int(state.get("qty", 0) or 0),
            "avg_price": int(state.get("avg_price", 0) or 0),
            "entry_date": state.get("entry_date") or today,
            "defer_sell_next_day": bool(state.get("defer_sell_next_day", False)),
        }]

    if state.get("date") != today:
        # Day rollover: keep open position context, reset daily counters only.
        state["date"] = today
        state["realized_pnl_pct"] = 0.0
        state["trading_disabled_today"] = False
        state["entry_legs_done"] = 0
        if state.get("defer_sell_next_day") and state.get("entry_date") != today:
            # Next day reached -> allow sell from today.
            state["defer_sell_next_day"] = False
        save_state(state)

    # 1) Entry window (env configurable, defaults to intraday)
    entry_start = env_time("DT_ENTRY_START", "09:01")
    entry_end = env_time("DT_ENTRY_END", "15:10")
    if entry_start <= t <= entry_end and is_continuous_session(t):
        if daily_loss_guard(state):
            log_event("entry_skip", {"reason": "daily_loss_guard", "realized_pnl_pct": state.get("realized_pnl_pct", 0.0)}, notify=True)
            return

        log_event("entry_scan_start", {"window": f"{entry_start.strftime('%H:%M')}-{entry_end.strftime('%H:%M')}", "mode": cfg.mode})
        held_symbols = {str(p.get("symbol", "")).strip() for p in (state.get("positions") or []) if p.get("symbol")}
        held_themes = {str(p.get("theme", "general")) for p in (state.get("positions") or [])}
        prefer_div = str(os.getenv("DT_PREFER_DIVERSIFICATION", "1")).strip().lower() in {"1", "true", "yes", "y"}
        avoid_same_theme = str(os.getenv("DT_AVOID_SAME_THEME", "1")).strip().lower() in {"1", "true", "yes", "y"}
        symbol, score, q, sel_theme = pick_top_symbol(
            client,
            exclude_symbols=held_symbols if prefer_div else set(),
            exclude_themes=held_themes if avoid_same_theme else set(),
        )
        if not symbol:
            log_event("entry_skip", {"reason": "no tradeable candidate", "held_symbols": list(held_symbols), "held_themes": list(held_themes)}, notify=True)
            return

        raw_price = int(q.get("stck_prpr", "0") or 0)
        prev_close = int(q.get("stck_sdpr", "0") or 0)
        regime = volatility_regime_from_quote(q)
        frac = position_fraction(regime)

        b = client.get_balance()
        cash = available_cash_for_buy(b)
        usable_cash = int(cash * frac)
        # hard cap per-symbol exposure (percent of available cash)
        max_symbol_exposure_pct = max(1.0, min(100.0, env_float("DT_MAX_SYMBOL_EXPOSURE_PCT", 40.0)))
        symbol_cap_cash = int(cash * (max_symbol_exposure_pct / 100.0))
        usable_cash = min(usable_cash, symbol_cap_cash)

        splits = parse_splits(os.getenv("DT_ENTRY_SPLITS", "40,35,25"))
        interval_sec = env_int("DT_ENTRY_SPLIT_INTERVAL_SEC", 45)

        total_qty = 0
        total_cost = 0
        bought_at_upper_limit = False

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
                "theme": sel_theme,
            },
            notify=True,
        )

        for i, w in enumerate(splits, start=1):
            # refresh quote each leg
            q_now = client.get_domestic_quote(symbol).get("output", {})
            leg_raw = int(q_now.get("stck_prpr", "0") or raw_price)
            leg_prev = int(q_now.get("stck_sdpr", "0") or prev_close)
            leg_price = clamp_order_price_by_krx_limit(leg_raw, leg_prev)
            up_limit_price = upper_limit_price(leg_prev)

            # don't chase stocks already at upper limit
            if str(os.getenv("DT_SKIP_UPPER_LIMIT_BUY", "1")).strip().lower() in {"1", "true", "yes", "y"} and leg_price >= up_limit_price:
                log_event("buy_leg_skip", {"symbol": symbol, "leg": i, "reason": "at_upper_limit", "price": leg_price})
                continue

            remaining_cash = max(0, usable_cash - total_cost)
            leg_budget = int(usable_cash * w)
            leg_budget = min(leg_budget, remaining_cash)
            leg_qty = calc_qty(leg_budget, leg_price)

            if leg_qty <= 0:
                log_event("buy_leg_skip", {"symbol": symbol, "leg": i, "reason": "qty=0", "budget": leg_budget, "price": leg_price})
                continue

            executed_qty = leg_qty
            if dry_run:
                log_event("buy_dry_run", {"symbol": symbol, "leg": i, "qty": leg_qty, "price": leg_price}, notify=True)
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_buy(symbol=symbol, qty=leg_qty, price=leg_price, ord_dvsn="00")
                log_event("buy_submitted", {"symbol": symbol, "leg": i, "qty": leg_qty, "price": leg_price, "result": res}, notify=True)
                ok = str((res or {}).get("rt_cd", "")) == "0"
                if not ok:
                    executed_qty = 0
                else:
                    append_trade_history(
                        "BUY",
                        symbol,
                        leg_qty,
                        leg_price,
                        leg=i,
                        is_limit_up_buy=bool(leg_price >= up_limit_price),
                        order_no=(res.get("output") or {}).get("ODNO", "") if isinstance(res, dict) else "",
                    )

            total_qty += executed_qty
            total_cost += executed_qty * leg_price
            if leg_price >= up_limit_price:
                bought_at_upper_limit = True
            state["entry_legs_done"] = i
            save_state(state)

            if i < len(splits):
                time.sleep(max(1, interval_sec))

        if total_qty > 0:
            positions = state.get("positions") or []
            found = None
            for p in positions:
                if p.get("symbol") == symbol:
                    found = p
                    break
            if found:
                prev_qty = int(found.get("qty", 0) or 0)
                prev_avg = int(found.get("avg_price", 0) or 0)
                new_qty = prev_qty + total_qty
                new_cost = prev_qty * prev_avg + total_cost
                found["qty"] = new_qty
                found["avg_price"] = int(round(new_cost / max(1, new_qty)))
                found["defer_sell_next_day"] = bool(found.get("defer_sell_next_day", False) or bought_at_upper_limit)
                found["entry_date"] = found.get("entry_date") or today
                found["theme"] = found.get("theme") or sel_theme
            else:
                positions.append({
                    "symbol": symbol,
                    "qty": int(total_qty),
                    "avg_price": int(round(total_cost / max(1, total_qty))),
                    "entry_date": today,
                    "defer_sell_next_day": bool(bought_at_upper_limit),
                    "theme": sel_theme,
                    "tp1_done": False,
                    "peak_pnl_pct": 0.0,
                })
            state["positions"] = positions
            if bought_at_upper_limit:
                log_event("sell_deferred_limit_up", {"symbol": symbol, "entry_date": today}, notify=True)
            sync_legacy_fields_from_positions(state)
            save_state(state)

    # 2) Risk/exit monitor (multi-position)
    positions = state.get("positions") or []
    updated_positions = []
    exit_start = env_time("DT_EXIT_START", "15:15")
    exit_end = env_time("DT_EXIT_END", "15:20")

    for p in positions:
        symbol = str(p.get("symbol", "")).strip()
        qty = int(p.get("qty", 0) or 0)
        avg = int(p.get("avg_price", 0) or 0)
        if not symbol or qty <= 0 or avg <= 0:
            continue

        d = client.get_domestic_quote(symbol)
        cur = int(d.get("output", {}).get("stck_prpr", "0") or 0)
        if cur <= 0:
            updated_positions.append(p)
            continue

        pnl = (cur - avg) / avg * 100
        prev_close = int(d.get("output", {}).get("stck_sdpr", "0") or 0)
        sell_price = clamp_order_price_by_krx_limit(cur, prev_close)
        defer_today = bool(p.get("defer_sell_next_day")) and p.get("entry_date") == today
        log_event("monitor", {"symbol": symbol, "cur": cur, "avg": avg, "pnl_pct": round(pnl, 2), "sell_price": sell_price, "defer_today": defer_today})

        # track best unrealized pnl for trailing exit
        prev_peak = float(p.get("peak_pnl_pct", -999.0) or -999.0)
        peak = max(prev_peak, pnl)
        p["peak_pnl_pct"] = round(peak, 4)

        closed = False

        # partial take-profit (phase 1)
        tp1_enabled = str(os.getenv("DT_TP1_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "y"}
        tp1_done = bool(p.get("tp1_done", False))
        tp1_pct = env_float("DT_TP1_PCT", 2.0)
        tp1_ratio = max(0.1, min(0.9, env_float("DT_TP1_SELL_RATIO", 0.5)))
        if (not closed) and tp1_enabled and (not tp1_done) and pnl >= tp1_pct and is_continuous_session(t):
            sell_qty = max(1, int(qty * tp1_ratio))
            sell_qty = min(sell_qty, qty)
            if dry_run:
                log_event("tp1_dry_run", {"symbol": symbol, "qty": sell_qty, "price": sell_price, "pnl_pct": round(pnl, 2)}, notify=True)
                p["tp1_done"] = True
            else:
                if cfg.mode == "real" and confirm != "REAL_ORDER":
                    raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                res = client.order_cash_sell(symbol=symbol, qty=sell_qty, price=sell_price, ord_dvsn="00")
                log_event("tp1_sell", {"symbol": symbol, "qty": sell_qty, "result": res, "pnl_pct": round(pnl, 2)}, notify=True)
                ok = str((res or {}).get("rt_cd", "")) == "0"
                if ok:
                    append_trade_history(
                        "SELL", symbol, sell_qty, sell_price, reason="tp1",
                        order_no=(res.get("output") or {}).get("ODNO", "") if isinstance(res, dict) else "",
                    )
                    part_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
                    weight = sell_qty / max(1, qty)
                    state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + (part_pnl_pct * weight)
                    p["tp1_done"] = True
                    p["qty"] = max(0, qty - sell_qty)
                    qty = int(p["qty"])
                    if qty <= 0:
                        closed = True

        # trailing profit protection (phase 2)
        trail_enabled = str(os.getenv("DT_TRAIL_ENABLED", "1")).strip().lower() in {"1", "true", "yes", "y"}
        trail_gap = max(0.2, env_float("DT_TRAIL_GAP_PCT", 1.2))
        if (not closed) and trail_enabled and bool(p.get("tp1_done", False)) and is_continuous_session(t):
            pullback = peak - pnl
            if pnl > 0 and pullback >= trail_gap:
                if dry_run:
                    log_event("trail_dry_run", {"symbol": symbol, "qty": qty, "price": sell_price, "pnl_pct": round(pnl, 2), "peak_pnl_pct": round(peak, 2)}, notify=True)
                    closed = True
                else:
                    if cfg.mode == "real" and confirm != "REAL_ORDER":
                        raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                    res = client.order_cash_sell(symbol=symbol, qty=qty, price=sell_price, ord_dvsn="00")
                    log_event("trail_sell", {"symbol": symbol, "qty": qty, "result": res, "pnl_pct": round(pnl, 2), "peak_pnl_pct": round(peak, 2)}, notify=True)
                    ok = str((res or {}).get("rt_cd", "")) == "0"
                    if ok:
                        append_trade_history(
                            "SELL", symbol, qty, sell_price, reason="trail",
                            order_no=(res.get("output") or {}).get("ODNO", "") if isinstance(res, dict) else "",
                        )
                        trade_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
                        state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + trade_pnl_pct
                        closed = True

        # stop loss -10%
        if (not closed) and pnl <= -10.0:
            if defer_today:
                log_event("stoploss_deferred_limit_up", {"symbol": symbol, "pnl_pct": round(pnl, 2)}, notify=True)
            elif not is_continuous_session(t):
                log_event("stoploss_wait", {"symbol": symbol, "reason": "not continuous session"}, notify=True)
            else:
                if dry_run:
                    log_event("stoploss_dry_run", {"symbol": symbol, "qty": qty, "price": sell_price}, notify=True)
                    closed = True
                else:
                    if cfg.mode == "real" and confirm != "REAL_ORDER":
                        raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                    res = client.order_cash_sell(symbol=symbol, qty=qty, price=sell_price, ord_dvsn="00")
                    log_event("stoploss_sell", {"symbol": symbol, "result": res}, notify=True)
                    ok = str((res or {}).get("rt_cd", "")) == "0"
                    if ok:
                        append_trade_history(
                            "SELL", symbol, qty, sell_price, reason="stoploss",
                            order_no=(res.get("output") or {}).get("ODNO", "") if isinstance(res, dict) else "",
                        )
                        closed = True

                if closed:
                    trade_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
                    state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + trade_pnl_pct
                    if daily_loss_guard(state):
                        state["trading_disabled_today"] = False
                        log_event("daily_stop_triggered", {"realized_pnl_pct": round(state['realized_pnl_pct'], 2)}, notify=True)

        # force close in configured exit window
        if (not closed) and exit_start <= t <= exit_end and is_continuous_session(t):
            if defer_today:
                log_event("eod_close_deferred_limit_up", {"symbol": symbol, "entry_date": p.get("entry_date")}, notify=True)
            elif should_hold_overnight(d.get("output", {}), pnl):
                log_event("eod_hold_overnight", {"symbol": symbol, "pnl_pct": round(pnl, 2), "window": f"{exit_start.strftime('%H:%M')}-{exit_end.strftime('%H:%M')}"}, notify=True)
            else:
                delay, reason = should_delay_eod_close(d.get("output", {}), pnl, t)
                if delay:
                    log_event("eod_close_delay", {"symbol": symbol, "reason": reason, "pnl_pct": round(pnl, 2)})
                else:
                    if dry_run:
                        log_event("eod_close_dry_run", {"symbol": symbol, "qty": qty, "price": sell_price, "reason": reason}, notify=True)
                        closed = True
                    else:
                        if cfg.mode == "real" and confirm != "REAL_ORDER":
                            raise RuntimeError("real 실행은 --confirm REAL_ORDER 필요")
                        res = client.order_cash_sell(symbol=symbol, qty=qty, price=sell_price, ord_dvsn="00")
                        log_event("eod_close_sell", {"symbol": symbol, "result": res, "reason": reason}, notify=True)
                        ok = str((res or {}).get("rt_cd", "")) == "0"
                        if ok:
                            append_trade_history(
                                "SELL", symbol, qty, sell_price, reason="eod_close",
                                order_no=(res.get("output") or {}).get("ODNO", "") if isinstance(res, dict) else "",
                            )
                            closed = True

                if closed:
                    trade_pnl_pct = ((sell_price - avg) / avg) * 100 if avg > 0 else 0.0
                    state["realized_pnl_pct"] = float(state.get("realized_pnl_pct", 0.0)) + trade_pnl_pct
                    if daily_loss_guard(state):
                        state["trading_disabled_today"] = False
                        log_event("daily_stop_triggered", {"realized_pnl_pct": round(state['realized_pnl_pct'], 2)}, notify=True)

        if not closed:
            updated_positions.append(p)

    state["positions"] = updated_positions
    sync_legacy_fields_from_positions(state)
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
