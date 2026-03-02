import React, { useEffect, useMemo, useState } from 'react'
import SummaryCards from './components/SummaryCards'
import JobsTable from './components/JobsTable'
import DetailPanel from './components/DetailPanel'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
const AUTH_USER = import.meta.env.VITE_AUTH_USER || ''
const AUTH_PASS = import.meta.env.VITE_AUTH_PASS || ''
const box = { border: '1px solid #334155', borderRadius: 10, padding: 10, background: '#111827' }

async function apiGet(path) {
  const headers = {}
  if (AUTH_USER && AUTH_PASS) headers.Authorization = 'Basic ' + btoa(`${AUTH_USER}:${AUTH_PASS}`)
  const res = await fetch(`${API}${path}`, { headers })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

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

  const loadSummaryAndJobs = async () => {
    try {
      setError('')
      const [s, j] = await Promise.all([apiGet('/api/cron/summary'), apiGet('/api/cron/jobs')])
      setSummary(s)
      setJobs(j.jobs || [])
      if (!selectedId && (j.jobs || []).length) setSelectedId(j.jobs[0].id)
    } catch (e) {
      setError('API 인증 또는 연결 오류: ' + e.message)
    }
  }

  const loadDetail = async (id) => {
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

  const filtered = useMemo(() => jobs.filter((j) => {
    const hit = !q || j.name.toLowerCase().includes(q.toLowerCase()) || j.id.toLowerCase().includes(q.toLowerCase())
    const st = !status || String(j.status).toLowerCase() === status
    return hit && st
  }), [jobs, q, status])

  return (
    <div style={{ fontFamily: 'Inter,system-ui,sans-serif', background: '#0f172a', minHeight: '100vh', color: '#e5e7eb', display: 'grid', gridTemplateColumns: '220px 1fr' }}>
      <aside style={{ borderRight: '1px solid #1f2937', padding: 16, background: '#0b1220' }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Dashboard</div>
        <div style={{ ...box, background: '#0b2536', borderColor: '#1f4b63', color: '#7dd3fc' }}>대시보드</div>
      </aside>

      <main style={{ padding: 20 }}>
        <h1 style={{ marginTop: 0 }}>대시보드</h1>
        {error && <div style={{ ...box, borderColor: '#7f1d1d', color: '#fca5a5', marginBottom: 10 }}>{error}</div>}

        <SummaryCards summary={summary} />

        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder='이름/ID 검색' style={{ ...box, flex: 1, color: '#e5e7eb' }} />
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ ...box, color: '#e5e7eb' }}>
            <option value=''>전체 상태</option>
            <option value='ok'>ok</option>
            <option value='idle'>idle</option>
            <option value='error'>error</option>
          </select>
          <button onClick={loadSummaryAndJobs} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>새로고침</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 12 }}>
          <div style={box}><JobsTable jobs={filtered} selectedId={selectedId} onSelect={setSelectedId} /></div>
          <div style={box}><DetailPanel tab={tab} setTab={setTab} detail={detail} runs={runs} raw={raw} /></div>
        </div>
      </main>
    </div>
  )
}
