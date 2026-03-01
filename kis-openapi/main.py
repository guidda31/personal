#!/usr/bin/env python3
import argparse
import json
import sys

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from client import KISClient, load_config_from_env


def cmd_quote(symbol: str):
    cfg = load_config_from_env()
    client = KISClient(cfg)
    data = client.get_domestic_quote(symbol)

    output = data.get("output", {})
    name = output.get("hts_kor_isnm") or output.get("prdt_name") or symbol
    price = output.get("stck_prpr")
    diff = output.get("prdy_vrss")
    rate = output.get("prdy_ctrt")

    print(f"종목: {name} ({symbol})")
    print(f"현재가: {price}")
    print(f"전일대비: {diff} ({rate}%)")
    print("--- raw ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    if load_dotenv:
        load_dotenv()

    p = argparse.ArgumentParser(description="KIS OpenAPI sample client")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("quote", help="국내주식 현재가 조회")
    q.add_argument("--symbol", required=True, help="예: 005930")

    args = p.parse_args()

    try:
        if args.command == "quote":
            cmd_quote(args.symbol)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
