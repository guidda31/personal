import React from 'react'

const box = { border: '1px solid #334155', borderRadius: 10, padding: 10, background: '#111827' }

export default function SummaryCards({ summary, isMobile }) {
  if (!summary) return null
  const data = {
    TOTAL: summary.totalJobs,
    ENABLED: summary.enabledJobs,
    OK: summary.okJobs,
    IDLE: summary.idleJobs,
    ERROR: summary.errorJobs,
    RUNS24H: summary.runs24h,
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2,minmax(0,1fr))' : 'repeat(6,minmax(0,1fr))', gap: 8, marginBottom: 12 }}>
      {Object.entries(data).map(([k, v]) => (
        <div key={k} style={box}>
          <div style={{ color: '#94a3b8', fontSize: 12 }}>{k}</div>
          <strong style={{ fontSize: 20 }}>{v}</strong>
        </div>
      ))}
    </div>
  )
}
