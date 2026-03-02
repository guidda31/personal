#!/usr/bin/env python3
import requests

BASE = 'http://127.0.0.1:8000'
AUTH = ('admin', 'pass123')


def fetch(path):
    r = requests.get(BASE + path, auth=AUTH, timeout=5)
    r.raise_for_status()
    return r.json()


def main():
    market = fetch('/api/news/market?limit=100').get('items', [])
    others = fetch('/api/news/others?limit=100').get('items', [])

    m_ids = {x['id'] for x in market}
    o_ids = {x['id'] for x in others}
    overlap = sorted(m_ids & o_ids)

    print('[news-split-validation]')
    print(f'- market={len(market)}')
    print(f'- others={len(others)}')
    print(f'- overlap={len(overlap)}')
    if overlap:
        print(f'- overlap_ids={overlap[:20]}')


if __name__ == '__main__':
    main()
