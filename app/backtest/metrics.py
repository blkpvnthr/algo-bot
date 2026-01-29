from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: int) -> dict:
    """Compute basic performance metrics from an equity curve."""
    if equity_df.empty:
        return {
            "start_equity": 0.0,
            "end_equity": 0.0,
            "total_return": 0.0,
            "annualized_vol": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "num_bars": 0,
        }

    eq = equity_df["equity"].astype(float)
    rets = eq.pct_change().dropna()

    total_return = (eq.iloc[-1] / eq.iloc[0]) - 1.0
    vol = float(rets.std() * np.sqrt(bars_per_year)) if len(rets) else 0.0
    sharpe = float(
        (rets.mean() / (rets.std() + 1e-12)) * np.sqrt(bars_per_year)
    ) if len(rets) else 0.0

    peak = eq.cummax()
    dd = (eq / peak) - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0

    return {
        "start_equity": float(eq.iloc[0]),
        "end_equity": float(eq.iloc[-1]),
        "total_return": float(total_return),
        "annualized_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "num_bars": int(len(eq)),
    }


def run(data, params):
    """
    Strategy entrypoint for your backtest runner.

    data:   dict[symbol] -> DataFrame (indexed by ts)
    params: dict of strategy params (risk, rebalance, etc.)
    """
    syms = list(data.keys())
    if not syms:
        return {"target_weights": {}}

    # Equal-weight buy & hold across all symbols
    w = 1.0 / len(syms)
    weights = {s: w for s in syms}

    # Optional: if you later pass custom weights via params["weights"],
    # you can normalize them like this:
    #
    # raw = params.get("weights")
    # if isinstance(raw, dict):
    #     weights = {s: float(raw.get(s, 0.0)) for s in syms}
    #     total = sum(abs(v) for v in weights.values()) or 1.0
    #     weights = {s: v / total for s, v in weights.items()}

    print("target_weights:", weights)
    return {"target_weights": weights}
