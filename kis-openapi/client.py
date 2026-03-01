import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests


BASE_URLS = {
    # 문서 기준 일반적으로 사용되는 도메인
    "real": "https://openapi.koreainvestment.com:9443",
    "mock": "https://openapivts.koreainvestment.com:29443",
}

TR_IDS = {
    # 국내주식 현재가 조회
    # 실전/모의 TR ID는 문서 업데이트에 따라 달라질 수 있음
    "quote_real": "FHKST01010100",
    "quote_mock": "FHKST01010100",
}


@dataclass
class KISConfig:
    mode: str
    app_key: str
    app_secret: str
    account_no: str = ""
    token_cache: str = ".kis_token.json"


class KISClient:
    def __init__(self, cfg: KISConfig):
        self.cfg = cfg
        if cfg.mode not in BASE_URLS:
            raise ValueError("KIS_MODE must be 'real' or 'mock'")
        self.base_url = BASE_URLS[cfg.mode]
        self._token: str | None = None

    def _cache_path(self) -> Path:
        return Path(self.cfg.token_cache)

    def _load_cached_token(self) -> str | None:
        p = self._cache_path()
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) > time.time() + 30:
                return data.get("access_token")
        except Exception:
            return None
        return None

    def _save_cached_token(self, token: str, expires_at_epoch: int):
        p = self._cache_path()
        payload = {
            "access_token": token,
            "expires_at": int(expires_at_epoch),
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_access_token(self, force_refresh: bool = False) -> str:
        if self._token and not force_refresh:
            return self._token

        if not force_refresh:
            cached = self._load_cached_token()
            if cached:
                self._token = cached
                return cached

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.cfg.app_key,
            "appsecret": self.cfg.app_secret,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"Token issue failed: {data}")

        expires_in = int(data.get("expires_in", 86400))

        # Prefer explicit expiry timestamp from API doc: access_token_token_expired
        expires_at_epoch = int(time.time()) + expires_in
        expired_at_text = data.get("access_token_token_expired")
        if expired_at_text:
            try:
                dt = datetime.strptime(expired_at_text, "%Y-%m-%d %H:%M:%S")
                expires_at_epoch = int(dt.timestamp())
            except Exception:
                pass

        self._save_cached_token(token, expires_at_epoch)
        self._token = token
        return token

    def _headers(self, tr_id: str) -> Dict[str, str]:
        token = self.get_access_token()
        return {
            "authorization": f"Bearer {token}",
            "appkey": self.cfg.app_key,
            "appsecret": self.cfg.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "content-type": "application/json; charset=utf-8",
        }

    def get_domestic_quote(self, symbol: str) -> Dict[str, Any]:
        """
        국내주식 현재가 조회
        참고: /uapi/domestic-stock/v1/quotations/inquire-price
        """
        path = "/uapi/domestic-stock/v1/quotations/inquire-price"
        url = f"{self.base_url}{path}"
        tr_id = TR_IDS["quote_real"] if self.cfg.mode == "real" else TR_IDS["quote_mock"]

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": symbol,
        }

        resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data



def load_config_from_env() -> KISConfig:
    mode = os.getenv("KIS_MODE", "mock").strip().lower()
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()
    account_no = os.getenv("KIS_ACCOUNT_NO", "").strip()
    token_cache = os.getenv("KIS_TOKEN_CACHE", ".kis_token.json").strip()

    missing = [k for k, v in {
        "KIS_APP_KEY": app_key,
        "KIS_APP_SECRET": app_secret,
    }.items() if not v]

    if missing:
        raise RuntimeError(f"Missing env: {', '.join(missing)}")

    return KISConfig(
        mode=mode,
        app_key=app_key,
        app_secret=app_secret,
        account_no=account_no,
        token_cache=token_cache,
    )
