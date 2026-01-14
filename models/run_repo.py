# models/run_repo.py
from __future__ import annotations

import json
import time
import uuid
from typing import List, Optional

from models.db import get_conn


def create_run(
    user_id: str,
    provider: str,
    symbols: List[str],
    start: str,
    end: str,
    timeframe: str,
    status: str = "running",
    strategy_id: str | None = None,
) -> str:
    rid = uuid.uuid4().hex
    now = int(time.time())

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO runs (id,user_id,strategy_id,provider,symbols_json,start,end,timeframe,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (rid, user_id, strategy_id, provider, json.dumps(symbols), start, end, timeframe, status, now, now),
    )
    conn.commit()
    conn.close()
    return rid


def list_runs(user_id: str) -> List[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, strategy_id, provider, symbols_json, start, end, timeframe, status, exit_code, created_at, updated_at
        FROM runs
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id,),
    ).fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["symbols"] = json.loads(d.get("symbols_json") or "[]")
        d.pop("symbols_json", None)
        out.append(d)
    return out


def get_run(user_id: str, run_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM runs WHERE id=? AND user_id=?",
        (run_id, user_id),
    ).fetchone()
    conn.close()

    if not row:
        return None

    d = dict(row)
    d["symbols"] = json.loads(d.get("symbols_json") or "[]")
    d.pop("symbols_json", None)
    return d


def update_run_result(
    user_id: str,
    run_id: str,
    status: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> bool:
    now = int(time.time())
    # store last N chars to avoid DB bloat
    stdout = (stdout or "")[-200_000:]
    stderr = (stderr or "")[-200_000:]

    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE runs
        SET status=?, exit_code=?, stdout=?, stderr=?, updated_at=?
        WHERE id=? AND user_id=?
        """,
        (status, exit_code, stdout, stderr, now, run_id, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0
