from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd

from services.storage_service import ensure_workspace, write_manifest_and_data, read_manifest
from services.exec_service import run_user_entry
from backtest.engine import run_backtest_target_weights
from backtest.metrics import compute_metrics


def write_artifact_text(ws: Path, name: str, text: str) -> None:
    ensure_workspace(ws)
    (ws / "artifacts" / name).write_text(text or "", encoding="utf-8")


def write_artifact_json(ws: Path, name: str, obj) -> None:
    ensure_workspace(ws)
    (ws / "artifacts" / name).write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def write_artifact_csv(ws: Path, name: str, df: pd.DataFrame) -> None:
    ensure_workspace(ws)
    df.to_csv(ws / "artifacts" / name, index=False)


def list_artifacts(ws: Path) -> list[str]:
    p = ws / "artifacts"
    if not p.exists():
        return []
    return sorted([x.name for x in p.iterdir() if x.is_file()])


def load_frames_from_workspace(ws: Path) -> Dict[str, pd.DataFrame]:
    manifest = read_manifest(ws)
    frames: Dict[str, pd.DataFrame] = {}
    for s in manifest.get("symbols", []):
        sym = s["symbol"]
        fp = (ws / s["path"]).resolve()
        df = pd.read_parquet(fp)
        # ensure indexed by ts
        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.sort_values("ts").set_index("ts")
        frames[sym] = df
    return frames


def bars_per_year(timeframe: str) -> int:
    return 252 if timeframe == "1Day" else 252 * 390


def run_backtest_job(ws: Path, entry: str, timeout_sec: int = 60) -> dict:
    # 1) run user code -> decision.json
    rc, stdout, stderr = run_user_entry(ws, entry, timeout_sec=timeout_sec)
    write_artifact_text(ws, "runner_stdout.txt", stdout)
    write_artifact_text(ws, "runner_stderr.txt", stderr)

    if rc != 0:
        return {"status": "error", "exit_code": rc, "stdout": stdout, "stderr": stderr, "artifacts": list_artifacts(ws)}

    decision_path = ws / "artifacts" / "decision.json"
    if not decision_path.exists():
        return {"status": "error", "exit_code": 1, "stdout": stdout, "stderr": "decision.json not produced", "artifacts": list_artifacts(ws)}

    decision = json.loads(decision_path.read_text(encoding="utf-8"))

    # 2) load frames and run engine
    manifest = read_manifest(ws)
    meta = manifest.get("meta", {})
    params = meta.get("params", {}) or {}

    frames = load_frames_from_workspace(ws)

    tw = decision.get("target_weights")
    if not isinstance(tw, dict) or not tw:
        return {"status": "error", "exit_code": 1, "stdout": stdout, "stderr": "Strategy must return {'target_weights': {...}} for MVP", "artifacts": list_artifacts(ws)}

    equity_df, trades_df = run_backtest_target_weights(
        frames=frames,
        target_weights=tw,
        capital=float(params.get("capital", 10000)),
        rebalance=str(params.get("rebalance", "monthly")),
        slippage_bps=float(params.get("slippage_bps", 1.0)),
        commission=float(params.get("commission", 0.0)),
        price_col="close",
    )

    # 3) artifacts
    equity_json = [{"ts": str(ix), "equity": float(v)} for ix, v in equity_df["equity"].items()]
    write_artifact_json(ws, "equity_curve.json", equity_json)
    write_artifact_csv(ws, "trades.csv", trades_df)

    m = compute_metrics(equity_df, bars_per_year(str(meta.get("timeframe", "1Day"))))
    write_artifact_json(ws, "metrics.json", m)

    return {
        "status": "ok",
        "exit_code": 0,
        "stdout": f"Backtest complete. Sharpe={m['sharpe']:.2f} MaxDD={m['max_drawdown']:.2%}",
        "stderr": stderr,
        "artifacts": list_artifacts(ws),
    }
