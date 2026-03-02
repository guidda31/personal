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
  const [menu, setMenu] = useState('dashboard')
  const [summary, setSummary] = useState(null)
  const [jobs, setJobs] = useState([])
  const [news, setNews] = useState([])
  const [stockNews, setStockNews] = useState([])
  const [newsCategories, setNewsCategories] = useState([])
  const [newsQ, setNewsQ] = useState(localStorage.getItem('news_q') || '')
  const [newsCategory, setNewsCategory] = useState(localStorage.getItem('news_category') || '')
  const [newsSource, setNewsSource] = useState(localStorage.getItem('news_source') || '')
  const [newsDays, setNewsDays] = useState(Number(localStorage.getItem('news_days') || 30))
  const [newsSort, setNewsSort] = useState('latest')
  const [expandedNews, setExpandedNews] = useState({})
  const [newsDetail, setNewsDetail] = useState(null)
  const [q, setQ] = useState(localStorage.getItem('dash_q') || '')
  const [status, setStatus] = useState(localStorage.getItem('dash_status') || '')
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState(null)
  const [runs, setRuns] = useState([])
  const [raw, setRaw] = useState('')
  const [tab, setTab] = useState('info')
  const [error, setError] = useState('')
  const [isMobile, setIsMobile] = useState(window.innerWidth < 1100)

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

  const loadNews = async () => {
    try {
      setError('')
      const qs = new URLSearchParams({ limit: '50', days: String(newsDays) })
      if (newsCategory) qs.set('category', newsCategory)
      if (newsSource) qs.set('source', newsSource)
      if (newsQ) qs.set('q', newsQ)
      const [n, c] = await Promise.all([
        apiGet(`/api/news?${qs.toString()}`),
        apiGet('/api/news/categories')
      ])
      setNews(n.items || [])
      setNewsCategories(c.items || [])
    } catch (e) {
      setError('뉴스 조회 오류: ' + e.message)
    }
  }

  const loadStockNews = async () => {
    try {
      setError('')
      const s = await apiGet(`/api/news/stocks?limit=50&days=${newsDays}`)
      setStockNews(s.items || [])
    } catch (e) {
      setError('주식 뉴스 조회 오류: ' + e.message)
    }
  }

  const loadNewsDetail = async (id) => {
    try {
      const d = await apiGet(`/api/news/item/${id}`)
      setNewsDetail(d)
    } catch (e) {
      setError('뉴스 상세 조회 오류: ' + e.message)
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
    menu === 'dashboard' ? loadSummaryAndJobs() : loadNews()
  }

  const saveNewsFilters = () => {
    localStorage.setItem('news_q', newsQ)
    localStorage.setItem('news_category', newsCategory)
    localStorage.setItem('news_source', newsSource)
    localStorage.setItem('news_days', String(newsDays))
  }

  const resetNewsFilters = () => {
    setNewsQ('')
    setNewsCategory('')
    setNewsSource('')
    setNewsDays(30)
    localStorage.removeItem('news_q')
    localStorage.removeItem('news_category')
    localStorage.removeItem('news_source')
    localStorage.removeItem('news_days')
  }

  const clearAuth = () => {
    setAuthUser('')
    setAuthPass('')
    localStorage.removeItem('cron_auth_user')
    localStorage.removeItem('cron_auth_pass')
  }

  useEffect(() => { loadSummaryAndJobs() }, [])
  useEffect(() => { if (selectedId) loadDetail(selectedId) }, [selectedId])
  useEffect(() => {
    if (menu === 'dashboard') loadSummaryAndJobs()
    if (menu === 'news') loadNews()
    if (menu === 'stocks') loadStockNews()
  }, [menu])
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 1100)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    localStorage.setItem('news_q', newsQ)
    localStorage.setItem('news_category', newsCategory)
    localStorage.setItem('news_source', newsSource)
    localStorage.setItem('news_days', String(newsDays))
  }, [newsQ, newsCategory, newsSource, newsDays])

  useEffect(() => {
    localStorage.setItem('dash_q', q)
    localStorage.setItem('dash_status', status)
  }, [q, status])

  useEffect(() => {
    const timer = setInterval(() => {
      if (menu === 'dashboard') loadSummaryAndJobs()
      if (menu === 'news') loadNews()
      if (menu === 'stocks') loadStockNews()
    }, 300000)
    return () => clearInterval(timer)
  }, [menu, newsQ, newsCategory, newsSource, newsDays])

  const filtered = useMemo(() => jobs.filter((j) => {
    const hit = !q || j.name.toLowerCase().includes(q.toLowerCase()) || j.id.toLowerCase().includes(q.toLowerCase())
    const st = !status || String(j.status).toLowerCase() === status
    return hit && st
  }), [jobs, q, status])

  const statusCount = useMemo(() => {
    const out = { all: jobs.length, ok: 0, idle: 0, error: 0 }
    jobs.forEach((j) => {
      const s = String(j.status || '').toLowerCase()
      if (s === 'ok') out.ok += 1
      else if (s === 'idle') out.idle += 1
      else if (s === 'error') out.error += 1
    })
    return out
  }, [jobs])

  const renderDashboard = () => (
    <>
      <h1 style={{ marginTop: 0, marginBottom: 6, letterSpacing: '-0.01em' }}>대시보드</h1>
      <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>Cron 상태를 목록/상세로 확인하고 실행 이력을 추적합니다.</div>
      <SummaryCards summary={summary} isMobile={isMobile} />

      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder='이름/ID 검색' style={{ ...box, flex: 1, color: '#e5e7eb' }} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ ...box, color: '#e5e7eb' }}>
          <option value=''>전체 상태</option><option value='ok'>ok</option><option value='idle'>idle</option><option value='error'>error</option>
        </select>
        <button onClick={loadSummaryAndJobs} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>새로고침</button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12, color: '#cbd5e1', fontSize: 12 }}>
        <span style={{ ...box, padding: '4px 10px' }}>ALL {statusCount.all}</span>
        <span style={{ ...box, padding: '4px 10px', color: '#22c55e' }}>OK {statusCount.ok}</span>
        <span style={{ ...box, padding: '4px 10px', color: '#f59e0b' }}>IDLE {statusCount.idle}</span>
        <span style={{ ...box, padding: '4px 10px', color: '#ef4444' }}>ERROR {statusCount.error}</span>
        <span style={{ ...box, padding: '4px 10px' }}>FILTERED {filtered.length}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(620px,1.1fr) minmax(420px,.9fr)', gap: 12 }}>
        <div style={box}><JobsTable jobs={filtered} selectedId={selectedId} onSelect={setSelectedId} /></div>
        <div style={box}><DetailPanel tab={tab} setTab={setTab} detail={detail} runs={runs} raw={raw} /></div>
      </div>
    </>
  )

  const renderStocks = () => (
    <>
      <h1 style={{ marginTop: 0, marginBottom: 6 }}>주식</h1>
      <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>뉴스 중 주식/증시 관련 항목만 분리한 메뉴입니다.</div>
      <div style={{ marginBottom: 12 }}>
        <button onClick={loadStockNews} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>주식 뉴스 새로고침</button>
      </div>
      <div style={box}>
        {stockNews.length === 0 ? <div style={{ color: '#94a3b8' }}>주식 관련 뉴스가 없습니다.</div> : stockNews.map((n) => (
          <div key={n.id} style={{ borderTop: '1px solid #263142', padding: '10px 0' }}>
            <div style={{ fontWeight: 700 }}>{n.title}</div>
            <div style={{ color: '#94a3b8', fontSize: 12 }}>{n.source || '-'} · {n.category || '-'} · {n.publishedAtMs ? new Date(n.publishedAtMs).toLocaleString('ko-KR') : '-'}</div>
            <div style={{ marginTop: 4, fontSize: 13, whiteSpace: 'pre-wrap' }}>{(n.summary || '-').slice(0, 320)}{(n.summary||'').length>320?' ...':''}</div>
            <div style={{ marginTop: 6, display: 'flex', gap: 10 }}>
              <button onClick={() => loadNewsDetail(n.id)} style={{ ...box, padding: '4px 8px', cursor: 'pointer', color: '#7dd3fc', fontSize: 12 }}>상세 보기</button>
              {n.url && <a href={n.url} target='_blank' rel='noreferrer' style={{ color: '#7dd3fc', fontSize: 12 }}>원문 보기</a>}
            </div>
          </div>
        ))}
      </div>
    </>
  )

  const renderNews = () => {
    const sorted = [...news].sort((a, b) => {
      const ta = a.publishedAtMs || a.createdAtMs || 0
      const tb = b.publishedAtMs || b.createdAtMs || 0
      return newsSort === 'latest' ? tb - ta : ta - tb
    })

    const sourceCount = sorted.reduce((acc, n) => {
      const s = n.source || 'unknown'
      acc[s] = (acc[s] || 0) + 1
      return acc
    }, {})

    const uniqueSources = Object.keys(sourceCount).length
    const latestTs = sorted[0]?.publishedAtMs || sorted[0]?.createdAtMs || null
    const oldestTs = sorted[sorted.length - 1]?.publishedAtMs || sorted[sorted.length - 1]?.createdAtMs || null

    return (
      <>
        <h1 style={{ marginTop: 0, marginBottom: 6 }}>뉴스</h1>
        <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 10 }}>정보성 뉴스/브리핑 기록을 확인합니다.</div>
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 180px 140px 120px auto auto auto', gap: 8, marginBottom: 12 }}>
          <input value={newsQ} onChange={(e) => setNewsQ(e.target.value)} placeholder='뉴스 검색어' style={{ ...box, color: '#e5e7eb' }} />
          <input value={newsCategory} onChange={(e) => setNewsCategory(e.target.value)} placeholder='카테고리(예: cron-news)' style={{ ...box, color: '#e5e7eb' }} />
          <select value={newsDays} onChange={(e) => setNewsDays(Number(e.target.value))} style={{ ...box, color: '#e5e7eb' }}>
            <option value={7}>최근 7일</option>
            <option value={30}>최근 30일</option>
            <option value={90}>최근 90일</option>
          </select>
          <select value={newsSort} onChange={(e) => setNewsSort(e.target.value)} style={{ ...box, color: '#e5e7eb' }}>
            <option value='latest'>최신순</option>
            <option value='oldest'>오래된순</option>
          </select>
          <button onClick={loadNews} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>뉴스 새로고침</button>
          <button onClick={saveNewsFilters} style={{ ...box, cursor: 'pointer', color: '#7dd3fc' }}>필터 저장</button>
          <button onClick={resetNewsFilters} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>필터 초기화</button>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <span style={{ ...box, padding: '4px 8px', fontSize: 12 }}>총 {sorted.length}건</span>
          <span style={{ ...box, padding: '4px 8px', fontSize: 12 }}>소스 {uniqueSources}개</span>
          <span style={{ ...box, padding: '4px 8px', fontSize: 12 }}>최신 {latestTs ? new Date(latestTs).toLocaleDateString('ko-KR') : '-'}</span>
          <span style={{ ...box, padding: '4px 8px', fontSize: 12 }}>최초 {oldestTs ? new Date(oldestTs).toLocaleDateString('ko-KR') : '-'}</span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          {newsCategories.slice(0, 8).map((c) => (
            <button key={c.category} onClick={() => setNewsCategory(c.category)} style={{ ...box, padding: '4px 8px', fontSize: 12, color: newsCategory===c.category ? '#7dd3fc' : '#cbd5e1', cursor: 'pointer' }}>
              {c.category} {c.count}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          {Object.entries(sourceCount).slice(0, 8).map(([s, c]) => (
            <button key={s} onClick={() => setNewsSource(s)} style={{ ...box, padding: '4px 8px', fontSize: 12, color: newsSource===s ? '#7dd3fc':'#cbd5e1', cursor:'pointer' }}>{s} {c}</button>
          ))}
        </div>
        <div style={box}>
          {sorted.length === 0 ? <div style={{ color: '#94a3b8' }}>조건에 맞는 뉴스가 없습니다.</div> : sorted.map((n) => {
            const expanded = !!expandedNews[n.id]
            const body = n.summary || '-'
            const shortBody = body.length > 240 && !expanded ? body.slice(0, 240) + ' ...' : body
            return (
              <div key={n.id} style={{ borderTop: '1px solid #263142', padding: '10px 0' }}>
                <div style={{ fontWeight: 700 }}>{n.title}</div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>{n.source || '-'} · {n.category || '-'} · {n.publishedAtMs ? new Date(n.publishedAtMs).toLocaleString('ko-KR') : '-'}</div>
                <div style={{ marginTop: 4, fontSize: 13, whiteSpace: 'pre-wrap' }}>{shortBody}</div>
                <div style={{ marginTop: 6, display: 'flex', gap: 10, alignItems: 'center' }}>
                  {body.length > 240 && (
                    <button
                      onClick={() => setExpandedNews((p) => ({ ...p, [n.id]: !p[n.id] }))}
                      style={{ ...box, padding: '4px 8px', cursor: 'pointer', color: '#e5e7eb', fontSize: 12 }}
                    >
                      {expanded ? '요약 접기' : '요약 펼치기'}
                    </button>
                  )}
                  <button onClick={() => loadNewsDetail(n.id)} style={{ ...box, padding: '4px 8px', cursor: 'pointer', color: '#7dd3fc', fontSize: 12 }}>상세 보기</button>
                  <button
                    onClick={() => navigator.clipboard?.writeText(`${n.title}\n\n${body}`)}
                    style={{ ...box, padding: '4px 8px', cursor: 'pointer', color: '#e5e7eb', fontSize: 12 }}
                  >
                    요약 복사
                  </button>
                  {n.url && <a href={n.url} target='_blank' rel='noreferrer' style={{ color: '#7dd3fc', fontSize: 12 }}>원문 보기</a>}
                </div>
              </div>
            )
          })}
        </div>
      </>
    )
  }

  return (
    <div style={{ fontFamily: 'Inter,system-ui,sans-serif', background: '#0f172a', minHeight: '100vh', color: '#e5e7eb', display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '220px 1fr' }}>
      {!isMobile && <aside style={{ borderRight: '1px solid #1f2937', padding: 16, background: '#0b1220', position:'sticky', top:0, height:'100vh' }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Dashboard</div>
        <div onClick={() => setMenu('dashboard')} style={{ ...box, marginBottom:8, cursor:'pointer', background: menu==='dashboard' ? '#0b2536':'#111827', borderColor: menu==='dashboard' ? '#1f4b63':'#334155', color: menu==='dashboard' ? '#7dd3fc':'#e5e7eb', display:'flex', justifyContent:'space-between' }}><span>대시보드</span><span style={{fontSize:12, color:'#94a3b8'}}>{jobs.length}</span></div>
        <div onClick={() => { setMenu('news'); loadNews() }} style={{ ...box, marginBottom:8, cursor:'pointer', background: menu==='news' ? '#0b2536':'#111827', borderColor: menu==='news' ? '#1f4b63':'#334155', color: menu==='news' ? '#7dd3fc':'#e5e7eb', display:'flex', justifyContent:'space-between' }}><span>뉴스</span><span style={{fontSize:12, color:'#94a3b8'}}>{news.length}</span></div>
        <div onClick={() => { setMenu('stocks'); loadStockNews() }} style={{ ...box, cursor:'pointer', background: menu==='stocks' ? '#0b2536':'#111827', borderColor: menu==='stocks' ? '#1f4b63':'#334155', color: menu==='stocks' ? '#7dd3fc':'#e5e7eb', display:'flex', justifyContent:'space-between' }}><span>주식</span><span style={{fontSize:12, color:'#94a3b8'}}>{stockNews.length}</span></div>
      </aside>}

      <main style={{ padding: 20, maxWidth: 1600 }}>
        {newsDetail && (
          <div style={{ ...box, marginBottom: 10, borderColor:'#1f4b63' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
              <strong>뉴스 상세</strong>
              <button onClick={() => setNewsDetail(null)} style={{ ...box, padding:'4px 8px', cursor:'pointer', color:'#e5e7eb' }}>닫기</button>
            </div>
            <div style={{ fontWeight:700 }}>{newsDetail.title}</div>
            <div style={{ color:'#94a3b8', fontSize:12 }}>{newsDetail.source || '-'} · {newsDetail.category || '-'} · {newsDetail.publishedAtMs ? new Date(newsDetail.publishedAtMs).toLocaleString('ko-KR') : '-'}</div>
            <pre style={{ ...box, marginTop:8, whiteSpace:'pre-wrap', maxHeight:260, overflow:'auto' }}>{newsDetail.summary || '-'}</pre>
            {newsDetail.url && <a href={newsDetail.url} target='_blank' rel='noreferrer' style={{ color:'#7dd3fc', fontSize:12 }}>원문 보기</a>}
          </div>
        )}
        {isMobile && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <button onClick={() => setMenu('dashboard')} style={{ ...box, cursor: 'pointer', color: menu==='dashboard' ? '#7dd3fc' : '#e5e7eb', background: menu==='dashboard' ? '#0b2536' : '#111827' }}>대시보드</button>
            <button onClick={() => { setMenu('news'); loadNews() }} style={{ ...box, cursor: 'pointer', color: menu==='news' ? '#7dd3fc' : '#e5e7eb', background: menu==='news' ? '#0b2536' : '#111827' }}>뉴스</button>
            <button onClick={() => { setMenu('stocks'); loadStockNews() }} style={{ ...box, cursor: 'pointer', color: menu==='stocks' ? '#7dd3fc' : '#e5e7eb', background: menu==='stocks' ? '#0b2536' : '#111827' }}>주식</button>
          </div>
        )}
        {error && <div style={{ ...box, borderColor: '#7f1d1d', color: '#fca5a5', marginBottom: 10 }}>{error}</div>}

        <div style={{ ...box, marginBottom: 12, display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr auto auto auto', gap: 8 }}>
          <input value={authUser} onChange={(e) => setAuthUser(e.target.value)} placeholder='API 계정' style={{ ...box, color: '#e5e7eb' }} />
          <input value={authPass} onChange={(e) => setAuthPass(e.target.value)} placeholder='API 비밀번호' type='password' style={{ ...box, color: '#e5e7eb' }} />
          <button onClick={saveAuth} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>인증 저장/적용</button>
          <button onClick={clearAuth} style={{ ...box, cursor: 'pointer', color: '#e5e7eb' }}>인증 초기화</button>
          <div style={{ ...box, padding: '8px 10px', color: authUser && authPass ? '#22c55e' : '#f59e0b', fontWeight: 700 }}>{authUser && authPass ? '인증 상태: 적용됨' : '인증 상태: 미설정'}</div>
        </div>

        {menu === 'dashboard' ? renderDashboard() : menu === 'news' ? renderNews() : renderStocks()}
      </main>
    </div>
  )
}
