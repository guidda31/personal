#!/usr/bin/env python3
import math
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from urllib.request import Request, urlopen

UA = "Mozilla/5.0"


@dataclass
class DailyBar:
    date: str
    close: float
    open: float
    high: float
    low: float
    volume: float


def fetch_text(url: str, encoding: str = "utf-8") -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=12) as r:
        data = r.read()
    return data.decode(encoding, "ignore")


def get_usdkrw() -> tuple[float | None, str | None]:
    html = fetch_text("https://finance.naver.com/marketindex/", encoding="euc-kr")
    m = re.search(r'미국 USD.*?value">([^<]+)<.*?change">([^<]+)<', html, re.S)
    if not m:
        return None, None
    price = float(m.group(1).replace(",", "").strip())
    chg = m.group(2).strip()
    return price, chg


def get_top_volume(market: str, count: int) -> list[dict]:
    sosok = "0" if market == "KOSPI" else "1"
    html = fetch_text(f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}", encoding="euc-kr")
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        if 'class="tltle"' not in tr:
            continue
        m_name = re.search(r'<a href="/item/main\.naver\?code=(\d+)" class="tltle">([^<]+)</a>', tr)
        if not m_name:
            continue
        code, name = m_name.group(1), unescape(m_name.group(2)).strip()

        m_price = re.search(r'<td class="number">\s*([0-9,]+)\s*</td>', tr)
        plain_nums = re.findall(r'<td class="number">\s*([0-9,]+|N/A)\s*</td>', tr)
        if not m_price or len(plain_nums) < 2:
            continue
        try:
            price = int(m_price.group(1).replace(",", ""))
            volume = int(plain_nums[1].replace(",", ""))
        except Exception:
            continue

        rows.append({"name": name, "code": code, "market": market, "price": price, "volume": volume})
    rows.sort(key=lambda x: x["volume"], reverse=True)
    return rows[:count]


def get_daily_bars(code: str, pages: int = 8) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for p in range(1, pages + 1):
        html = fetch_text(f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}", encoding="euc-kr")
        row_pat = re.compile(
            r'<td align="center"><span class="tah p10 gray03">(\d{4}\.\d{2}\.\d{2})</span></td>\s*'
            r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>\s*'
            r'<td class="num">.*?</td>\s*'
            r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>\s*'
            r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>\s*'
            r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>\s*'
            r'<td class="num"><span class="tah p11">([0-9,]+)</span></td>',
            re.S,
        )
        for m in row_pat.finditer(html):
            d, c, o, h, l, v = m.groups()
            bars.append(
                DailyBar(
                    date=d,
                    close=float(c.replace(",", "")),
                    open=float(o.replace(",", "")),
                    high=float(h.replace(",", "")),
                    low=float(l.replace(",", "")),
                    volume=float(v.replace(",", "")),
                )
            )
    # naver returns latest first; ensure unique date and keep order latest->old
    seen = set()
    uniq = []
    for b in bars:
        if b.date in seen:
            continue
        seen.add(b.date)
        uniq.append(b)
    return uniq


def sma(values: list[float], n: int) -> float:
    if len(values) < n:
        return sum(values) / max(1, len(values))
    return sum(values[:n]) / n


def rsi_14(closes_latest_first: list[float]) -> float:
    if len(closes_latest_first) < 15:
        return 50.0
    # use oldest->newest diffs
    closes = list(reversed(closes_latest_first[:15]))
    gains = []
    losses = []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr_14(bars_latest_first: list[DailyBar]) -> float:
    if len(bars_latest_first) < 15:
        return max(1.0, bars_latest_first[0].close * 0.02)
    bars = bars_latest_first[:15]
    trs = []
    for i in range(14):
        cur = bars[i]
        prev_close = bars[i + 1].close
        tr = max(cur.high - cur.low, abs(cur.high - prev_close), abs(cur.low - prev_close))
        trs.append(tr)
    return sum(trs) / len(trs)


def percent(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def probability_score(bars_latest_first: list[DailyBar], usdkrw: float | None = None, usdkrw_chg_text: str | None = None) -> tuple[float, dict]:
    closes = [b.close for b in bars_latest_first]
    vols = [b.volume for b in bars_latest_first]
    cur = closes[0]

    mom_3 = percent(cur, closes[3]) if len(closes) > 3 else 0.0
    mom_5 = percent(cur, closes[5]) if len(closes) > 5 else 0.0
    mom_20 = percent(cur, closes[20]) if len(closes) > 20 else 0.0
    rsi = rsi_14(closes)
    vol_ratio = (vols[0] / (sum(vols[1:6]) / 5)) if len(vols) > 6 and sum(vols[1:6]) > 0 else 1.0

    # FX penalty for KRW weakness shock days
    fx_penalty = 0.0
    if usdkrw_chg_text:
        m = re.search(r'([+-]?[0-9]+\.?[0-9]*)', usdkrw_chg_text.replace(',', ''))
        if m:
            try:
                fx_delta = float(m.group(1))
                if fx_delta > 8:
                    fx_penalty = 0.25
            except Exception:
                pass

    # Heuristic logit model (interpretable, not overfit)
    z = (
        0.10 * mom_3
        + 0.08 * mom_5
        + 0.04 * mom_20
        + 0.35 * math.log(max(vol_ratio, 0.2))
        + (0.15 if 45 <= rsi <= 62 else (-0.12 if rsi > 75 else 0.0))
        - fx_penalty
    )

    prob = sigmoid(z) * 100
    details = {
        "mom_3": round(mom_3, 2),
        "mom_5": round(mom_5, 2),
        "mom_20": round(mom_20, 2),
        "rsi14": round(rsi, 2),
        "vol_ratio": round(vol_ratio, 2),
        "fx_penalty": fx_penalty,
    }
    return round(prob, 2), details


def target_stop_from_atr(cur: float, atr: float, style: str = "neutral") -> tuple[int, int]:
    style = style.lower()
    if style == "aggressive":
        t_mult, s_mult = 2.2, 1.4
    elif style == "conservative":
        t_mult, s_mult = 1.2, 0.9
    else:  # neutral
        t_mult, s_mult = 1.7, 1.1
    target = int(round(cur + atr * t_mult))
    stop = int(round(max(1, cur - atr * s_mult)))
    return target, stop


def scenario_label(prob: float, rsi: float, vol_ratio: float) -> str:
    if prob >= 66 and vol_ratio >= 1.2 and rsi < 72:
        return "상승 모멘텀 우세"
    if prob >= 55:
        return "중립~상승 시도"
    if prob >= 45:
        return "박스권/혼조 가능"
    return "변동성 주의(보수 접근)"


def now_kst() -> str:
    return datetime.now().strftime("%Y-%m-%d(%a) %H:%M KST")
