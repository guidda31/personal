import React, { useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
const AUTH_USER = import.meta.env.VITE_AUTH_USER || ''
const AUTH_PASS = import.meta.env.VITE_AUTH_PASS || ''

async function apiGet(path) {
  const headers = {}
  if (AUTH_USER && AUTH_PASS) {
    headers['Authorization'] = 'Basic ' + btoa(`${AUTH_USER}:${AUTH_PASS}`)
  }
  const res = await fetch(`${API}${path}`, { headers })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

const box = { border: '1px solid #334155', borderRadius: 10, padding: 10, background: '#111827' }
const fmt = (ms) => (ms ? new Date(ms).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '-')

export default function App() {
  const [summary, setSummary] = useState(null)
  const [jobs, setJobs] = useState([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState(null)
  const [runs, setRuns] = useState([])
  const [raw, setRaw] = useState('')
  const [tab, setTab] = useState('info')
  const [error, setError] = useState('')

  async function loadSummaryAndJobs() {
    try {
      setError('')
      const [s, j] = await Promise.all([
        apiGet('/api/cron/summary'),
        apiGet('/api/cron/jobs'),
      ])
      setSummary(s)
      setJobs(j.jobs || [])
      if (!selectedId && (j.jobs || []).length) setSelectedId(j.jobs[0].id)
    } catch (e) {
      setError('API 인증 또는 연결 오류: ' + e.message)
    }
  }

  async function loadDetail(id) {
    if (!id) return
    try {
      const [d, r, rw] = await Promise.all([
        apiGet(`/api/cron/jobs/${id}`),
        apiGet(`/api/cron/jobs/${id}/runs?limit=20`),
        apiGet(`/api/cron/jobs/${id}/raw`),
      ])
      setDetail(d)
      setRuns(r.runs || [])
      setRaw(rw.rawJson || '')
    } catch (e) {
      setError('상세 조회 오류: ' + e.message)
    }
  }

  useEffect(() => { loadSummaryAndJobs() }, [])
  useEffect(() => { if (selectedId) loadDetail(selectedId) }, [selectedId])

  const filtered = useMemo(() => jobs.filter(j => {
    const hit = !q || j.name.toLowerCase().includes(q.toLowerCase()) || j.id.toLowerCase().includes(q.toLowerCase())
    const st = !status || String(j.status).toLowerCase() === status
    return hit && st
  }), [jobs, q, status])

  return (
    <div style={{ fontFamily: 'Inter,system-ui,sans-serif', padding: 20, background: '#0f172a', minHeight: '100vh', color: '#e5e7eb' }}>
      <h1 style={{ marginTop: 0 }}>Cron Dashboard (FE/BE 분리)</h1>
      {error && <div style={{...box, borderColor:'#7f1d1d', color:'#fca5a5', marginBottom:10}}>{error}</div>}

      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,minmax(0,1fr))', gap: 8, marginBottom: 12 }}>
          {Object.entries({ TOTAL: summary.totalJobs, ENABLED: summary.enabledJobs, OK: summary.okJobs, IDLE: summary.idleJobs, ERROR: summary.errorJobs, RUNS24H: summary.runs24h }).map(([k, v]) =>
            <div key={k} style={box}><div style={{ color: '#94a3b8', fontSize: 12 }}>{k}</div><strong style={{ fontSize: 20 }}>{v}</strong></div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={q} onChange={e => setQ(e.target.value)} placeholder='이름/ID 검색' style={{ ...box, flex: 1, color: '#e5e7eb' }} />
        <select value={status} onChange={e => setStatus(e.target.value)} style={{ ...box, color: '#e5e7eb' }}>
          <option value=''>전체 상태</option>
          <option value='ok'>ok</option>
          <option value='idle'>idle</option>
          <option value='error'>error</option>
        </select>
        <button onClick={loadSummaryAndJobs} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>새로고침</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 12 }}>
        <div style={box}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr><th style={{ textAlign: 'left' }}>Name</th><th>Status</th><th>Next</th></tr></thead>
            <tbody>
              {filtered.map(j => (
                <tr key={j.id} onClick={() => setSelectedId(j.id)} style={{ cursor: 'pointer', background: selectedId === j.id ? '#0b2536' : 'transparent' }}>
                  <td style={{ borderTop: '1px solid #263142', padding: 8 }}>
                    <strong>{j.name}</strong>
                    <div style={{ color: '#94a3b8', fontSize: 11 }}>{j.id}</div>
                  </td>
                  <td style={{ borderTop: '1px solid #263142', padding: 8 }}>{j.status}</td>
                  <td style={{ borderTop: '1px solid #263142', padding: 8 }}>{fmt(j.nextRunAtMs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={box}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <button onClick={() => setTab('info')} style={{ ...box, padding: '6px 10px', background: tab === 'info' ? '#0b2536' : '#111827', color: '#e5e7eb', cursor: 'pointer' }}>기본정보</button>
            <button onClick={() => setTab('runs')} style={{ ...box, padding: '6px 10px', background: tab === 'runs' ? '#0b2536' : '#111827', color: '#e5e7eb', cursor: 'pointer' }}>실행이력</button>
            <button onClick={() => setTab('raw')} style={{ ...box, padding: '6px 10px', background: tab === 'raw' ? '#0b2536' : '#111827', color: '#e5e7eb', cursor: 'pointer' }}>Raw JSON</button>
          </div>

          {tab === 'info' && detail && (
            <div style={{ fontSize: 13, lineHeight: 1.7 }}>
              <div><b>{detail.name}</b></div>
              <div>ID: {detail.id}</div>
              <div>Status: {detail.status}</div>
              <div>Schedule: {detail.scheduleExpr} @ {detail.scheduleTz}</div>
              <div>Next / Last: {fmt(detail.nextRunAtMs)} / {fmt(detail.lastRunAtMs)}</div>
              <div>Delivery: {detail.deliveryMode || '-'} / {detail.deliveryChannel || '-'} / {detail.deliveryTo || '-'}</div>
              <div style={{ marginTop: 8, color: '#94a3b8' }}>Payload</div>
              <pre style={{ ...box, whiteSpace: 'pre-wrap', maxHeight: 180, overflow: 'auto' }}>{detail.payloadMessage || '-'}</pre>
            </div>
          )}

          {tab === 'runs' && (
            <div>
              {runs.map(r => (
                <div key={r.runId} style={{ borderTop: '1px solid #263142', padding: '8px 0', fontSize: 12 }}>
                  <div><b>{fmt(r.runAtMs)}</b> · {r.status}</div>
                  <div style={{ color: '#94a3b8' }}>duration: {r.durationMs ?? '-'} ms · delivery: {r.deliveryStatus || '-'} · tokens: {r.totalTokens ?? '-'}</div>
                </div>
              ))}
            </div>
          )}

          {tab === 'raw' && (
            <pre style={{ ...box, whiteSpace: 'pre-wrap', maxHeight: 420, overflow: 'auto' }}>{raw || '-'}</pre>
          )}
        </div>
      </div>
    </div>
  )
}
