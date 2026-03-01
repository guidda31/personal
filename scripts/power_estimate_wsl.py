#!/usr/bin/env python3
"""
WSL power estimate report (heuristic, not hardware-accurate).
- Uses CPU usage + loadavg + optional nvidia-smi info
- Prints estimated system power range
"""

from __future__ import annotations
import os
import shutil
import subprocess
import time


def read_cpu_times():
    with open('/proc/stat', 'r', encoding='utf-8') as f:
        line = f.readline().strip().split()
    vals = list(map(int, line[1:]))
    idle = vals[3] + vals[4] if len(vals) > 4 else vals[3]
    total = sum(vals)
    return idle, total


def cpu_percent(interval=0.5):
    i1, t1 = read_cpu_times()
    time.sleep(interval)
    i2, t2 = read_cpu_times()
    didle = i2 - i1
    dtotal = t2 - t1
    if dtotal <= 0:
        return 0.0
    return max(0.0, min(100.0, (1 - didle / dtotal) * 100))


def get_gpu_power_watts():
    if not shutil.which('nvidia-smi'):
        return None
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=power.draw', '--format=csv,noheader,nounits'],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip().splitlines()
        vals = [float(x.strip()) for x in out if x.strip()]
        return sum(vals) if vals else None
    except Exception:
        return None


def estimate_cpu_power(cpu_pct: float, cores: int) -> tuple[float, float]:
    # Heuristic for laptop/desktop mixed environments:
    # idle ~ 8-20W total platform baseline, CPU dynamic scaled by load+cores
    base_low, base_high = 8.0, 20.0
    dyn_low = (cpu_pct / 100.0) * max(8.0, cores * 3.0)
    dyn_high = (cpu_pct / 100.0) * max(20.0, cores * 8.0)
    return base_low + dyn_low, base_high + dyn_high


def main():
    cpu = cpu_percent(0.7)
    cores = os.cpu_count() or 4
    la1, la5, la15 = os.getloadavg()

    cpu_low, cpu_high = estimate_cpu_power(cpu, cores)
    gpu_w = get_gpu_power_watts()

    total_low, total_high = cpu_low, cpu_high
    if gpu_w is not None:
        total_low += gpu_w * 0.9
        total_high += gpu_w * 1.1

    print('WSL 추정 전력 리포트 (대략치)')
    print(f'- CPU 사용률: {cpu:.1f}%')
    print(f'- 코어 수: {cores}')
    print(f'- LoadAvg: {la1:.2f} / {la5:.2f} / {la15:.2f}')
    if gpu_w is not None:
        print(f'- GPU 전력(nvidia-smi): {gpu_w:.1f}W')
    else:
        print('- GPU 전력: 측정 불가(nvidia-smi 미탐지)')
    print(f'- 추정 시스템 전력: {total_low:.1f}W ~ {total_high:.1f}W')
    print('※ 실제 센서값이 아닌 추정치입니다.')


if __name__ == '__main__':
    main()
