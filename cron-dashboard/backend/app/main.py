import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import get_db, SessionLocal

app = FastAPI(title='Cron Dashboard API', version='2.2.0')
security = HTTPBasic(auto_error=False)
AUTH_USER = os.getenv('CRON_DASHBOARD_AUTH_USER', '')
AUTH_PASS = os.getenv('CRON_DASHBOARD_AUTH_PASS', '')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def startup_init():
    db = SessionLocal()
    try:
        db.execute(text('''
            CREATE TABLE IF NOT EXISTS news_items (
              id BIGINT AUTO_INCREMENT PRIMARY KEY,
              title VARCHAR(255) NOT NULL,
              source VARCHAR(64) NULL,
              category VARCHAR(64) NULL,
              summary MEDIUMTEXT NULL,
              url VARCHAR(1024) NULL,
              published_at_ms BIGINT NULL,
              created_at_ms BIGINT NOT NULL,
              INDEX idx_news_published (published_at_ms DESC),
              INDEX idx_news_category (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        '''))
        db.commit()
    finally:
        db.close()


def auth_guard(credentials: HTTPBasicCredentials | None = Depends(security)):
    if not AUTH_USER or not AUTH_PASS:
        return True
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized', headers={'WWW-Authenticate': 'Basic'})
    ok_user = secrets.compare_digest(credentials.username, AUTH_USER)
    ok_pass = secrets.compare_digest(credentials.password, AUTH_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized', headers={'WWW-Authenticate': 'Basic'})
    return True


@app.get('/api/news/categories')
def news_categories(_: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    rows = db.execute(text('''
        SELECT COALESCE(category,'unknown') as category, COUNT(*) as cnt
        FROM news_items
        GROUP BY COALESCE(category,'unknown')
        ORDER BY cnt DESC
    ''')).mappings().all()
    return {'items': [{'category': r['category'], 'count': int(r['cnt'])} for r in rows]}


@app.get('/api/news/item/{news_id}')
def news_detail(news_id: int, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    row = db.execute(text('''
        SELECT id,title,source,category,summary,url,published_at_ms,created_at_ms
        FROM news_items WHERE id=:id LIMIT 1
    '''), {'id': news_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail='not found')
    return {
        'id': row['id'], 'title': row['title'], 'source': row['source'], 'category': row['category'],
        'summary': row['summary'], 'url': row['url'], 'publishedAtMs': row['published_at_ms'], 'createdAtMs': row['created_at_ms']
    }


MARKET_COND = """
(
  title LIKE '%증시%' OR title LIKE '%주식%' OR title LIKE '%KRX%' OR title LIKE '%코스피%' OR title LIKE '%코스닥%'
  OR summary LIKE '%증시%' OR summary LIKE '%주식%' OR summary LIKE '%목표가%' OR summary LIKE '%손절%'
  OR source LIKE '%krx%' OR source LIKE '%invest-monitor%'
)
"""


@app.get('/api/news/market')
def news_market(limit: int = 50, days: int = 30, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    lim = min(max(limit, 1), 200)
    days = min(max(days, 1), 365)
    min_ts = int(__import__('time').time() * 1000) - (days * 86400000)

    rows = db.execute(text(f'''
        SELECT id,title,source,category,summary,url,published_at_ms,created_at_ms
        FROM news_items
        WHERE COALESCE(published_at_ms, created_at_ms) >= :min_ts
          AND {MARKET_COND}
        ORDER BY COALESCE(published_at_ms, created_at_ms) DESC
        LIMIT :lim
    '''), {'min_ts': min_ts, 'lim': lim}).mappings().all()

    items = [{
        'id': r['id'], 'title': r['title'], 'source': r['source'], 'category': r['category'],
        'summary': r['summary'], 'url': r['url'], 'publishedAtMs': r['published_at_ms'], 'createdAtMs': r['created_at_ms']
    } for r in rows]
    return {'total': len(items), 'items': items}


@app.get('/api/news/others')
def news_others(limit: int = 50, days: int = 30, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    lim = min(max(limit, 1), 200)
    days = min(max(days, 1), 365)
    min_ts = int(__import__('time').time() * 1000) - (days * 86400000)

    rows = db.execute(text(f'''
        SELECT id,title,source,category,summary,url,published_at_ms,created_at_ms
        FROM news_items
        WHERE COALESCE(published_at_ms, created_at_ms) >= :min_ts
          AND NOT {MARKET_COND}
        ORDER BY COALESCE(published_at_ms, created_at_ms) DESC
        LIMIT :lim
    '''), {'min_ts': min_ts, 'lim': lim}).mappings().all()

    items = [{
        'id': r['id'], 'title': r['title'], 'source': r['source'], 'category': r['category'],
        'summary': r['summary'], 'url': r['url'], 'publishedAtMs': r['published_at_ms'], 'createdAtMs': r['created_at_ms']
    } for r in rows]
    return {'total': len(items), 'items': items}


@app.get('/api/news')
def news_list(
    limit: int = 30,
    category: str | None = None,
    source: str | None = None,
    q: str | None = None,
    days: int = 30,
    _: bool = Depends(auth_guard),
    db: Session = Depends(get_db),
):
    lim = min(max(limit, 1), 200)
    days = min(max(days, 1), 365)
    min_ts = int(__import__('time').time() * 1000) - (days * 86400000)

    where = ['COALESCE(published_at_ms, created_at_ms) >= :min_ts']
    params = {'lim': lim, 'min_ts': min_ts}

    if category:
        where.append('category = :category')
        params['category'] = category
    if source:
        where.append('source = :source')
        params['source'] = source
    if q:
        where.append('(title LIKE :q OR summary LIKE :q OR source LIKE :q)')
        params['q'] = f'%{q}%'

    sql = f'''
        SELECT id,title,source,category,summary,url,published_at_ms,created_at_ms
        FROM news_items
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(published_at_ms, created_at_ms) DESC
        LIMIT :lim
    '''

    rows = db.execute(text(sql), params).mappings().all()
    items = [{
        'id': r['id'], 'title': r['title'], 'source': r['source'], 'category': r['category'],
        'summary': r['summary'], 'url': r['url'], 'publishedAtMs': r['published_at_ms'], 'createdAtMs': r['created_at_ms']
    } for r in rows]
    return {'total': len(items), 'items': items}


@app.get('/api/cron/jobs')
def cron_jobs(_: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    rows = db.execute(text('''
        SELECT id,name,enabled,schedule_expr,schedule_tz,status,next_run_at_ms,last_run_at_ms,last_duration_ms,session_target,agent_id,updated_at_ms
        FROM cron_jobs
        ORDER BY name ASC
    ''')).mappings().all()
    jobs = []
    updated = 0
    for r in rows:
        updated = max(updated, r['updated_at_ms'] or 0)
        jobs.append({
            'id': r['id'], 'name': r['name'], 'enabled': bool(r['enabled']),
            'schedule': f"{r['schedule_expr'] or ''} @ {r['schedule_tz'] or ''}",
            'status': r['status'] or 'idle', 'nextRunAtMs': r['next_run_at_ms'],
            'lastRunAtMs': r['last_run_at_ms'], 'lastDurationMs': r['last_duration_ms'],
            'target': r['session_target'] or '-', 'agent': r['agent_id'] or '-', 'updatedAtMs': r['updated_at_ms'],
        })
    return {'total': len(jobs), 'jobs': jobs, 'updatedAt': updated}


@app.get('/api/cron/summary')
def cron_summary(_: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    row = db.execute(text('''
        SELECT
          (SELECT COUNT(*) FROM cron_jobs) AS total_jobs,
          (SELECT COUNT(*) FROM cron_jobs WHERE enabled=1) AS enabled_jobs,
          (SELECT COUNT(*) FROM cron_jobs WHERE status='ok') AS ok_jobs,
          (SELECT COUNT(*) FROM cron_jobs WHERE status='idle') AS idle_jobs,
          (SELECT COUNT(*) FROM cron_jobs WHERE status='error') AS error_jobs,
          (SELECT COUNT(*) FROM cron_job_runs WHERE run_at_ms >= (UNIX_TIMESTAMP()*1000 - 86400000)) AS runs_24h
    ''')).mappings().first()
    return {
        'totalJobs': int(row['total_jobs'] or 0), 'enabledJobs': int(row['enabled_jobs'] or 0),
        'okJobs': int(row['ok_jobs'] or 0), 'idleJobs': int(row['idle_jobs'] or 0),
        'errorJobs': int(row['error_jobs'] or 0), 'runs24h': int(row['runs_24h'] or 0),
    }


@app.get('/api/cron/jobs/{job_id}')
def cron_job_detail(job_id: str, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    row = db.execute(text('''
        SELECT id,name,enabled,schedule_kind,schedule_expr,schedule_tz,session_target,wake_mode,agent_id,status,
               next_run_at_ms,last_run_at_ms,last_duration_ms,last_delivery_status,consecutive_errors,
               payload_kind,payload_message,delivery_mode,delivery_channel,delivery_to,updated_at_ms
        FROM cron_jobs WHERE id=:id LIMIT 1
    '''), {'id': job_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail='not found')
    return {
        'id': row['id'], 'name': row['name'], 'enabled': bool(row['enabled']),
        'scheduleKind': row['schedule_kind'], 'scheduleExpr': row['schedule_expr'], 'scheduleTz': row['schedule_tz'],
        'sessionTarget': row['session_target'], 'wakeMode': row['wake_mode'], 'agentId': row['agent_id'],
        'status': row['status'], 'nextRunAtMs': row['next_run_at_ms'], 'lastRunAtMs': row['last_run_at_ms'],
        'lastDurationMs': row['last_duration_ms'], 'lastDeliveryStatus': row['last_delivery_status'],
        'consecutiveErrors': int(row['consecutive_errors'] or 0), 'payloadKind': row['payload_kind'],
        'payloadMessage': row['payload_message'], 'deliveryMode': row['delivery_mode'],
        'deliveryChannel': row['delivery_channel'], 'deliveryTo': row['delivery_to'], 'updatedAtMs': row['updated_at_ms']
    }


@app.get('/api/cron/jobs/{job_id}/runs')
def cron_job_runs(job_id: str, limit: int = 20, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    lim = min(max(limit, 1), 100)
    rows = db.execute(text('''
        SELECT run_id,run_at_ms,status,duration_ms,delivered,delivery_status,model,provider,usage_total_tokens,summary
        FROM cron_job_runs
        WHERE job_id=:id
        ORDER BY run_at_ms DESC
        LIMIT :lim
    '''), {'id': job_id, 'lim': lim}).mappings().all()
    runs = [{
        'runId': r['run_id'], 'runAtMs': r['run_at_ms'], 'status': r['status'], 'durationMs': r['duration_ms'],
        'delivered': None if r['delivered'] is None else bool(r['delivered']),
        'deliveryStatus': r['delivery_status'], 'model': r['model'], 'provider': r['provider'],
        'totalTokens': r['usage_total_tokens'], 'summary': r['summary']
    } for r in rows]
    return {'id': job_id, 'runs': runs}


@app.get('/api/cron/jobs/{job_id}/raw')
def cron_job_raw(job_id: str, _: bool = Depends(auth_guard), db: Session = Depends(get_db)):
    row = db.execute(text('SELECT raw_json FROM cron_jobs WHERE id=:id LIMIT 1'), {'id': job_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail='not found')
    return {'id': job_id, 'rawJson': row['raw_json']}
