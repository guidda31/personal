#!/usr/bin/env python3
import re
import time
from sqlalchemy import text
from app.database import SessionLocal

NEWS_JOB_HINTS = [
    'daily-news-summary',
    'krx-surge-watch',
    'krx-hourly',
]


def looks_news_job(name: str) -> bool:
    n = (name or '').lower()
    return any(h in n for h in NEWS_JOB_HINTS)


def summarize(text_blob: str) -> str:
    if not text_blob:
        return ''
    t = text_blob.strip()
    # strip very long messages for list view
    return t[:1200]


def extract_title(name: str, summary: str) -> str:
    m = re.search(r'\[(.*?)\]', summary or '')
    if m:
        return m.group(1)[:250]
    first_line = (summary or '').strip().splitlines()[0] if summary else ''
    if first_line:
        return first_line[:250]
    return f"{name} 요약"


def main():
    db = SessionLocal()
    try:
        rows = db.execute(text('''
            SELECT r.run_id, r.job_id, r.summary, r.run_at_ms, j.name
            FROM cron_job_runs r
            JOIN cron_jobs j ON j.id = r.job_id
            WHERE r.status='ok'
            ORDER BY r.run_at_ms DESC
            LIMIT 300
        ''')).mappings().all()

        inserted = 0
        for r in rows:
            if not looks_news_job(r['name'] or ''):
                continue
            if not (r['summary'] or '').strip():
                continue

            exists = db.execute(text('SELECT 1 FROM news_items WHERE source=:src AND category=:cat AND published_at_ms=:ts LIMIT 1'), {
                'src': r['name'],
                'cat': 'cron-news',
                'ts': r['run_at_ms'],
            }).first()
            if exists:
                continue

            db.execute(text('''
                INSERT INTO news_items (title, source, category, summary, url, published_at_ms, created_at_ms)
                VALUES (:title, :source, :category, :summary, :url, :published_at_ms, :created_at_ms)
            '''), {
                'title': extract_title(r['name'], r['summary']),
                'source': r['name'],
                'category': 'cron-news',
                'summary': summarize(r['summary']),
                'url': None,
                'published_at_ms': r['run_at_ms'],
                'created_at_ms': int(time.time() * 1000),
            })
            inserted += 1

        db.commit()
        print(f'[news-ingest] inserted={inserted}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
