# server/marketdata.py
import os
from flask import Blueprint, request, jsonify, current_app
import requests
from datetime import datetime
from dateutil import parser as dateparser

bp = Blueprint("marketdata", __name__)

# Use Alpaca Data API V2 base
ALPACA_BASE = "https://data.alpaca.markets/v2"

# Read keys from env
ALPACA_KEY = os.environ.get("APCA_API_KEY_ID")
ALPACA_SECRET = os.environ.get("APCA_API_SECRET_KEY")

# simple mapping from your UI timeframe to Alpaca timeframe parameter
TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "1H": "1Hour",
    "4H": "1Hour",   # Alpaca does not have 4H bars; consider 1Hour or 1Day aggregation server-side
    "1D": "1Day",
    "1W": "1Day"
}

def alpaca_headers():
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise RuntimeError("Alpaca API credentials not set in environment.")
    return {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }

@bp.route("/api/marketdata", methods=["GET"])
def marketdata():
    """
    Query params:
      symbol (required)
      start (ISO date, optional)
      end (ISO date, optional)
      timeframe (optional: 1m|5m|15m|1H|1D) default 1D
      limit (optional)
      feed (optional) -> 'stocks' or 'crypto' (default stocks)
    """
    symbol = request.args.get("symbol", "").strip()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    timeframe = request.args.get("timeframe", "1D")
    alp_tf = TIMEFRAME_MAP.get(timeframe, TIMEFRAME_MAP["1D"])

    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", None)
    feed = request.args.get("feed", "stocks")  # could extend to crypto

    # validate/normalize dates (Alpaca expects RFC3339/ISO8601)
    params = {"timeframe": alp_tf}
    if start:
        try:
            # parse to iso
            dt = dateparser.parse(start)
            params["start"] = dt.isoformat()
        except Exception:
            return jsonify({"error": "invalid start date"}), 400
    if end:
        try:
            dt = dateparser.parse(end)
            params["end"] = dt.isoformat()
        except Exception:
            return jsonify({"error": "invalid end date"}), 400
    if limit:
        try:
            params["limit"] = int(limit)
        except:
            pass

    # Build endpoint URL depending on feed
    # For stocks (example): /v2/stocks/{symbol}/bars
    # For crypto: /v2/crypto/{symbol}/bars (depends on Alpaca account and data access)
    if feed == "crypto":
        url = f"{ALPACA_BASE}/crypto/{symbol}/bars"
    else:
        url = f"{ALPACA_BASE}/stocks/{symbol}/bars"

    try:
        resp = requests.get(url, params=params, headers=alpaca_headers(), timeout=20)
    except requests.RequestException as e:
        current_app.logger.exception("Alpaca request failed")
        return jsonify({"error": "request failed", "message": str(e)}), 502

    # Forward status and JSON (or text) to client with light normalization
    if resp.status_code != 200:
        return jsonify({
            "error": "alpaca_error",
            "status_code": resp.status_code,
            "body": resp.text[:2000]
        }), 502

    data = resp.json()

    # Alpaca returns { bars: [...], next_page_token? } — normalize to a simple list of bars
    bars = data.get("bars") or data.get("bars", [])
    # Example bar: { "t":"2024-01-01T13:30:00Z", "o":..., "h":..., "l":..., "c":..., "v":... }
    # Convert to an easier format if needed (timestamp, o,h,l,c,v)
    normalized = []
    for b in bars:
        normalized.append({
            "t": b.get("t"),
            "o": b.get("o"),
            "h": b.get("h"),
            "l": b.get("l"),
            "c": b.get("c"),
            "v": b.get("v"),
        })

    return jsonify({
        "symbol": symbol,
        "timeframe": alp_tf,
        "bars": normalized,
        "raw_meta": {k: v for k, v in data.items() if k != "bars"}
    })
