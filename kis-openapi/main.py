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
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
