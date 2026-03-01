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


def classify_theme(name: str) -> str:
    n = name.upper()
    themes = {
        "defense": ["한화", "LIG", "현대로템", "풍산", "방산"],
        "energy": ["S-OIL", "SK이노", "GS", "정유", "가스", "에너지"],
        "semiconductor": ["삼성전자", "SK하이닉스", "한미반도체", "반도체"],
        "bio": ["바이오", "셀트리온", "삼성바이오", "젠큐릭스"],
        "finance": ["금융", "은행", "증권", "우리금융", "KB", "신한", "하나"],
        "construction": ["건설", "대우건설", "현대건설", "GS건설"],
    }
    for k, kws in themes.items():
        if any(kw.upper() in n for kw in kws):
            return k
    return "general"


def theme_factor(theme: str, fx_delta: float | None) -> float:
    # Risk-off day heuristic: weak KRW favors defense/energy, penalizes high-beta growth.
    if fx_delta is None:
        return 0.0
    if fx_delta > 8:
        if theme in {"defense", "energy"}:
            return 0.12
        if theme in {"bio"}:
            return -0.08
    return 0.0


def probability_score(
    bars_latest_first: list[DailyBar],
    name: str = "",
    usdkrw: float | None = None,
    usdkrw_chg_text: str | None = None,
) -> tuple[float, dict]:
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
    fx_delta = None
    if usdkrw_chg_text:
        m = re.search(r'([+-]?[0-9]+\.?[0-9]*)', usdkrw_chg_text.replace(',', ''))
        if m:
            try:
                fx_delta = float(m.group(1))
                if fx_delta > 8:
                    fx_penalty = 0.25
            except Exception:
                pass

    th = classify_theme(name)
    th_adj = theme_factor(th, fx_delta)

    overheat_penalty = 0.0
    if rsi > 82:
        overheat_penalty += 0.20
    if mom_5 > 35:
        overheat_penalty += 0.20

    # Heuristic logit model (interpretable, not overfit)
    z = (
        0.06 * mom_3
        + 0.05 * mom_5
        + 0.025 * mom_20
        + 0.22 * math.log(max(vol_ratio, 0.2))
        + (0.10 if 42 <= rsi <= 64 else (-0.22 if rsi > 78 else 0.0))
        - fx_penalty
        - overheat_penalty
        + th_adj
    )

    # Calibration: soften confidence and avoid 99% saturation.
    raw_prob = sigmoid(z / 4.8) * 100
    prob = min(82.0, max(18.0, raw_prob))
    details = {
        "mom_3": round(mom_3, 2),
        "mom_5": round(mom_5, 2),
        "mom_20": round(mom_20, 2),
        "rsi14": round(rsi, 2),
        "vol_ratio": round(vol_ratio, 2),
        "fx_penalty": fx_penalty,
        "theme": th,
        "theme_adj": round(th_adj, 3),
        "overheat_penalty": round(overheat_penalty, 3),
    }
    return round(prob, 2), details


def target_stop_from_atr(cur: float, atr: float, style: str = "neutral") -> tuple[int, int, str]:
    style = style.lower()

    # Volatility regime by ATR ratio
    atr_ratio = atr / max(cur, 1)
    if atr_ratio >= 0.08:
        regime = "high"
    elif atr_ratio >= 0.04:
        regime = "mid"
    else:
        regime = "low"

    if style == "aggressive":
        base_t, base_s = 2.2, 1.4
    elif style == "conservative":
        base_t, base_s = 1.2, 0.9
    else:  # neutral
        base_t, base_s = 1.7, 1.1

    # Dynamic adjustment by regime
    if regime == "high":
        t_mult = base_t * 1.25
        s_mult = base_s * 1.20
    elif regime == "mid":
        t_mult = base_t * 1.0
        s_mult = base_s * 1.0
    else:  # low
        t_mult = base_t * 0.85
        s_mult = base_s * 0.80

    target = int(round(cur + atr * t_mult))
    stop = int(round(max(1, cur - atr * s_mult)))

    # KRX daily price limit guard (day-trading realism): +/-30%
    max_target = int(round(cur * 1.30))
    min_stop = int(round(cur * 0.70))
    target = min(target, max_target)
    stop = max(stop, min_stop)

    return target, stop, regime


def scenario_label(prob: float, rsi: float, vol_ratio: float, regime: str, theme: str) -> str:
    base = ""
    if prob >= 66 and vol_ratio >= 1.2 and rsi < 72:
        base = "상승 모멘텀 우세"
    elif prob >= 55:
        base = "중립~상승 시도"
    elif prob >= 45:
        base = "박스권/혼조 가능"
    else:
        base = "변동성 주의(보수 접근)"

    regime_txt = {"high": "고변동", "mid": "중변동", "low": "저변동"}.get(regime, "중변동")
    return f"{base} · {regime_txt} · {theme}"


def now_kst() -> str:
    return datetime.now().strftime("%Y-%m-%d(%a) %H:%M KST")
