import React from 'react'

const fmt = (ms) => (ms ? new Date(ms).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '-')

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
  )
}
