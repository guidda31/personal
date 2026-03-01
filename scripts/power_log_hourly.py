#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import csv
import subprocess
import re

SCRIPT = '/home/guidda/.openclaw/workspace/scripts/power_estimate_wsl.py'
LOG = Path('/home/guidda/.openclaw/workspace/tmp/power_hourly.csv')
LOG.parent.mkdir(parents=True, exist_ok=True)

out = subprocess.check_output(['python3', SCRIPT], text=True)

m = re.search(r'추정 시스템 전력: ([0-9.]+)W ~ ([0-9.]+)W', out)
g = re.search(r'GPU 전력\(nvidia-smi\): ([0-9.]+)W', out)
if not m:
    raise SystemExit('power parse failed')
low, high = float(m.group(1)), float(m.group(2))
gpu = float(g.group(1)) if g else ''
ts = datetime.now().strftime('%Y-%m-%d %H:00:00')

new = not LOG.exists()
with LOG.open('a', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    if new:
        w.writerow(['ts','power_low_w','power_high_w','gpu_w'])
    w.writerow([ts, f'{low:.2f}', f'{high:.2f}', gpu])
