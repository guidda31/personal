import React from 'react'

const fmt = (ms) => (ms ? new Date(ms).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '-')

const statusStyle = (s) => {
  const v = String(s || '').toLowerCase()
  if (v === 'ok') return { color: '#22c55e', fontWeight: 700 }
  if (v === 'error') return { color: '#ef4444', fontWeight: 700 }
  if (v === 'idle') return { color: '#f59e0b', fontWeight: 700 }
  return { color: '#e5e7eb' }
}

export default function JobsTable({ jobs, selectedId, onSelect }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ textAlign: 'left' }}>Name</th>
          <th>Status</th>
          <th>Next</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((j) => (
          <tr key={j.id} onClick={() => onSelect(j.id)} style={{ cursor: 'pointer', background: selectedId === j.id ? '#0b2536' : 'transparent' }}>
            <td style={{ borderTop: '1px solid #263142', padding: '10px 8px' }}>
              <strong>{j.name}</strong>
              <div style={{ color: '#94a3b8', fontSize: 11 }}>{j.id}</div>
            </td>
            <td style={{ borderTop: '1px solid #263142', padding: '10px 8px', ...statusStyle(j.status) }}>{j.status}</td>
            <td style={{ borderTop: '1px solid #263142', padding: '10px 8px', fontSize: 12, color:'#cbd5e1' }}>{fmt(j.nextRunAtMs)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
