#!/usr/bin/env node
const { exec } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DB_USER = process.env.CRON_DB_USER || 'guidda';
const DB_PASS = process.env.CRON_DB_PASS || '!q1w2e3r4t5';
const DB_NAME = process.env.CRON_DB_NAME || 'internal_db';
const RUNS_LIMIT = Number(process.env.CRON_RUNS_LIMIT || 15);

function run(cmd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { maxBuffer: 1024 * 1024 * 20 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout);
    });
  });
}

async function runSql(sql) {
  const f = path.join(os.tmpdir(), `cron_dashboard_${Date.now()}_${Math.random().toString(36).slice(2)}.sql`);
  fs.writeFileSync(f, sql, 'utf8');
  try {
    await run(`mariadb -u ${DB_USER} -p'${DB_PASS}' ${DB_NAME} < ${f}`);
  } finally {
    try { fs.unlinkSync(f); } catch {}
  }
}

function esc(v) {
  if (v === null || v === undefined) return 'NULL';
  return `'${String(v).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
}

async function ensureSchema() {
  const sql = `
CREATE TABLE IF NOT EXISTS cron_jobs (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  schedule_kind VARCHAR(16) NOT NULL DEFAULT 'cron',
  schedule_expr VARCHAR(64) NOT NULL,
  schedule_tz VARCHAR(64) NOT NULL,
  session_target VARCHAR(32) NULL,
  wake_mode VARCHAR(32) NULL,
  agent_id VARCHAR(64) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'idle',
  next_run_at_ms BIGINT NULL,
  last_run_at_ms BIGINT NULL,
  last_duration_ms INT NULL,
  last_delivery_status VARCHAR(64) NULL,
  consecutive_errors INT NOT NULL DEFAULT 0,
  payload_kind VARCHAR(32) NULL,
  payload_message MEDIUMTEXT NULL,
  delivery_mode VARCHAR(32) NULL,
  delivery_channel VARCHAR(32) NULL,
  delivery_to VARCHAR(255) NULL,
  raw_json LONGTEXT NULL,
  updated_at_ms BIGINT NOT NULL,
  INDEX idx_jobs_status (status),
  INDEX idx_jobs_name (name),
  INDEX idx_jobs_next (next_run_at_ms),
  INDEX idx_jobs_updated (updated_at_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
  INDEX idx_runs_job_time (job_id, run_at_ms DESC),
  INDEX idx_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
`;
  await runSql(sql);
}

async function fetchJobs() {
  const raw = await run('openclaw cron list --json');
  const parsed = JSON.parse(raw);
  return parsed.jobs || [];
}

async function upsertJobs(jobs, now) {
  if (!jobs.length) return;

  const values = jobs.map((j) => {
    const id = j.id || '';
    const name = j.name || '';
    const enabled = j.enabled ? 1 : 0;
    const scheduleKind = j.schedule?.kind || 'cron';
    const expr = j.schedule?.expr || '';
    const tz = j.schedule?.tz || '';
    const sessionTarget = j.sessionTarget || null;
    const wakeMode = j.wakeMode || null;
    const agentId = j.agentId || null;
    const status = j.state?.lastStatus || j.state?.lastRunStatus || 'idle';
    const nextRun = j.state?.nextRunAtMs ?? null;
    const lastRun = j.state?.lastRunAtMs ?? null;
    const lastDuration = j.state?.lastDurationMs ?? null;
    const lastDeliveryStatus = j.state?.lastDeliveryStatus ?? null;
    const consecutiveErrors = j.state?.consecutiveErrors ?? 0;
    const payloadKind = j.payload?.kind ?? null;
    const payloadMessage = j.payload?.message ?? null;
    const deliveryMode = j.delivery?.mode ?? null;
    const deliveryChannel = j.delivery?.channel ?? null;
    const deliveryTo = j.delivery?.to ?? null;
    const rawJson = JSON.stringify(j);

    return `(${esc(id)},${esc(name)},${enabled},${esc(scheduleKind)},${esc(expr)},${esc(tz)},${esc(sessionTarget)},${esc(wakeMode)},${esc(agentId)},${esc(status)},${nextRun === null ? 'NULL' : Number(nextRun)},${lastRun === null ? 'NULL' : Number(lastRun)},${lastDuration === null ? 'NULL' : Number(lastDuration)},${esc(lastDeliveryStatus)},${Number(consecutiveErrors)},${esc(payloadKind)},${esc(payloadMessage)},${esc(deliveryMode)},${esc(deliveryChannel)},${esc(deliveryTo)},${esc(rawJson)},${now})`;
  }).join(',\n');

  const sql = `
INSERT INTO cron_jobs (
  id,name,enabled,schedule_kind,schedule_expr,schedule_tz,session_target,wake_mode,agent_id,status,next_run_at_ms,last_run_at_ms,last_duration_ms,last_delivery_status,consecutive_errors,payload_kind,payload_message,delivery_mode,delivery_channel,delivery_to,raw_json,updated_at_ms
) VALUES
${values}
ON DUPLICATE KEY UPDATE
  name=VALUES(name),
  enabled=VALUES(enabled),
  schedule_kind=VALUES(schedule_kind),
  schedule_expr=VALUES(schedule_expr),
  schedule_tz=VALUES(schedule_tz),
  session_target=VALUES(session_target),
  wake_mode=VALUES(wake_mode),
  agent_id=VALUES(agent_id),
  status=VALUES(status),
  next_run_at_ms=VALUES(next_run_at_ms),
  last_run_at_ms=VALUES(last_run_at_ms),
  last_duration_ms=VALUES(last_duration_ms),
  last_delivery_status=VALUES(last_delivery_status),
  consecutive_errors=VALUES(consecutive_errors),
  payload_kind=VALUES(payload_kind),
  payload_message=VALUES(payload_message),
  delivery_mode=VALUES(delivery_mode),
  delivery_channel=VALUES(delivery_channel),
  delivery_to=VALUES(delivery_to),
  raw_json=VALUES(raw_json),
  updated_at_ms=VALUES(updated_at_ms);
`;
  await runSql(sql);
}

async function fetchRunsForJob(jobId) {
  try {
    const raw = await run(`openclaw cron runs --id ${jobId} --limit ${RUNS_LIMIT}`);
    const parsed = JSON.parse(raw);
    return parsed.entries || [];
  } catch {
    return [];
  }
}

async function upsertRuns(allRuns, now) {
  if (!allRuns.length) return;

  const values = allRuns.map((r) => {
    const usage = r.usage || {};
    return `(${esc(r.jobId)},${Number(r.runAtMs || 0)},${r.durationMs != null ? Number((r.runAtMs || 0) + (r.durationMs || 0)) : 'NULL'},${esc(r.status || 'unknown')},${r.durationMs != null ? Number(r.durationMs) : 'NULL'},${r.delivered == null ? 'NULL' : (r.delivered ? 1 : 0)},${esc(r.deliveryStatus ?? null)},${esc(r.model ?? null)},${esc(r.provider ?? null)},${usage.input_tokens != null ? Number(usage.input_tokens) : 'NULL'},${usage.output_tokens != null ? Number(usage.output_tokens) : 'NULL'},${usage.total_tokens != null ? Number(usage.total_tokens) : 'NULL'},${esc(r.summary ?? null)},${esc(JSON.stringify(r))},${now})`;
  }).join(',\n');

  const sql = `
INSERT INTO cron_job_runs (
  job_id,run_at_ms,finished_at_ms,status,duration_ms,delivered,delivery_status,model,provider,usage_input_tokens,usage_output_tokens,usage_total_tokens,summary,raw_json,created_at_ms
) VALUES
${values}
ON DUPLICATE KEY UPDATE
  finished_at_ms=VALUES(finished_at_ms),
  duration_ms=VALUES(duration_ms),
  delivered=VALUES(delivered),
  delivery_status=VALUES(delivery_status),
  model=VALUES(model),
  provider=VALUES(provider),
  usage_input_tokens=VALUES(usage_input_tokens),
  usage_output_tokens=VALUES(usage_output_tokens),
  usage_total_tokens=VALUES(usage_total_tokens),
  summary=VALUES(summary),
  raw_json=VALUES(raw_json);
`;
  await runSql(sql);
}

async function writeSyncLog(startedAt, status, jobsCount, runsCount, errMsg) {
  const finishedAt = Date.now();
  const sql = `
INSERT INTO cron_job_sync_log (started_at_ms, finished_at_ms, status, jobs_count, runs_count, error_message)
VALUES (${startedAt}, ${finishedAt}, ${esc(status)}, ${jobsCount == null ? 'NULL' : Number(jobsCount)}, ${runsCount == null ? 'NULL' : Number(runsCount)}, ${esc(errMsg ?? null)});
`;
  await runSql(sql);
}

(async () => {
  const startedAt = Date.now();
  try {
    await ensureSchema();
    const jobs = await fetchJobs();
    const now = Date.now();
    await upsertJobs(jobs, now);

    let runsCount = 0;
    const allRuns = [];
    for (const j of jobs) {
      const entries = await fetchRunsForJob(j.id);
      runsCount += entries.length;
      allRuns.push(...entries);
    }
    await upsertRuns(allRuns, now);

    await writeSyncLog(startedAt, 'ok', jobs.length, runsCount, null);
    console.log(`[collector] jobs=${jobs.length}, runs=${runsCount}`);
  } catch (e) {
    try { await writeSyncLog(startedAt, 'error', null, null, e.message || String(e)); } catch {}
    console.error('[collector] error:', e.message || e);
    process.exit(1);
  }
})();
