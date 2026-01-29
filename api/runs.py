# api/runs.py
from __future__ import annotations

import json
from flask import Blueprint, jsonify, request, send_from_directory

from services.data_sources import fetch_alpaca_bars, fetch_yfinance_bars
from services.runner_service import (
    create_workspace,
    write_user_files,
    write_manifest_and_data,
    run_in_docker,
    list_artifacts,
)
from models.run_repo import (
    create_run,
    get_run,
    list_runs,
    update_run_result,
)

bp = Blueprint("runs", __name__, url_prefix="/api/runs")


def _user_id() -> str:
    # MVP until auth is wired
    return "demo-user"


@bp.get("")
def http_list_runs():
    uid = _user_id()
    return jsonify(list_runs(user_id=uid))


@bp.post("")
def http_create_run():
    uid = _user_id()
    body = request.get_json(force=True) or {}

    provider = (body.get("provider") or "yfinance").lower()  # alpaca|yfinance
    symbols = [s.upper() for s in (body.get("symbols") or ["SPY"])]
    start = body.get("start") or "2024-01-01"
    end = body.get("end") or "2025-01-01"
    timeframe = body.get("timeframe") or "1Day"
    timeout_sec = int(body.get("timeout_sec") or 30)

    entry = body.get("entry") or "main.py"
    files = body.get("files") or {"main.py": body.get("code", "print('hello')\n")}

    # 1) Create run record
    run_id = create_run(
        user_id=uid,
        provider=provider,
        symbols=symbols,
        start=start,
        end=end,
        timeframe=timeframe,
        status="running",
    )

    # 2) Create workspace + write code
    ws = create_workspace(run_id)
    write_user_files(ws, files)
    meta = {
        "provider": provider,
        "symbols": symbols,
        "start": start,
        "end": end,
        "timeframe": timeframe,
        "params": params,  # ✅ include params for the container runner
    }
    # 2) Create workspace + write code
    ws = create_workspace(run_id)
    write_user_files(ws, files)

    # 3) Fetch data server-side
    if provider == "alpaca":
        frames = fetch_alpaca_bars(symbols, start, end, timeframe=timeframe)
    else:
        interval = "1d" if timeframe in ("1Day", "1D", "day") else "1m"
        frames = fetch_yfinance_bars(symbols, start, end, interval=interval)

    # 4) Write data + manifest into workspace
    write_manifest_and_data(ws, meta, frames)

    # 5) Run container
    exit_code, stdout, stderr = run_in_docker(ws, entry=entry, timeout_sec=timeout_sec)

    status = "done" if exit_code == 0 else ("timeout" if exit_code == 124 else "error")
    arts = list_artifacts(ws)

    # 6) Persist result
    update_run_result(
        user_id=uid,
        run_id=run_id,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )

    return jsonify({
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "artifacts": arts,
    })
    return jsonify(r)


@bp.get("/<run_id>/artifacts")
def http_list_artifacts(run_id: str):
    uid = _user_id()
    r = get_run(user_id=uid, run_id=run_id)
    if not r:
        return jsonify({"error": "not found"}), 404

    ws = create_workspace(run_id)
    return jsonify(list_artifacts(ws))


@bp.get("/<run_id>/artifacts/<name>")
def http_get_artifact(run_id: str, name: str):
    uid = _user_id()
    r = get_run(user_id=uid, run_id=run_id)
    if not r:
        return jsonify({"error": "not found"}), 404

    ws = create_workspace(run_id)
    art_dir = ws / "artifacts"
    return send_from_directory(art_dir, name, as_attachment=False)