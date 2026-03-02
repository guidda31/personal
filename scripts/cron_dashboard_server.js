#!/usr/bin/env node
const http = require('http');
const { exec } = require('child_process');

const HOST = process.env.CRON_DASHBOARD_HOST || '0.0.0.0';
const PORT = Number(process.env.CRON_DASHBOARD_PORT || 8088);

function run(cmd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { maxBuffer: 1024 * 1024 * 5 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr || err.message));
      resolve(stdout);
    });
  });
}

async function getCronJobs() {
  const raw = await run('openclaw cron list --json');
  const parsed = JSON.parse(raw);
  const jobs = (parsed.jobs || []).map((j) => ({
    id: j.id,
    name: j.name,
    schedule: `${j.schedule?.expr || ''} @ ${j.schedule?.tz || ''}`,
    nextRunAtMs: j.state?.nextRunAtMs || null,
    lastRunAtMs: j.state?.lastRunAtMs || null,
    status: j.state?.lastStatus || j.state?.lastRunStatus || 'idle',
    target: j.sessionTarget || '-',
    agent: j.agentId || '-',
    enabled: !!j.enabled,
  }));
  return { total: jobs.length, jobs, updatedAt: Date.now() };
}

function pageHtml() {
  return `<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Cron Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
    h1 { margin: 0 0 12px; }
    .top { display:flex; gap:10px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }
    input, select, button { padding:8px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; font-size: 13px; }
    th { background: #f5f5f5; text-align: left; }
    .ok { color: #0a7d22; font-weight: 600; }
    .idle { color: #666; font-weight: 600; }
    .error { color: #c01818; font-weight: 700; }
  </style>
</head>
<body>
  <h1>OpenClaw Cron Dashboard</h1>
  <div class="top">
    <input id="q" placeholder="이름/ID 검색" />
    <select id="status">
      <option value="">전체 상태</option>
      <option value="ok">ok</option>
      <option value="idle">idle</option>
      <option value="error">error</option>
    </select>
    <button id="refresh">새로고침</button>
    <span id="meta"></span>
  </div>
  <table>
    <thead>
      <tr><th>Name</th><th>ID</th><th>Schedule</th><th>Next</th><th>Last</th><th>Status</th><th>Target</th><th>Agent</th><th>Enabled</th></tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
<script>
let all=[];
function fmt(ms){ if(!ms) return '-'; return new Date(ms).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}); }
function render(){
  const q=document.getElementById('q').value.toLowerCase().trim();
  const s=document.getElementById('status').value;
  const rows=all.filter(r=>{
    const hit=!q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q);
    const st=!s || String(r.status).toLowerCase()===s;
    return hit && st;
  });
  document.getElementById('rows').innerHTML = rows.map(r=>`<tr>
    <td>\${r.name}</td>
    <td><code>\${r.id}</code></td>
    <td>\${r.schedule}</td>
    <td>\${fmt(r.nextRunAtMs)}</td>
    <td>\${fmt(r.lastRunAtMs)}</td>
    <td class="\${(r.status||'').toLowerCase()}">\${r.status||'-'}</td>
    <td>\${r.target}</td>
    <td>\${r.agent}</td>
    <td>\${r.enabled?'Y':'N'}</td>
  </tr>`).join('');
}
async function load(){
  const res=await fetch('/api/cron/jobs');
  const data=await res.json();
  all=data.jobs||[];
  document.getElementById('meta').textContent = `총 \${data.total}개 · 갱신 \${new Date(data.updatedAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})}`;
  render();
}
['q','status'].forEach(id=>document.getElementById(id).addEventListener('input', render));
document.getElementById('refresh').addEventListener('click', load);
load();
setInterval(load, 60000);
</script>
</body></html>`;
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.url === '/api/cron/jobs') {
      const data = await getCronJobs();
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
      return res.end(JSON.stringify(data));
    }
    if (req.url === '/' || req.url.startsWith('/?')) {
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
