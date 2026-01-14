# services/data_sources.py
from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


# ----------------------------
# Env helpers
# ----------------------------
def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def json_serializer(obj):
    """Useful if you want to jsonify Alpaca objects elsewhere."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


# ----------------------------
# Historical data
# ----------------------------
def fetch_alpaca_bars(
    symbols: List[str],
    start: str,
    end: str,
    timeframe: str = "1Day",
) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical bars from Alpaca and return {symbol: dataframe}.
    DataFrame includes a 'date' column (UTC).
    """
    key = _env("ALPACA_API_KEY")
    secret = _env("ALPACA_SECRET_KEY")  # <- consistent name

    client = StockHistoricalDataClient(key, secret)

    tf = TimeFrame.Day if timeframe in ("1Day", "1D", "day") else TimeFrame.Minute

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=tf,
        start=pd.Timestamp(start, tz="UTC"),
        end=pd.Timestamp(end, tz="UTC"),
        adjustment="raw",
    )

    bars = client.get_stock_bars(req).df  # multi-index df: (symbol, timestamp)

    out: Dict[str, pd.DataFrame] = {}
    if bars is None or len(bars) == 0:
        return out

    for sym in symbols:
        try:
            df = bars.xs(sym, level=0).reset_index()
        except Exception:
            continue
        df.rename(columns={"timestamp": "date"}, inplace=True)
        out[sym] = df

    return out


def fetch_yfinance_bars(
    symbols: List[str],
    start: str,
    end: str,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical bars from yfinance and return {symbol: dataframe}.
    DataFrame includes a 'date' column (local exchange tz or naive; yfinance behavior varies).
    """
    out: Dict[str, pd.DataFrame] = {}

    for sym in symbols:
        df = yf.download(
            sym,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
        if df is None or df.empty:
            continue

        df = df.reset_index()

        # yfinance uses 'Date' for 1d, 'Datetime' for intraday
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "date"}, inplace=True)
        elif "Date" in df.columns:
            df.rename(columns={"Date": "date"}, inplace=True)

        df.columns = [c.lower() for c in df.columns]
        out[sym] = df

    return out


# ----------------------------
# Trading (orders)
# ----------------------------
def place_market_order(symbol: str, qty: int, side: str) -> dict:
    """
    Place a market order via Alpaca trading API.
    Expects env vars:
      - ALPACA_API_KEY
      - ALPACA_SECRET_KEY
      - ALPACA_PAPER=true|false  (default true)
    """
    key = _env("ALPACA_API_KEY")
    secret = _env("ALPACA_SECRET_KEY")
    paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

    trading_client = TradingClient(key, secret, paper=paper)

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=int(qty),
        side=OrderSide(side),         # "buy" | "sell"
        time_in_force=TimeInForce.DAY
    )
    order_response = trading_client.submit_order(order_data=order_data)

    # Alpaca response objects are not always JSON-serializable directly
    return order_response.__dict__
