# models/db.py
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "data/app.db")


def get_conn() -> sqlite3.Connection:
    # Ensure the folder for the DB exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Create tables
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                entry TEXT NOT NULL,
                files_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_strategies_user
                ON strategies(user_id);

            CREATE INDEX IF NOT EXISTS idx_strategies_user_created
                ON strategies(user_id, created_at);

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                symbols_json TEXT NOT NULL,
                start TEXT NOT NULL,
                end TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_runs_user
                ON runs(user_id);

            CREATE INDEX IF NOT EXISTS idx_runs_user_created
                ON runs(user_id, created_at);

            -- ============================
            -- Insider bot event stream
            -- ============================
            CREATE TABLE IF NOT EXISTS insider_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                event_type TEXT NOT NULL,              -- FORM4_SEEN | BUY_SIGNAL | BUY_PLACED | SELL_SIGNAL | LIQUIDATED | ERROR
                symbol TEXT,
                value_usd TEXT,                        -- store as text to avoid float issues
                accession TEXT,
                cik TEXT,
                payload_json TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_insider_events_ts
                ON insider_events(ts);

            CREATE INDEX IF NOT EXISTS idx_insider_events_symbol_ts
                ON insider_events(symbol, ts);

            -- ============================
            -- Insider bot dedupe table
            -- ============================
            CREATE TABLE IF NOT EXISTS seen_form4 (
                accession TEXT PRIMARY KEY,
                first_seen INTEGER NOT NULL
            );
            """
        )

        conn.commit()
    finally:
        conn.close()
