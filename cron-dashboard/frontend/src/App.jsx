import React, { useEffect, useMemo, useState } from 'react'
import SummaryCards from './components/SummaryCards'
import JobsTable from './components/JobsTable'
import DetailPanel from './components/DetailPanel'

const API = import.meta.env.VITE_API_BASE || ''
const box = { border: '1px solid #334155', borderRadius: 10, padding: 10, background: '#111827' }

function makeAuthHeader(user, pass) {
  if (!user || !pass) return null
  return 'Basic ' + btoa(`${user}:${pass}`)
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

  const [authUser, setAuthUser] = useState(localStorage.getItem('cron_auth_user') || '')
  const [authPass, setAuthPass] = useState(localStorage.getItem('cron_auth_pass') || '')

  const apiGet = async (path) => {
    const headers = {}
    const auth = makeAuthHeader(authUser, authPass)
    if (auth) headers.Authorization = auth
    const res = await fetch(`${API}${path}`, { headers })
    if (!res.ok) throw new Error(`API ${res.status}`)
    return res.json()
  }

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

  const saveAuth = () => {
    localStorage.setItem('cron_auth_user', authUser)
    localStorage.setItem('cron_auth_pass', authPass)
    loadSummaryAndJobs()
  }

  const clearAuth = () => {
    setAuthUser('')
    setAuthPass('')
    localStorage.removeItem('cron_auth_user')
    localStorage.removeItem('cron_auth_pass')
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

        <div style={{ ...box, marginBottom: 12, display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 8 }}>
          <input value={authUser} onChange={(e) => setAuthUser(e.target.value)} placeholder='API 계정' style={{ ...box, color: '#e5e7eb' }} />
          <input value={authPass} onChange={(e) => setAuthPass(e.target.value)} placeholder='API 비밀번호' type='password' style={{ ...box, color: '#e5e7eb' }} />
          <button onClick={saveAuth} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>인증 저장/적용</button>
          <button onClick={clearAuth} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>인증 초기화</button>
        </div>

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
