# api/insider_events.py
from __future__ import annotations

import json
from flask import Blueprint, jsonify, request

from models.db import get_conn

bp = Blueprint("insider_events", __name__, url_prefix="/api/insider-events")


@bp.get("")
def list_events():
    limit = min(int(request.args.get("limit", 200)), 1000)
    symbol = (request.args.get("symbol") or "").strip().upper() or None

    conn = get_conn()
    try:
        if symbol:
            rows = conn.execute(
                """
                SELECT id, ts, event_type, symbol, value_usd, accession, cik, payload_json
                FROM insider_events
                WHERE symbol = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, ts, event_type, symbol, value_usd, accession, cik, payload_json
                FROM insider_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.pop("payload_json") or "{}")
            out.append(d)

        return jsonify(out)
    finally:
        conn.close()
