from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: int) -> dict:
    eq = equity_df["equity"].astype(float)
    rets = eq.pct_change().dropna()

    total_return = (eq.iloc[-1] / eq.iloc[0]) - 1.0
    vol = float(rets.std() * np.sqrt(bars_per_year)) if len(rets) else 0.0
    sharpe = float((rets.mean() / (rets.std() + 1e-12)) * np.sqrt(bars_per_year)) if len(rets) else 0.0

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
