# api/explore.py
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request

from services.alpaca_rest import alpaca_get_json, get_alpaca_config

bp = Blueprint("explore", __name__, url_prefix="/api/explore")

# ---- simple in-memory cache for assets ----
_ASSET_CACHE: Dict[str, Any] = {"ts": 0.0, "assets": []}
_ASSET_TTL_SEC = 6 * 60 * 60  # 6 hours


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _round(v: float | None, nd: int = 2) -> float | None:
    if v is None or not math.isfinite(v):
        return None
    return round(v, nd)


def _get_assets_cached() -> List[Dict[str, Any]]:
    now = time.time()
    if _ASSET_CACHE["assets"] and (now - float(_ASSET_CACHE["ts"])) < _ASSET_TTL_SEC:
        return _ASSET_CACHE["assets"]

    cfg = get_alpaca_config()
    url = f"{cfg.trading_base_url}/v2/assets"
    # Pull all active US equities; we filter client-side by query
    assets = alpaca_get_json(url, cfg, params={"status": "active", "asset_class": "us_equity"})
    # assets is a list of dicts
    _ASSET_CACHE["assets"] = assets
    _ASSET_CACHE["ts"] = now
    return assets


@bp.get("/search")
def explore_search():
    q = (request.args.get("q") or "").strip().upper()
    if not q:
        return jsonify([])

    assets = _get_assets_cached()

    # Simple “contains” match on symbol + name. Limit results for UI.
    out: List[Dict[str, str]] = []
    for a in assets:
        sym = (a.get("symbol") or "").upper()
        name = (a.get("name") or "")
        if not sym:
            continue
        if q in sym or q in name.upper():
            out.append({
                "symbol": sym,
                "name": name,
                "type": (a.get("class") or "Stock").upper(),
            })
        if len(out) >= 12:
            break

    return jsonify(out)


def _bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Calls Alpaca Market Data v2 bars endpoint.
    Feed defaults to IEX for broad compatibility.
    """
    cfg = get_alpaca_config()
    url = f"{cfg.data_base_url}/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": timeframe,          # "1Min" / "1Day" etc.
        "start": _iso(start),
        "end": _iso(end),
        "adjustment": "raw",
        "feed": "iex",                   # change to "sip" if you have access
        "limit": 10000,
    }
    j = alpaca_get_json(url, cfg, params=params)
    return j.get("bars") or []


@bp.get("/quote")
def explore_quote():
    symbol = (request.args.get("symbol") or "SPY").strip().upper()

    # We’ll compute:
    # - last = latest close from recent intraday bars (or daily bars fallback)
    # - change/% = last - prev_close from daily bars
    # - day range/volume = from today’s intraday bars (fallback to daily)
    now = _now_utc()
    start_intraday = now - timedelta(days=5)  # enough to cover weekends/holidays
    start_daily = now - timedelta(days=14)

    # Intraday bars (1Min): used for "last", "day_low/high", "volume"
    intraday = _bars(symbol, "1Min", start_intraday, now)
    # Daily bars (1Day): used for prev close
    daily = _bars(symbol, "1Day", start_daily, now)

    last = None
    day_low = None
    day_high = None
    volume = None
    asof = ""

    # intraday bars include fields: t,o,h,l,c,v (t is RFC3339)
    if intraday:
        # Find bars that are "today" in UTC; this is imperfect for US market day,
        # but good enough for MVP. Improve later by using NYSE session date.
        today = now.date()
        todays = []
        for b in intraday:
            t = b.get("t")
            try:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.date() == today:
                todays.append(b)

        src = todays if todays else intraday

        last = _safe_float(src[-1].get("c"))
        day_low = min((_safe_float(x.get("l")) for x in src), default=None)
        day_high = max((_safe_float(x.get("h")) for x in src), default=None)
        volume = sum((int(x.get("v") or 0) for x in src))
        asof = src[-1].get("t") or ""

    # fallback to daily if intraday missing
    if last is None and daily:
        last = _safe_float(daily[-1].get("c"))
        day_low = _safe_float(daily[-1].get("l"))
        day_high = _safe_float(daily[-1].get("h"))
        volume = int(daily[-1].get("v") or 0)
        asof = daily[-1].get("t") or ""

    prev_close = None
    if len(daily) >= 2:
        prev_close = _safe_float(daily[-2].get("c"))

    change = None
    change_pct = None
    if last is not None and prev_close not in (None, 0.0):
        change = last - prev_close
        change_pct = (change / prev_close) * 100.0

    # Format for your UI fields
    return jsonify({
        "symbol": symbol,
        "last": _round(last, 2),
        "change": _round(change, 2) if change is not None else None,
        "change_pct": (f"{_round(change_pct, 2):.2f}%" if change_pct is not None else None),
        "day_low": _round(day_low, 2),
        "day_high": _round(day_high, 2),
        "volume": volume,
        "asof": asof,
    })


@bp.get("/news")
def explore_news():
    # MVP placeholder. If you want Alpaca news next, we can wire it here.
    # Return shape expected by your JS: [{title,url,source,ts}]
    symbol = (request.args.get("symbol") or "SPY").strip().upper()
    return jsonify([])
