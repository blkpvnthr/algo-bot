# services/alpaca_rest.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class AlpacaConfig:
    api_key: str
    api_secret: str
    # Market data base URL (SIP requires subscription; IEX is common default)
    data_base_url: str = "https://data.alpaca.markets"
    # Trading base URL (assets endpoint lives here)
    trading_base_url: str = "https://paper-api.alpaca.markets"


def get_alpaca_config() -> AlpacaConfig:
    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
    sec = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET")
    if not key or not sec:
        raise RuntimeError("Missing Alpaca keys: set APCA_API_KEY_ID and APCA_API_SECRET_KEY")

    # Optional overrides
    data_url = os.getenv("ALPACA_DATA_URL") or "https://data.alpaca.markets"
    trade_url = os.getenv("ALPACA_TRADING_URL") or os.getenv("APCA_API_BASE_URL") or "https://paper-api.alpaca.markets"
    return AlpacaConfig(api_key=key, api_secret=sec, data_base_url=data_url, trading_base_url=trade_url)


def _headers(cfg: AlpacaConfig) -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": cfg.api_key,
        "APCA-API-SECRET-KEY": cfg.api_secret,
    }


def alpaca_get_json(url: str, cfg: AlpacaConfig, params: Optional[Dict[str, Any]] = None) -> Any:
    r = requests.get(url, headers=_headers(cfg), params=params, timeout=15)
    r.raise_for_status()
    return r.json()
