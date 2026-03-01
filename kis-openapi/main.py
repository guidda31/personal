#!/usr/bin/env python3
import argparse
import json
import sys

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from client import KISClient, load_config_from_env


def _client() -> KISClient:
    cfg = load_config_from_env()
    return KISClient(cfg)


def _dump(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_quote(symbol: str):
    data = _client().get_domestic_quote(symbol)
    output = data.get("output", {})
    name = output.get("hts_kor_isnm") or output.get("prdt_name") or symbol
    price = output.get("stck_prpr")
    diff = output.get("prdy_vrss")
    rate = output.get("prdy_ctrt")

    print(f"종목: {name} ({symbol})")
    print(f"현재가: {price}")
    print(f"전일대비: {diff} ({rate}%)")
    print("--- raw ---")
    _dump(data)


def cmd_orderbook(symbol: str):
    data = _client().get_domestic_orderbook(symbol)
    print(f"호가 조회: {symbol}")
    _dump(data)


def cmd_conclusion(symbol: str):
    data = _client().get_domestic_conclusion(symbol)
    print(f"체결 조회: {symbol}")
    _dump(data)


def cmd_daily(symbol: str, period: str, adjusted: str):
    data = _client().get_domestic_daily(symbol, period_code=period, adj_price=adjusted)
    print(f"일봉/주봉/월봉 조회: {symbol} (period={period}, adj={adjusted})")
    _dump(data)


def cmd_balance():
    data = _client().get_balance()
    print("계좌 잔고 조회")
    _dump(data)


def _guard_real_order(confirm: str | None):
    c = _client()
    if c.cfg.mode == "real" and confirm != "REAL_ORDER":
        raise RuntimeError("real 주문은 --confirm REAL_ORDER 가 필요합니다")


def cmd_buy(symbol: str, qty: int, price: int, dry_run: bool, confirm: str | None):
    if dry_run:
        print(f"[DRY-RUN] BUY {symbol} qty={qty} price={price}")
        return
    _guard_real_order(confirm)
    data = _client().order_cash_buy(symbol, qty, price)
    print("매수 주문 결과")
    _dump(data)


def cmd_sell(symbol: str, qty: int, price: int, dry_run: bool, confirm: str | None):
    if dry_run:
        print(f"[DRY-RUN] SELL {symbol} qty={qty} price={price}")
        return
    _guard_real_order(confirm)
    data = _client().order_cash_sell(symbol, qty, price)
    print("매도 주문 결과")
    _dump(data)


def cmd_orders(start: str, end: str, side: str):
    data = _client().inquire_orders(start, end, side)
    print("주문 조회 결과")
    _dump(data)


def cmd_cancel(orgn_odno: str, symbol: str, qty: int, price: int, dry_run: bool, confirm: str | None):
    if dry_run:
        print(f"[DRY-RUN] CANCEL odno={orgn_odno} symbol={symbol} qty={qty} price={price}")
        return
    _guard_real_order(confirm)
    data = _client().cancel_order(orgn_odno, symbol, qty, price)
    print("취소 주문 결과")
    _dump(data)


def main():
    if load_dotenv:
        load_dotenv()

    p = argparse.ArgumentParser(description="KIS OpenAPI sample client")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("quote", help="국내주식 현재가 조회")
    q.add_argument("--symbol", required=True, help="예: 005930")

    ob = sub.add_parser("orderbook", help="국내주식 호가 조회")
    ob.add_argument("--symbol", required=True, help="예: 005930")

    cc = sub.add_parser("conclusion", help="국내주식 당일 체결 조회")
    cc.add_argument("--symbol", required=True, help="예: 005930")

    d = sub.add_parser("daily", help="국내주식 일/주/월봉 조회")
    d.add_argument("--symbol", required=True, help="예: 005930")
    d.add_argument("--period", default="D", choices=["D", "W", "M"], help="D/W/M")
    d.add_argument("--adjusted", default="1", choices=["0", "1"], help="수정주가 1, 원주가 0")

    sub.add_parser("balance", help="계좌 잔고 조회")

    b = sub.add_parser("buy", help="현금 매수 주문")
    b.add_argument("--symbol", required=True)
    b.add_argument("--qty", required=True, type=int)
    b.add_argument("--price", required=True, type=int)
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--confirm", default=None)

    s = sub.add_parser("sell", help="현금 매도 주문")
    s.add_argument("--symbol", required=True)
    s.add_argument("--qty", required=True, type=int)
    s.add_argument("--price", required=True, type=int)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--confirm", default=None)

    oi = sub.add_parser("orders", help="주문 조회")
    oi.add_argument("--start", required=True, help="YYYYMMDD")
    oi.add_argument("--end", required=True, help="YYYYMMDD")
    oi.add_argument("--side", default="00", choices=["00", "01", "02"], help="00 전체, 01 매도, 02 매수")

    c = sub.add_parser("cancel", help="주문 취소")
    c.add_argument("--odno", required=True, help="원주문번호")
    c.add_argument("--symbol", required=True)
    c.add_argument("--qty", required=True, type=int)
    c.add_argument("--price", default=0, type=int)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--confirm", default=None)

    args = p.parse_args()

    try:
        if args.command == "quote":
            cmd_quote(args.symbol)
        elif args.command == "orderbook":
            cmd_orderbook(args.symbol)
        elif args.command == "conclusion":
            cmd_conclusion(args.symbol)
        elif args.command == "daily":
            cmd_daily(args.symbol, args.period, args.adjusted)
        elif args.command == "balance":
            cmd_balance()
        elif args.command == "buy":
            cmd_buy(args.symbol, args.qty, args.price, args.dry_run, args.confirm)
        elif args.command == "sell":
            cmd_sell(args.symbol, args.qty, args.price, args.dry_run, args.confirm)
        elif args.command == "orders":
            cmd_orders(args.start, args.end, args.side)
        elif args.command == "cancel":
            cmd_cancel(args.odno, args.symbol, args.qty, args.price, args.dry_run, args.confirm)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
