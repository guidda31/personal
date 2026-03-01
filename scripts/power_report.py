#!/usr/bin/env python3
from datetime import datetime, date
from pathlib import Path
import csv
from collections import defaultdict

LOG = Path('/home/guidda/.openclaw/workspace/tmp/power_hourly.csv')
RATE = 190.0  # KRW/kWh simple blended estimate

if not LOG.exists():
    print('아직 누적 데이터가 없어. (power_hourly.csv 없음)')
    raise SystemExit(0)

rows = []
with LOG.open(encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        d = datetime.strptime(row['ts'], '%Y-%m-%d %H:%M:%S')
        low = float(row['power_low_w'])
        high = float(row['power_high_w'])
        rows.append((d, low, high))

by_day = defaultdict(lambda: [0.0,0.0,0])
for d,low,high in rows:
    k = d.date().isoformat()
    # each sample ~= 1 hour average
    by_day[k][0] += low/1000.0
    by_day[k][1] += high/1000.0
    by_day[k][2] += 1

print('일별 사용량/요금 (시간당 누적 기준)')
for k in sorted(by_day):
    low_kwh, high_kwh, n = by_day[k]
    print(f'- {k}: {low_kwh:.3f}~{high_kwh:.3f} kWh / {low_kwh*RATE:,.0f}~{high_kwh*RATE:,.0f}원 (샘플 {n}h)')

# billing cycle rule: N월 17일 ~ N+1월 16일 => (N+1)월 요금

def add_month(y: int, m: int, delta: int):
    m2 = m + delta
    y2 = y + (m2 - 1) // 12
    m2 = (m2 - 1) % 12 + 1
    return y2, m2


today = date.today()
if today.day >= 17:
    start_y, start_m = today.year, today.month
else:
    start_y, start_m = add_month(today.year, today.month, -1)

end_y, end_m = add_month(start_y, start_m, 1)
start = date(start_y, start_m, 17)
end = date(end_y, end_m, 16)
bill_month_label = f"{end_y}-{end_m:02d}"  # 예: 2026-03 (3월 요금)

sum_low = sum(v[0] for k,v in by_day.items() if start <= date.fromisoformat(k) <= end)
sum_high = sum(v[1] for k,v in by_day.items() if start <= date.fromisoformat(k) <= end)
print(f"\n월 정산 구간({start.isoformat()}~{end.isoformat()}) 누적 / {bill_month_label} 요금")
print(f'- 사용량: {sum_low:.3f}~{sum_high:.3f} kWh')
print(f'- 요금(추정): {sum_low*RATE:,.0f}~{sum_high*RATE:,.0f}원 (단가 {RATE:.0f}원/kWh 가정)')
