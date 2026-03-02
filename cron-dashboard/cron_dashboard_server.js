#!/usr/bin/env node
const http = require('http');
const { exec } = require('child_process');
const { URL } = require('url');

const HOST = process.env.CRON_DASHBOARD_HOST || '0.0.0.0';
const PORT = Number(process.env.CRON_DASHBOARD_PORT || 8088);
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

function safe(v) {
  return String(v || '').replace(/[^a-zA-Z0-9:_\-.]/g, '');
}

async function queryRows(sql) {
  const out = await run(`mariadb -u ${DB_USER} -p'${DB_PASS}' ${DB_NAME} -N -B -e ${JSON.stringify(sql)}`);
  return out.trim() ? out.trim().split('\n').map((line) => line.split('\t')) : [];
}

async function getJobs() {
  const rows = await queryRows(`
SELECT id,name,enabled,schedule_expr,schedule_tz,status,next_run_at_ms,last_run_at_ms,last_duration_ms,session_target,agent_id,updated_at_ms
FROM cron_jobs
ORDER BY name ASC;
`);

  const jobs = rows.map((r) => ({
    id: r[0],
    name: r[1],
    enabled: r[2] === '1',
    schedule: `${r[3] || ''} @ ${r[4] || ''}`,
    status: r[5] || 'idle',
    nextRunAtMs: r[6] ? Number(r[6]) : null,
    lastRunAtMs: r[7] ? Number(r[7]) : null,
    lastDurationMs: r[8] ? Number(r[8]) : null,
    target: r[9] || '-',
    agent: r[10] || '-',
    updatedAtMs: r[11] ? Number(r[11]) : null,
  }));

  return {
    total: jobs.length,
    jobs,
    updatedAt: jobs.reduce((m, j) => Math.max(m, j.updatedAtMs || 0), 0) || Date.now(),
  };
}

async function getJobDetail(id) {
  const jobId = safe(id);
  if (!jobId) return null;

  const rows = await queryRows(`
SELECT id,name,enabled,schedule_kind,schedule_expr,schedule_tz,session_target,wake_mode,agent_id,status,next_run_at_ms,last_run_at_ms,last_duration_ms,last_delivery_status,consecutive_errors,payload_kind,payload_message,delivery_mode,delivery_channel,delivery_to,updated_at_ms
FROM cron_jobs
WHERE id='${jobId}'
LIMIT 1;
`);

  if (!rows.length) return null;
  const r = rows[0];
  return {
    id: r[0],
    name: r[1],
    enabled: r[2] === '1',
    scheduleKind: r[3],
    scheduleExpr: r[4],
    scheduleTz: r[5],
    sessionTarget: r[6],
    wakeMode: r[7],
    agentId: r[8],
    status: r[9],
    nextRunAtMs: r[10] ? Number(r[10]) : null,
    lastRunAtMs: r[11] ? Number(r[11]) : null,
    lastDurationMs: r[12] ? Number(r[12]) : null,
    lastDeliveryStatus: r[13],
    consecutiveErrors: Number(r[14] || 0),
    payloadKind: r[15],
    payloadMessage: r[16],
    deliveryMode: r[17],
    deliveryChannel: r[18],
    deliveryTo: r[19],
    updatedAtMs: r[20] ? Number(r[20]) : null,
  };
}

async function getJobRuns(id, limit = 20) {
  const jobId = safe(id);
  const lim = Math.min(Math.max(Number(limit) || 20, 1), 100);
  if (!jobId) return [];

  const rows = await queryRows(`
SELECT run_id,run_at_ms,status,duration_ms,delivered,delivery_status,model,provider,usage_total_tokens,summary
FROM cron_job_runs
WHERE job_id='${jobId}'
ORDER BY run_at_ms DESC
LIMIT ${lim};
`);

  return rows.map((r) => ({
    runId: Number(r[0]),
    runAtMs: r[1] ? Number(r[1]) : null,
    status: r[2] || '-',
    durationMs: r[3] ? Number(r[3]) : null,
    delivered: r[4] === '1' ? true : r[4] === '0' ? false : null,
    deliveryStatus: r[5] || '-',
    model: r[6] || '-',
    provider: r[7] || '-',
    totalTokens: r[8] ? Number(r[8]) : null,
    summary: r[9] || '',
  }));
}

