#!/usr/bin/env python3
from sqlalchemy import text
from app.database import SessionLocal

MARKET_HINTS = ['증시','주식','KRX','코스피','코스닥','종목','목표가','손절','수급','매수']


def is_market(t: str) -> bool:
    s = (t or '').lower()
    return any(k.lower() in s for k in MARKET_HINTS)


def main():
    db = SessionLocal()
    try:
        rows = db.execute(text('''
            SELECT id,title,source,summary,published_at_ms
            FROM news_items
            ORDER BY COALESCE(published_at_ms, created_at_ms) DESC
            LIMIT 100
        ''')).mappings().all()

        market_like = []
        issue_like = []
        for r in rows:
            blob = f"{r['title'] or ''}\n{r['summary'] or ''}\n{r['source'] or ''}"
            if is_market(blob):
                market_like.append(r)
            else:
                issue_like.append(r)

        print('[classification-review] recent=100')
        print(f'- market_like={len(market_like)}')
        print(f'- issue_like={len(issue_like)}')

        print('\n[market_like sample 8]')
        for x in market_like[:8]:
            print(f"- ({x['id']}) {x['title'][:90]}")

        print('\n[issue_like sample 8]')
        for x in issue_like[:8]:
            print(f"- ({x['id']}) {x['title'][:90]}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
