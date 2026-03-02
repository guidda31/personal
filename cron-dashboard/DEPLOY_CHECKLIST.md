# 대시보드 배포 체크리스트

## 1) 서비스 기동
- [ ] `start_all.sh` 실행
- [ ] Frontend(5173) LISTEN 확인
- [ ] Backend(8000) LISTEN 확인
- [ ] `healthcheck.sh` 모두 OK

## 2) 데이터 파이프라인
- [ ] `backend/collector.py` 수동 실행 성공
- [ ] `cron-dashboard-collector` 크론 등록 확인
- [ ] `cron_job_sync_log` 최근 상태 `ok` 확인

## 3) 인증
- [ ] `enable_auth.sh <user> <pass>` 적용(운영)
- [ ] 무인증 401 확인
- [ ] 인증 200 확인 (`e2e_auth_check.sh`)
- [ ] Frontend 인증 상태 배지 확인

## 4) 기능 검증
- [ ] 목록 조회/검색/상태필터 정상
- [ ] 상세 탭(기본정보/실행이력/Raw JSON) 정상
- [ ] KPI 카드 수치 정상
- [ ] 모바일(<=1100px) 레이아웃 정상

## 5) 운영
- [ ] `@reboot #cron-dashboard-febe-autostart` 등록 확인
- [ ] 로그 파일 경로 확인 (`tmp/cron_dashboard_*.log`)
- [ ] 장애 시 `stop_all.sh -> start_all.sh` 복구 절차 확인
