from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class Fill:
    ts: pd.Timestamp
    symbol: str
    qty: float
    fill_px: float


def _rebalance_points(index: pd.DatetimeIndex, cadence: str) -> set[pd.Timestamp]:
    if cadence == "daily":
        return set(index)
    if cadence == "weekly":
        return set(index[index.to_series().dt.weekday == 0])  # Mondays
    if cadence == "monthly":
        s = index.to_series()
        return set(index[s.dt.is_month_start])
    return set(index)


def run_backtest_target_weights(
    frames: Dict[str, pd.DataFrame],
    target_weights: Dict[str, float],
    capital: float,
    rebalance: str = "monthly",
    slippage_bps: float = 1.0,
    commission: float = 0.0,
    price_col: str = "close",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    frames: sym -> df indexed by ts with at least [price_col]
    target_weights: sym -> weight (sums to 1 typically)
    """
    if not frames:
        raise ValueError("no frames")

    # Align on common timestamps (intersection). Union is possible but more complex.
    idx = None
    for df in frames.values():
        idx = df.index if idx is None else idx.intersection(df.index)
    idx = idx.sort_values()
    if len(idx) < 5:
        raise ValueError("not enough overlapping bars")

    prices = pd.DataFrame({s: frames[s].loc[idx, price_col].astype(float) for s in frames})

    cash = float(capital)
    pos: Dict[str, float] = {s: 0.0 for s in frames}  # qty per symbol
    fills: List[Fill] = []
    eq_rows = []

    rb = _rebalance_points(idx, rebalance)
    slip = slippage_bps / 10000.0

    for t in idx:
        px = prices.loc[t].to_dict()

        # compute equity
        equity = cash + sum(pos[s] * px.get(s, 0.0) for s in pos)
        eq_rows.append({"ts": t, "equity": equity})

        # rebalance at t (simple: fills at close of same bar)
        if t not in rb:
            continue

        # target dollar per symbol
        for s, w in (target_weights or {}).items():
            if s not in px or np.isnan(px[s]):
                continue
            target_val = equity * float(w)
            cur_val = pos.get(s, 0.0) * float(px[s])
            delta_val = target_val - cur_val
            if abs(delta_val) < 1e-8:
                continue

            raw_px = float(px[s])
            fill_px = raw_px * (1 + slip) if delta_val > 0 else raw_px * (1 - slip)
            qty = 0.0 if fill_px == 0 else (delta_val / fill_px)

            # book it
            cash -= qty * fill_px
            cash -= commission
            pos[s] = pos.get(s, 0.0) + qty
            fills.append(Fill(ts=t, symbol=s, qty=qty, fill_px=fill_px))

    equity_df = pd.DataFrame(eq_rows).set_index("ts")
    trades_df = pd.DataFrame([f.__dict__ for f in fills])
    return equity_df, trades_df
