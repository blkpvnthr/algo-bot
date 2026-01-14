import os
import json
import time
import uuid
import shutil
import sqlite3
import subprocess
from pathlib import Path
from threading import Thread
from uuid import UUID
from datetime import datetime

import pandas as pd
import yfinance as yf
from flask import Flask, render_template, request, jsonify, send_from_directory

from websocket import WebSocketApp, enableTrace  # websocket-client

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

# Optional (historical data):
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# -----------------------------
# Config (ENV ONLY)
# -----------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

WS_URL = os.getenv("ALPACA_WS_URL", "wss://stream.data.alpaca.markets/v2/iex")
RUNNER_IMAGE = os.getenv("RUNNER_IMAGE", "trading-runner:latest")
WORK_ROOT = Path(os.getenv("WORK_ROOT", "workspaces"))

# Safety caps
RUN_TIMEOUT_SEC_DEFAULT = int(os.getenv("RUN_TIMEOUT_SEC", "30"))
RUN_CPUS = os.getenv("RUN_CPUS", "1.0")
RUN_MEMORY = os.getenv("RUN_MEMORY", "768m")
RUN_PIDS = os.getenv("RUN_PIDS", "256")

# DB
DB_PATH = os.getenv("DB_PATH", "app.db")

app = Flask(
    __name__,
    template_folder="templates",  # keep your existing templates folder
    static_folder="static",
)

# -----------------------------
# Init clients
# -----------------------------
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
historical_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

# State for WS logic
previous_prices: dict[str, float] = {}
ws_thread: Thread | None = None
ws_running = False

