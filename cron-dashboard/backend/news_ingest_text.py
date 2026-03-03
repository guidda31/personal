#!/usr/bin/env python3
import argparse
import time
from app.database import SessionLocal
from sqlalchemy import text


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--category', default='cron-news')
    p.add_argument('--url', default='')
    p.add_argument('--published-at-ms', type=int, default=0)
    args = p.parse_args()

    body = input() if False else None
    import sys
    content = sys.stdin.read().strip()
    if not content:
        raise SystemExit('empty content')

    now = int(time.time() * 1000)
    pub = args.published_at_ms or now

    db = SessionLocal()
    try:
        db.execute(text('''
            INSERT INTO news_items (title, source, category, summary, url, published_at_ms, created_at_ms)
            VALUES (:title, :source, :category, :summary, :url, :published_at_ms, :created_at_ms)
        '''), {
            'title': args.title[:255],
            'source': args.source,
            'category': args.category,
            'summary': content,
            'url': args.url or None,
            'published_at_ms': pub,
            'created_at_ms': now,
        })
        db.commit()
        rid = db.execute(text('SELECT LAST_INSERT_ID() AS id')).mappings().first()['id']
        print(f'[news-ingest-text] inserted id={rid}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