function pageHtml() {
  return `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Cron Dashboard 2.0</title>
<style>
:root{
  --bg:#0f172a; --panel:#111827; --card:#1f2937; --line:#334155; --text:#e5e7eb; --muted:#94a3b8;
  --ok:#22c55e; --idle:#f59e0b; --error:#ef4444; --brand:#38bdf8;
}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#0b1220,#0f172a);color:var(--text);font-family:Inter,system-ui,Segoe UI,Roboto,sans-serif}
.header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;background:rgba(2,6,23,.55);backdrop-filter:blur(6px);position:sticky;top:0;z-index:20}
.title{font-size:18px;font-weight:700}
.wrap{display:grid;grid-template-columns:1fr;gap:14px;padding:16px;max-width:1400px;margin:0 auto}
.menu{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between}
.badge{padding:4px 10px;border-radius:999px;background:#0b2536;border:1px solid #1f4b63;color:#7dd3fc;font-size:12px}
.top{display:flex;gap:8px;flex-wrap:wrap}
input,select,button{background:#0b1220;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:9px 10px}
button{cursor:pointer}
button:hover{border-color:#4b5563}
.layout{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.card h2{font-size:14px;margin:0;padding:12px 14px;border-bottom:1px solid var(--line);color:#cbd5e1}
.table-wrap{max-height:70vh;overflow:auto}
table{width:100%;border-collapse:collapse}
th,td{padding:9px 10px;border-bottom:1px solid #263142;font-size:12px;vertical-align:top}
th{position:sticky;top:0;background:#0f172a;z-index:1;text-align:left;color:#cbd5e1}
tr:hover{background:#0b1220}
tr.active{background:#102236}
.status{font-weight:700}
.ok{color:var(--ok)} .idle{color:var(--idle)} .error{color:var(--error)}
.meta{color:var(--muted);font-size:12px}
.kv{display:grid;grid-template-columns:130px 1fr;gap:8px;font-size:12px;padding:14px}
.kv div:nth-child(odd){color:#94a3b8}
pre{margin:0;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:10px;white-space:pre-wrap;max-height:180px;overflow:auto;color:#cbd5e1}
.run-item{padding:10px 12px;border-bottom:1px solid #253042;font-size:12px}
.run-item:last-child{border-bottom:0}
@media (max-width:1100px){.layout{grid-template-columns:1fr}}
</style>
</head>
<body>
  <div class="header">
    <div class="title">OpenClaw Cron Dashboard 2.0</div>
    <div class="meta" id="meta">로딩중...</div>
  </div>
  <div class="wrap">
    <div class="menu">
      <div><strong>Cron Dashboard</strong> <span class="meta">(메뉴 1개 · 목록/상세)</span></div>
      <span class="badge">DB-backed</span>
    </div>

    <div class="top">
      <input id="q" placeholder="이름/ID 검색" />
      <select id="status">
        <option value="">전체 상태</option>
        <option value="ok">ok</option>
        <option value="idle">idle</option>
        <option value="error">error</option>
      </select>
      <button id="refresh">새로고침</button>
    </div>

    <div class="layout">
      <div class="card">
        <h2>목록</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Status</th><th>Next</th><th>Last</th><th>Schedule</th><th>Agent</th></tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2 id="detailTitle">상세</h2>
        <div id="detailBody" class="kv"><div>선택</div><div>좌측 목록에서 항목을 선택하세요.</div></div>
        <h2>최근 실행 이력</h2>
        <div id="runs"></div>
      </div>
    </div>
  </div>
<script>
let all=[]; let selectedId=null;
const elRows=document.getElementById('rows');
const elMeta=document.getElementById('meta');
const elDetailTitle=document.getElementById('detailTitle');
const elDetailBody=document.getElementById('detailBody');
const elRuns=document.getElementById('runs');

function fmt(ms){ if(!ms) return '-'; return new Date(ms).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}); }
function esc(s){ return String(s ?? '').replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])); }

function filterRows(){
  const q=document.getElementById('q').value.toLowerCase().trim();
  const s=document.getElementById('status').value;
  return all.filter(r=>{
    const hit=!q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q);
    const st=!s || String(r.status).toLowerCase()===s;
    return hit && st;
  });
}

function renderTable(){
  const rows=filterRows();
  elRows.innerHTML=rows.map(r=>`<tr data-id="${r.id}" class="${selectedId===r.id?'active':''}">
    <td><strong>${esc(r.name)}</strong><div class="meta">${esc(r.id)}</div></td>
    <td class="status ${esc(String(r.status||'').toLowerCase())}">${esc(r.status||'-')}</td>
    <td>${fmt(r.nextRunAtMs)}</td>
    <td>${fmt(r.lastRunAtMs)}</td>
    <td>${esc(r.schedule)}</td>
    <td>${esc(r.agent||'-')}</td>
  </tr>`).join('');

  [...elRows.querySelectorAll('tr')].forEach(tr=>{
    tr.onclick=()=>{ selectedId=tr.dataset.id; renderTable(); loadDetail(selectedId); };
  });
}

async function loadJobs(){
  const res=await fetch('/api/cron/jobs');
  const data=await res.json();
  all=data.jobs||[];
  elMeta.textContent=`총 ${data.total}개 · DB 갱신 ${fmt(data.updatedAt)}`;
  if(!selectedId && all.length) selectedId=all[0].id;
  renderTable();
  if(selectedId) loadDetail(selectedId);
}

async function loadDetail(id){
  const [dRes,rRes]=await Promise.all([
    fetch('/api/cron/jobs/'+encodeURIComponent(id)),
    fetch('/api/cron/jobs/'+encodeURIComponent(id)+'/runs?limit=20')
  ]);
  const d=await dRes.json();
  const r=await rRes.json();

  if(!d || d.error){
    elDetailTitle.textContent='상세';
    elDetailBody.innerHTML='<div>오류</div><div>상세 조회 실패</div>';
    elRuns.innerHTML='';
    return;
  }

  elDetailTitle.textContent=`상세 · ${d.name}`;
  elDetailBody.innerHTML=`
    <div>ID</div><div><code>${esc(d.id)}</code></div>
    <div>Enabled</div><div>${d.enabled?'Y':'N'}</div>
    <div>Status</div><div class="status ${esc(String(d.status||'').toLowerCase())}">${esc(d.status||'-')}</div>
    <div>Schedule</div><div>${esc(d.scheduleExpr||'')} @ ${esc(d.scheduleTz||'')}</div>
    <div>Next / Last</div><div>${fmt(d.nextRunAtMs)} / ${fmt(d.lastRunAtMs)}</div>
    <div>Duration / Errors</div><div>${d.lastDurationMs||'-'} ms / ${d.consecutiveErrors||0}</div>
    <div>Agent / Target</div><div>${esc(d.agentId||'-')} / ${esc(d.sessionTarget||'-')}</div>
    <div>Delivery</div><div>${esc(d.deliveryMode||'-')} / ${esc(d.deliveryChannel||'-')} / ${esc(d.deliveryTo||'-')}</div>
    <div>Payload Kind</div><div>${esc(d.payloadKind||'-')}</div>
    <div>Payload Message</div><div><pre>${esc(d.payloadMessage||'')}</pre></div>
  `;

  const runs=r.runs||[];
  elRuns.innerHTML=runs.length? runs.map(x=>`<div class="run-item">
    <div><strong>${fmt(x.runAtMs)}</strong> · <span class="status ${esc(String(x.status||'').toLowerCase())}">${esc(x.status)}</span></div>
    <div class="meta">duration: ${x.durationMs??'-'} ms · delivered: ${x.delivered===null?'-':(x.delivered?'Y':'N')} · delivery: ${esc(x.deliveryStatus||'-')}</div>
    <div class="meta">model: ${esc(x.model||'-')} · tokens: ${x.totalTokens??'-'}</div>
  </div>`).join('') : '<div class="run-item">이력 없음</div>';
}

document.getElementById('q').addEventListener('input', renderTable);
document.getElementById('status').addEventListener('input', renderTable);
document.getElementById('refresh').addEventListener('click', loadJobs);
loadJobs();
setInterval(loadJobs, 60000);
</script>
</body></html>`;
}

const server = http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

    if (u.pathname === '/api/cron/jobs') {
      const data = await getJobs();
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      return res.end(JSON.stringify(data));
    }

    if (u.pathname.startsWith('/api/cron/jobs/')) {
      const seg = u.pathname.split('/').filter(Boolean); // api cron jobs :id [runs]
      const id = seg[3] || '';
      if (seg[4] === 'runs') {
        const limit = Number(u.searchParams.get('limit') || '20');
        const runs = await getJobRuns(id, limit);
        res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
        return res.end(JSON.stringify({ id, runs }));
      }
      const detail = await getJobDetail(id);
      if (!detail) {
        res.writeHead(404, { 'content-type': 'application/json; charset=utf-8' });
        return res.end(JSON.stringify({ error: 'not found' }));
      }
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      return res.end(JSON.stringify(detail));
    }

    if (u.pathname === '/' ) {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      return res.end(pageHtml());
    }

    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('Not Found');
  } catch (e) {
    res.writeHead(500, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ error: String(e.message || e) }));
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[cron-dashboard] listening on http://${HOST}:${PORT}`);
});