# -----------------------------
# Helpers
# -----------------------------
def json_serializer(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def ensure_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS strategies (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            entry TEXT NOT NULL DEFAULT 'main.py',
            files_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            strategy_id TEXT,
            provider TEXT NOT NULL,
            symbols_json TEXT NOT NULL,
            start TEXT,
            end TEXT,
            timeframe TEXT,
            status TEXT NOT NULL,
            exit_code INTEGER,
            stdout TEXT,
            stderr TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    con.commit()
    con.close()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def current_user_id() -> str:
    # Drop-in: single user MVP. Replace with real auth later.
    return "demo-user"

def ws_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def create_workspace(run_id: str) -> Path:
    ws = WORK_ROOT / run_id
    ws_mkdir(ws)
    ws_mkdir(ws / "data")
    ws_mkdir(ws / "artifacts")
    return ws

def write_manifest(ws: Path, meta: dict, symbol_paths: list[dict]) -> None:
    manifest = {"meta": meta, "symbols": symbol_paths}
    (ws / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

def fetch_yfinance(symbols: list[str], start: str, end: str, interval: str) -> dict[str, pd.DataFrame]:
    out = {}
    for sym in symbols:
        df = yf.download(sym, start=start, end=end, interval=interval, auto_adjust=False, progress=False)
        if df is None or df.empty:
            continue
        df = df.reset_index()
        # standardize
        df.rename(columns={"Date": "date", "Datetime": "date"}, inplace=True)
        df.columns = [c.lower() for c in df.columns]
        out[sym] = df
    return out

def fetch_alpaca(symbols: list[str], start: str, end: str, timeframe: str) -> dict[str, pd.DataFrame]:
    tf = TimeFrame.Day if timeframe in ("1Day", "1D", "day") else TimeFrame.Minute
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=tf,
        start=pd.Timestamp(start, tz="UTC"),
        end=pd.Timestamp(end, tz="UTC"),
        adjustment="raw",
    )
    bars = historical_client.get_stock_bars(req).df
    out = {}
    for sym in symbols:
        try:
            df = bars.xs(sym, level=0).reset_index()
        except Exception:
            continue
        df.rename(columns={"timestamp": "date"}, inplace=True)
        out[sym] = df
    return out

def place_market_order(symbol: str, qty: int, side: str):
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide(side),
        time_in_force=TimeInForce.DAY
    )
    order_response = trading_client.submit_order(order_data=order_data)
    d = order_response.__dict__
    print("Market order response:", json.dumps(d, default=json_serializer, indent=2))
    return d

def docker_run(ws: Path, entry: str, timeout_sec: int) -> tuple[int, str, str]:
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--cpus", RUN_CPUS,
        "--memory", RUN_MEMORY,
        "--pids-limit", RUN_PIDS,
        "--security-opt", "no-new-privileges",
        "-v", f"{ws.resolve()}:/work",
        "-w", "/work",
        RUNNER_IMAGE,
        "python", entry
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", (e.stderr or "") + "\nTIMEOUT"

def list_artifacts(ws: Path) -> list[str]:
    art = ws / "artifacts"
    if not art.exists():
        return []
    return sorted([p.name for p in art.iterdir() if p.is_file()])

# -----------------------------
# WebSocket callbacks (kept from your original)
# -----------------------------
def on_message(ws, message):
    data = json.loads(message)
    print("Received message:", json.dumps(data, indent=2))
    for update in data:
        if update.get('T') == 't':  # Trade update
            symbol = update['S']
            price = float(update['p'])
            print(f"Trade update for {symbol}: Price = {price}")

            # Example hardcoded logic (you can replace later):
            if symbol == 'QBTS':
                if symbol in previous_prices:
                    prev = previous_prices[symbol]
                    if prev - price >= 0.05:
                        place_market_order(symbol="QBTS", qty=10, side="buy")
                previous_prices[symbol] = price

        elif update.get('T') == 'q':  # Quote update
            symbol = update['S']
            bid_price = update['bp']
            ask_price = update['ap']
            print(f"Quote update for {symbol}: Bid = {bid_price}, Ask = {ask_price}")

        elif update.get('T') == 'b':  # Bar update
            symbol = update['S']
            o, h, l, c, v = update['o'], update['h'], update['l'], update['c'], update['v']
            print(f"Bar update {symbol}: O={o}, H={h}, L={l}, C={c}, V={v}")

def on_error(ws, error):
    print("WS Error:", error)

def on_close(ws, close_status_code, close_msg):
    global ws_running
    ws_running = False
    print("### WS closed ###", close_status_code, close_msg)

def on_open(ws):
    print("WebSocket opened")
    auth_data = {"action": "auth", "key": ALPACA_API_KEY, "secret": ALPACA_SECRET_KEY}
    ws.send(json.dumps(auth_data))
    subscribe_message = {"action": "subscribe", "trades": ["QBTS"], "quotes": ["QBTS"], "bars": ["QBTS"]}
    ws.send(json.dumps(subscribe_message))

def start_ws_thread():
    global ws_thread, ws_running
    if ws_running:
        return
    ws_running = True

    def run():
        # set to True only in debugging
        enableTrace(False)
        ws = WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever()

    ws_thread = Thread(target=run, daemon=True)
    ws_thread.start()

# -----------------------------
# HTML routes (kept compatible)
# -----------------------------
@app.route('/')
def index():
    ensure_db()
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_websocket():
    start_ws_thread()
    return render_template('response.html', response="WebSocket started")

@app.route('/trade', methods=['POST'])
def manual_trade():
    symbol = request.form['symbol']
    qty = int(request.form['qty'])
    side = request.form['side']
    resp = place_market_order(symbol, qty, side)
    return render_template('response.html', response=json.dumps(resp, default=json_serializer, indent=2))

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json or {}
    print(f"Received webhook data: {data}")
    symbol = data.get('symbol')
    side = data.get('side')
    qty = int(data.get('qty', 1))
    resp = place_market_order(symbol, qty, side)
    resp_json = json.dumps(resp, default=json_serializer, indent=2)
    return render_template('webhooksss.html', response=resp_json)

# -----------------------------
# API: My Strategies (single-file MVP)
# -----------------------------
@app.get("/api/strategies")
def api_list_strategies():
    ensure_db()
    uid = current_user_id()
    con = db()
    rows = con.execute(
        "SELECT id,name,description,updated_at FROM strategies WHERE user_id=? ORDER BY updated_at DESC",
        (uid,)
    ).fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/strategies")
def api_create_strategy():
    ensure_db()
    uid = current_user_id()
    body = request.get_json(force=True)

    sid = body.get("id") or uuid.uuid4().hex
    now = int(time.time())

    files = body.get("files")
    if not files:
        # single-file default
        files = {"main.py": body.get("code", "# main.py\nprint('hello')\n")}

    con = db()
    con.execute(
        "INSERT INTO strategies (id,user_id,name,description,entry,files_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (sid, uid, body["name"], body.get("description", ""), body.get("entry", "main.py"),
         json.dumps(files), now, now)
    )
    con.commit()
    con.close()
    return jsonify({"id": sid})

@app.get("/api/strategies/<sid>")
def api_get_strategy(sid):
    ensure_db()
    uid = current_user_id()
    con = db()
    row = con.execute("SELECT * FROM strategies WHERE id=? AND user_id=?", (sid, uid)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    d = dict(row)
    d["files"] = json.loads(d["files_json"] or "{}")
    d.pop("files_json", None)
    return jsonify(d)

@app.put("/api/strategies/<sid>")
def api_update_strategy(sid):
    ensure_db()
    uid = current_user_id()
    body = request.get_json(force=True)
    now = int(time.time())

    files = body.get("files")
    if not files and "code" in body:
        files = {"main.py": body["code"]}

    con = db()
    cur = con.execute(
        "UPDATE strategies SET name=?, description=?, entry=?, files_json=?, updated_at=? WHERE id=? AND user_id=?",
        (body["name"], body.get("description", ""), body.get("entry", "main.py"),
         json.dumps(files or {}), now, sid, uid)
    )
    con.commit()
    con.close()
    if cur.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})

