#!/usr/bin/env python3
import json
import time
import subprocess
from sqlalchemy import text
from app.database import SessionLocal

RUNS_LIMIT = 15


def run_cmd(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout


def fetch_jobs():
    raw = run_cmd(["openclaw", "cron", "list", "--json"])
    return json.loads(raw).get("jobs", [])


def fetch_runs(job_id: str):
    try:
        raw = run_cmd(["openclaw", "cron", "runs", "--id", job_id, "--limit", str(RUNS_LIMIT)])
        return json.loads(raw).get("entries", [])
    except Exception:
        return []


def ensure_schema(db):
    db.execute(text("""
CREATE TABLE IF NOT EXISTS cron_job_runs (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  job_id VARCHAR(64) NOT NULL,
  run_at_ms BIGINT NOT NULL,
  finished_at_ms BIGINT NULL,
  status VARCHAR(32) NOT NULL,
  duration_ms INT NULL,
  delivered TINYINT(1) NULL,
  delivery_status VARCHAR(64) NULL,
  model VARCHAR(128) NULL,
  provider VARCHAR(64) NULL,
  usage_input_tokens INT NULL,
  usage_output_tokens INT NULL,
  usage_total_tokens INT NULL,
  summary MEDIUMTEXT NULL,
  raw_json LONGTEXT NULL,
  created_at_ms BIGINT NOT NULL,
  UNIQUE KEY uq_job_run (job_id, run_at_ms, status),
  INDEX idx_runs_job_time (job_id, run_at_ms DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""))
    db.execute(text("""
CREATE TABLE IF NOT EXISTS cron_job_sync_log (
  sync_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  started_at_ms BIGINT NOT NULL,
  finished_at_ms BIGINT NULL,
  status VARCHAR(16) NOT NULL,
  jobs_count INT NULL,
  runs_count INT NULL,
  error_message TEXT NULL,
  INDEX idx_sync_started (started_at_ms DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""))


def upsert_jobs(db, jobs, now_ms: int):
    for j in jobs:
        db.execute(text("""
INSERT INTO cron_jobs (
  id,name,enabled,target,agent,schedule_kind,schedule_expr,schedule_tz,session_target,wake_mode,agent_id,status,
  next_run_at_ms,last_run_at_ms,last_duration_ms,last_delivery_status,consecutive_errors,payload_kind,payload_message,
  delivery_mode,delivery_channel,delivery_to,raw_json,updated_at_ms
) VALUES (
  :id,:name,:enabled,:target,:agent,:schedule_kind,:schedule_expr,:schedule_tz,:session_target,:wake_mode,:agent_id,:status,
  :next_run_at_ms,:last_run_at_ms,:last_duration_ms,:last_delivery_status,:consecutive_errors,:payload_kind,:payload_message,
  :delivery_mode,:delivery_channel,:delivery_to,:raw_json,:updated_at_ms
)
ON DUPLICATE KEY UPDATE
  name=VALUES(name),enabled=VALUES(enabled),target=VALUES(target),agent=VALUES(agent),
  schedule_kind=VALUES(schedule_kind),schedule_expr=VALUES(schedule_expr),schedule_tz=VALUES(schedule_tz),
  session_target=VALUES(session_target),wake_mode=VALUES(wake_mode),agent_id=VALUES(agent_id),status=VALUES(status),
  next_run_at_ms=VALUES(next_run_at_ms),last_run_at_ms=VALUES(last_run_at_ms),last_duration_ms=VALUES(last_duration_ms),
  last_delivery_status=VALUES(last_delivery_status),consecutive_errors=VALUES(consecutive_errors),
  payload_kind=VALUES(payload_kind),payload_message=VALUES(payload_message),delivery_mode=VALUES(delivery_mode),
  delivery_channel=VALUES(delivery_channel),delivery_to=VALUES(delivery_to),raw_json=VALUES(raw_json),updated_at_ms=VALUES(updated_at_ms)
"""), {
            "id": j.get("id", ""),
            "name": j.get("name", ""),
            "enabled": 1 if j.get("enabled") else 0,
            "target": j.get("sessionTarget") or "-",
            "agent": j.get("agentId") or "-",
            "schedule_kind": (j.get("schedule") or {}).get("kind") or "cron",
            "schedule_expr": (j.get("schedule") or {}).get("expr") or "",
            "schedule_tz": (j.get("schedule") or {}).get("tz") or "",
            "session_target": j.get("sessionTarget"),
            "wake_mode": j.get("wakeMode"),
            "agent_id": j.get("agentId"),
            "status": ((j.get("state") or {}).get("lastStatus") or (j.get("state") or {}).get("lastRunStatus") or "idle"),
            "next_run_at_ms": (j.get("state") or {}).get("nextRunAtMs"),
            "last_run_at_ms": (j.get("state") or {}).get("lastRunAtMs"),
            "last_duration_ms": (j.get("state") or {}).get("lastDurationMs"),
            "last_delivery_status": (j.get("state") or {}).get("lastDeliveryStatus"),
            "consecutive_errors": (j.get("state") or {}).get("consecutiveErrors") or 0,
            "payload_kind": (j.get("payload") or {}).get("kind"),
            "payload_message": (j.get("payload") or {}).get("message"),
            "delivery_mode": (j.get("delivery") or {}).get("mode"),
            "delivery_channel": (j.get("delivery") or {}).get("channel"),
            "delivery_to": (j.get("delivery") or {}).get("to"),
            "raw_json": json.dumps(j, ensure_ascii=False),
            "updated_at_ms": now_ms,
        })


def upsert_runs(db, runs, now_ms: int):
    for r in runs:
        usage = r.get("usage") or {}
        run_at = r.get("runAtMs") or 0
        duration = r.get("durationMs")
        finished = run_at + duration if (run_at and duration) else None
        db.execute(text("""
INSERT INTO cron_job_runs (
  job_id,run_at_ms,finished_at_ms,status,duration_ms,delivered,delivery_status,model,provider,
  usage_input_tokens,usage_output_tokens,usage_total_tokens,summary,raw_json,created_at_ms
) VALUES (
  :job_id,:run_at_ms,:finished_at_ms,:status,:duration_ms,:delivered,:delivery_status,:model,:provider,
  :usage_input_tokens,:usage_output_tokens,:usage_total_tokens,:summary,:raw_json,:created_at_ms
)
ON DUPLICATE KEY UPDATE
  finished_at_ms=VALUES(finished_at_ms),duration_ms=VALUES(duration_ms),delivered=VALUES(delivered),
  delivery_status=VALUES(delivery_status),model=VALUES(model),provider=VALUES(provider),
  usage_input_tokens=VALUES(usage_input_tokens),usage_output_tokens=VALUES(usage_output_tokens),
  usage_total_tokens=VALUES(usage_total_tokens),summary=VALUES(summary),raw_json=VALUES(raw_json)
"""), {
            "job_id": r.get("jobId"),
            "run_at_ms": run_at,
            "finished_at_ms": finished,
            "status": r.get("status") or "unknown",
            "duration_ms": duration,
            "delivered": None if r.get("delivered") is None else (1 if r.get("delivered") else 0),
            "delivery_status": r.get("deliveryStatus"),
            "model": r.get("model"),
            "provider": r.get("provider"),
            "usage_input_tokens": usage.get("input_tokens"),
            "usage_output_tokens": usage.get("output_tokens"),
            "usage_total_tokens": usage.get("total_tokens"),
            "summary": r.get("summary"),
            "raw_json": json.dumps(r, ensure_ascii=False),
            "created_at_ms": now_ms,
        })


def sync_log(db, started, status, jobs_count=None, runs_count=None, err=None):
    db.execute(text("""
INSERT INTO cron_job_sync_log (started_at_ms, finished_at_ms, status, jobs_count, runs_count, error_message)
VALUES (:s, :f, :st, :jc, :rc, :e)
"""), {"s": started, "f": int(time.time()*1000), "st": status, "jc": jobs_count, "rc": runs_count, "e": err})


def main():
    started = int(time.time() * 1000)
    db = SessionLocal()
    try:
        ensure_schema(db)
        jobs = fetch_jobs()
        now = int(time.time() * 1000)
        upsert_jobs(db, jobs, now)

        all_runs = []
        for j in jobs:
            all_runs.extend(fetch_runs(j.get("id", "")))
        upsert_runs(db, all_runs, now)

        sync_log(db, started, "ok", len(jobs), len(all_runs), None)
        db.commit()
        print(f"[py-collector] jobs={len(jobs)} runs={len(all_runs)}")
    except Exception as e:
        db.rollback()
        try:
            sync_log(db, started, "error", None, None, str(e))
            db.commit()
        except Exception:
            pass
        print(f"[py-collector] error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
