# models/strategy_repo.py
from __future__ import annotations

import json
import time
import uuid
from typing import Dict, List, Optional

from models.db import get_conn


def create_strategy(
    user_id: str,
    name: str,
    description: str,
    entry: str,
    files: Dict[str, str],
) -> str:
    sid = uuid.uuid4().hex
    now = int(time.time())

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO strategies (id,user_id,name,description,entry,files_json,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (sid, user_id, name, description, entry, json.dumps(files), now, now),
    )
    conn.commit()
    conn.close()
    return sid


def list_strategies(user_id: str) -> List[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, name, description, entry, created_at, updated_at
        FROM strategies
        WHERE user_id=?
        ORDER BY updated_at DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_strategy(user_id: str, strategy_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM strategies WHERE id=? AND user_id=?",
        (strategy_id, user_id),
    ).fetchone()
    conn.close()

    if not row:
        return None

    d = dict(row)
    d["files"] = json.loads(d.get("files_json") or "{}")
    d.pop("files_json", None)
    return d


def update_strategy(
    user_id: str,
    strategy_id: str,
    name: str,
    description: str,
    entry: str,
    files: Dict[str, str],
) -> bool:
    now = int(time.time())
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE strategies
        SET name=?, description=?, entry=?, files_json=?, updated_at=?
        WHERE id=? AND user_id=?
        """,
        (name, description, entry, json.dumps(files), now, strategy_id, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def delete_strategy(user_id: str, strategy_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM strategies WHERE id=? AND user_id=?",
        (strategy_id, user_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0
