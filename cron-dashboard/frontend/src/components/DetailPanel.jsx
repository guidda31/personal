import React from 'react'

const box = { border: '1px solid #334155', borderRadius: 10, padding: 10, background: '#111827' }
const fmt = (ms) => (ms ? new Date(ms).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '-')

export default function DetailPanel({ tab, setTab, detail, runs, raw }) {
  return (
    <div>
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
          {runs.map((r) => (
            <div key={r.runId} style={{ borderTop: '1px solid #263142', padding: '8px 0', fontSize: 12 }}>
              <div><b>{fmt(r.runAtMs)}</b> · {r.status}</div>
              <div style={{ color: '#94a3b8' }}>duration: {r.durationMs ?? '-'} ms · delivery: {r.deliveryStatus || '-'} · tokens: {r.totalTokens ?? '-'}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'raw' && <pre style={{ ...box, whiteSpace: 'pre-wrap', maxHeight: 420, overflow: 'auto' }}>{raw || '-'}</pre>}
    </div>
  )
}
