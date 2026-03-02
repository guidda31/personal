# 대시보드 (cron-dashboard)

## 아키텍처
- Frontend: React + Vite (`frontend/`)
- Backend: FastAPI (`backend/`)
- DB: MariaDB (`internal_db`)

## 접속
- 로컬 Frontend: http://127.0.0.1:5173
- 로컬 Backend API: http://127.0.0.1:8000
- 외부(본인 Tailnet 기기): `http://<TAILNET_IP>:5173`
  - 현재 예시: `http://100.75.32.60:5173`
  - 원칙: `ts.net` 대신 Tailnet IP 고정 사용

## 주요 기능
- LNB 메뉴 분리:
  - **대시보드**(크론 운영 모니터링)
  - **뉴스**(정보성 브리핑/요약 아카이브)
- 대시보드:
  - 크론 목록 조회/검색/상태필터
  - 상세 탭: 기본정보 / 실행이력 / Raw JSON
  - KPI 카드: TOTAL / ENABLED / OK / IDLE / ERROR / RUNS24H
- 뉴스:
  - 필터(검색어/카테고리/기간/소스)
  - 정렬(최신순/오래된순)
  - 요약 펼침/접기, 요약 복사, 상세 보기

## 실행
```bash
/home/guidda/.openclaw/workspace/cron-dashboard/start_all.sh
/home/guidda/.openclaw/workspace/cron-dashboard/stop_all.sh
/home/guidda/.openclaw/workspace/cron-dashboard/healthcheck.sh
/home/guidda/.openclaw/workspace/cron-dashboard/tailnet_access_check.sh
```

## API (FastAPI)
### Dashboard
- `GET /api/cron/summary`
- `GET /api/cron/jobs`
- `GET /api/cron/jobs/{id}`
- `GET /api/cron/jobs/{id}/runs?limit=20`
- `GET /api/cron/jobs/{id}/raw`

### News
- `GET /api/news`
  - query: `limit`, `days`, `category`, `source`, `q`
- `GET /api/news/categories`
- `GET /api/news/{id}`

## 인증
### Backend Basic Auth (옵션)
- `CRON_DASHBOARD_AUTH_USER`
- `CRON_DASHBOARD_AUTH_PASS`

### Frontend 인증 UX
- 상단 인증 입력 + 저장/초기화 제공

## 환경 예시 파일
- `backend/.env.example`
- `frontend/.env.example`

## 데이터 수집
- Dashboard 수집기: `backend/collector.py`
  - 크론(1분): `#cron-dashboard-collector`
- News 적재기: `backend/news_ingest_from_runs.py`
  - 크론(5분): `#cron-dashboard-news-ingest`
- 수동 실행:
```bash
python3 /home/guidda/.openclaw/workspace/cron-dashboard/backend/collector.py
python3 /home/guidda/.openclaw/workspace/cron-dashboard/backend/news_ingest_from_runs.py
```

## 레거시 정리
- 기존 Node 단일 서버 파일은 `_legacy_cron_dashboard_server.js`로 이동
- 구 autostart 크론 제거 완료
- Node collector는 Python collector로 이관 완료