@app.delete("/api/strategies/<sid>")
def api_delete_strategy(sid):
    ensure_db()
    uid = current_user_id()
    con = db()
    cur = con.execute("DELETE FROM strategies WHERE id=? AND user_id=?", (sid, uid))
    con.commit()
    con.close()
    if cur.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})

# -----------------------------
# API: Runs (fetch data from Alpaca or yfinance, run in Docker)
# -----------------------------
@app.post("/api/runs")
def api_run():
    ensure_db()
    uid = current_user_id()
    body = request.get_json(force=True)

    provider = body.get("provider", "yfinance")  # "alpaca" | "yfinance"
    symbols = [s.upper() for s in (body.get("symbols") or ["SPY"])]
    start = body.get("start") or "2024-01-01"
    end = body.get("end") or "2025-01-01"
    timeframe = body.get("timeframe", "1Day")   # "1Day"/"1Min" or mapped
    timeout_sec = int(body.get("timeout_sec", RUN_TIMEOUT_SEC_DEFAULT))

    files = body.get("files") or {"main.py": body.get("code", "print('hello')\n")}
    entry = body.get("entry", "main.py")

    run_id = uuid.uuid4().hex
    ws = create_workspace(run_id)

    # Write user code
    for name, content in files.items():
        p = ws / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # Fetch dataset server-side
    if provider == "alpaca":
        frames = fetch_alpaca(symbols, start, end, timeframe=timeframe)
    else:
        interval = "1d" if timeframe in ("1Day", "1D", "day") else "1m"
        frames = fetch_yfinance(symbols, start, end, interval=interval)

    # Write parquet + manifest
    symbol_paths = []
    for sym, df in frames.items():
        outp = ws / "data" / f"{sym}.parquet"
        df.to_parquet(outp, index=False)
        symbol_paths.append({"symbol": sym, "path": f"data/{sym}.parquet"})

    meta = {"provider": provider, "symbols": symbols, "start": start, "end": end, "timeframe": timeframe}
    write_manifest(ws, meta, symbol_paths)

    # Record run (MVP stores stdout/stderr in DB; fine for small output)
    now = int(time.time())
    con = db()
    con.execute(
        "INSERT INTO runs (id,user_id,provider,symbols_json,start,end,timeframe,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (run_id, uid, provider, json.dumps(symbols), start, end, timeframe, "running", now, now)
    )
    con.commit()
    con.close()

    # Execute
    exit_code, stdout, stderr = docker_run(ws, entry=entry, timeout_sec=timeout_sec)

    status = "done" if exit_code == 0 else ("timeout" if exit_code == 124 else "error")
    con = db()
    con.execute(
        "UPDATE runs SET status=?, exit_code=?, stdout=?, stderr=?, updated_at=? WHERE id=? AND user_id=?",
        (status, exit_code, stdout[-200000:], stderr[-200000:], int(time.time()), run_id, uid)
    )
    con.commit()
    con.close()

    return jsonify({
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "artifacts": list_artifacts(ws),
    })

@app.get("/api/runs/<run_id>")
def api_get_run(run_id):
    ensure_db()
    uid = current_user_id()
    con = db()
    row = con.execute("SELECT * FROM runs WHERE id=? AND user_id=?", (run_id, uid)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    d = dict(row)
    d["symbols"] = json.loads(d.get("symbols_json") or "[]")
    d.pop("symbols_json", None)
    d["artifacts"] = list_artifacts(WORK_ROOT / run_id)
    return jsonify(d)

@app.get("/api/runs/<run_id>/artifacts")
def api_list_artifacts(run_id):
    uid = current_user_id()
    # basic ownership check via runs table
    con = db()
    row = con.execute("SELECT id FROM runs WHERE id=? AND user_id=?", (run_id, uid)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(list_artifacts(WORK_ROOT / run_id))

@app.get("/api/runs/<run_id>/artifacts/<name>")
def api_get_artifact(run_id, name):
    uid = current_user_id()
    con = db()
    row = con.execute("SELECT id FROM runs WHERE id=? AND user_id=?", (run_id, uid)).fetchone()
    con.close()
    if not row:
        return jsonify({"error": "not found"}), 404

    ws = WORK_ROOT / run_id / "artifacts"
    return send_from_directory(ws, name, as_attachment=False)

# -----------------------------
# Start
# -----------------------------
if __name__ == "__main__":
    ensure_db()
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=5001, debug=True)
