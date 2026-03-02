import React, { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export default function App() {
  const [summary, setSummary] = useState(null)
  const [jobs, setJobs] = useState([])

  async function load() {
    const [s, j] = await Promise.all([
      fetch(`${API}/api/cron/summary`).then(r => r.json()),
      fetch(`${API}/api/cron/jobs`).then(r => r.json()),
    ])
    setSummary(s)
    setJobs(j.jobs || [])
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{fontFamily:'system-ui',padding:20, background:'#0f172a', minHeight:'100vh', color:'#e5e7eb'}}>
      <h1>Cron Dashboard (Frontend/Backend 분리)</h1>
      {summary && (
        <div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:8,marginBottom:12}}>
          {Object.entries({TOTAL:summary.totalJobs, ENABLED:summary.enabledJobs, OK:summary.okJobs, IDLE:summary.idleJobs, ERROR:summary.errorJobs, RUNS24H:summary.runs24h}).map(([k,v])=>
            <div key={k} style={{border:'1px solid #334155',borderRadius:8,padding:8,background:'#111827'}}><div>{k}</div><strong>{v}</strong></div>
          )}
        </div>
      )}
      <table style={{width:'100%',borderCollapse:'collapse',background:'#111827'}}>
        <thead><tr><th>Name</th><th>Status</th><th>Schedule</th><th>Next</th></tr></thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.id}><td>{j.name}</td><td>{j.status}</td><td>{j.schedule}</td><td>{j.nextRunAtMs || '-'}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
