from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd

from backtest.engine import run_backtest_target_weights
from backtest.metrics import compute_metrics


def load_manifest(ws: Path) -> dict:
    return json.loads((ws / "data" / "manifest.json").read_text(encoding="utf-8"))


def load_frames(ws: Path, manifest: dict) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for s in manifest.get("symbols", []):
        sym = s["symbol"]
        p = (ws / s["path"]).resolve()
        df = pd.read_parquet(p)

        if "ts" not in df.columns:
            raise RuntimeError(f"{sym}.parquet missing 'ts' column (write index as ts before parquet)")

        df["ts"] = pd.to_datetime(df["ts"])
        df = df.sort_values("ts").set_index("ts")
        frames[sym] = df

    if not frames:
        raise RuntimeError("no parquet frames found")
    return frames


def import_user_entry(ws: Path, entry: str):
    entry_path = (ws / entry).resolve()
    if not entry_path.exists():
        raise RuntimeError(f"entry not found: {entry}")

    spec = importlib.util.spec_from_file_location("user_entry", entry_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    if not hasattr(mod, "run"):
        raise RuntimeError("Strategy must define: def run(data, params): ...")

    return mod



def write_json(ws: Path, name: str, obj):
    out = ws / "artifacts" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def write_csv(ws: Path, name: str, df: pd.DataFrame):
    out = ws / "artifacts" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)


def bars_per_year(timeframe: str) -> int:
    tf = (timeframe or "1Day").lower()
    return 252 if "day" in tf else 252 * 390


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--entry", required=True)
    args = ap.parse_args()

    ws = Path(args.ws).resolve()
    (ws / "artifacts").mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(ws)
    meta = manifest.get("meta", {}) or {}
    params = meta.get("params", {}) or {}

    frames = load_frames(ws, manifest)

    # --- user decision ---
    mod = import_user_entry(ws, args.entry)
    decision = mod.run(frames, params)  # frames: dict[sym] -> df indexed by ts
    write_json(ws, "decision.json", decision)

    # --- MVP contract: target weights ---
    tw = decision.get("target_weights")
    if not isinstance(tw, dict) or not tw:
        raise RuntimeError("MVP requires return {'target_weights': {...}}")

    equity_df, trades_df = run_backtest_target_weights(
        frames=frames,
        target_weights=tw,
        capital=float(params.get("capital", 50000)),
        rebalance=str(params.get("rebalance", "monthly")),
        slippage_bps=float(params.get("slippage_bps", 1.0)),
        commission=float(params.get("commission", 0.0)),
    )

    equity_json = [{"ts": str(ix), "equity": float(v)} for ix, v in equity_df["equity"].items()]
    write_json(ws, "equity_curve.json", equity_json)
    write_csv(ws, "trades.csv", trades_df)

    m = compute_metrics(equity_df, bars_per_year(meta.get("timeframe", "1Day")))
    write_json(ws, "metrics.json", m)

    print(f"Backtest complete. Sharpe={m['sharpe']:.2f} MaxDD={m['max_drawdown']:.2%} Bars={m['num_bars']}")


if __name__ == "__main__":
    main()
