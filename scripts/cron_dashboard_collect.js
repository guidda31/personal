#!/usr/bin/env node
const { exec } = require('child_process');

const DB_USER = process.env.CRON_DB_USER || 'guidda';
const DB_PASS = process.env.CRON_DB_PASS || '!q1w2e3r4t5';
const DB_NAME = process.env.CRON_DB_NAME || 'internal_db';

function run(cmd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { maxBuffer: 1024 * 1024 * 10 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout);
    });
  });
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
  schedule_expr VARCHAR(64) NOT NULL,
  schedule_tz VARCHAR(64) NOT NULL,
  next_run_at_ms BIGINT NULL,
  last_run_at_ms BIGINT NULL,
  status VARCHAR(32) NOT NULL,
  target VARCHAR(64) NOT NULL,
  agent VARCHAR(64) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  raw_json LONGTEXT NULL,
  updated_at_ms BIGINT NOT NULL,
  INDEX idx_status (status),
  INDEX idx_name (name),
  INDEX idx_updated (updated_at_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
`;
  await run(`mariadb -u ${DB_USER} -p'${DB_PASS}' ${DB_NAME} -e ${esc(sql)}`);
}

async function collect() {
  const raw = await run('openclaw cron list --json');
  const parsed = JSON.parse(raw);
  const jobs = parsed.jobs || [];
  const now = Date.now();

  if (!jobs.length) {
    console.log('[collector] no jobs');
    return;
  }

  const values = jobs.map((j) => {
    const id = j.id || '';
    const name = j.name || '';
    const expr = j.schedule?.expr || '';
    const tz = j.schedule?.tz || '';
    const next = j.state?.nextRunAtMs ?? null;
    const last = j.state?.lastRunAtMs ?? null;
    const status = j.state?.lastStatus || j.state?.lastRunStatus || 'idle';
    const target = j.sessionTarget || '-';
    const agent = j.agentId || '-';
    const enabled = j.enabled ? 1 : 0;
    const rawJson = JSON.stringify(j);

    return `(${esc(id)},${esc(name)},${esc(expr)},${esc(tz)},${next === null ? 'NULL' : Number(next)},${last === null ? 'NULL' : Number(last)},${esc(status)},${esc(target)},${esc(agent)},${enabled},${esc(rawJson)},${now})`;
  }).join(',\n');

  const sql = `
INSERT INTO cron_jobs (
  id,name,schedule_expr,schedule_tz,next_run_at_ms,last_run_at_ms,status,target,agent,enabled,raw_json,updated_at_ms
) VALUES
${values}
ON DUPLICATE KEY UPDATE
  name=VALUES(name),
  schedule_expr=VALUES(schedule_expr),
  schedule_tz=VALUES(schedule_tz),
  next_run_at_ms=VALUES(next_run_at_ms),
  last_run_at_ms=VALUES(last_run_at_ms),
  status=VALUES(status),
  target=VALUES(target),
  agent=VALUES(agent),
  enabled=VALUES(enabled),
  raw_json=VALUES(raw_json),
  updated_at_ms=VALUES(updated_at_ms);
`;

  await run(`mariadb -u ${DB_USER} -p'${DB_PASS}' ${DB_NAME} -e ${esc(sql)}`);
  console.log(`[collector] upserted ${jobs.length} jobs`);
}

(async () => {
  try {
    await ensureSchema();
    await collect();
  } catch (e) {
    console.error('[collector] error:', e.message || e);
    process.exit(1);
  }
})();
