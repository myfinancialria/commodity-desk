"""Vectorised daily backtester + the strategy library.

A strategy is a function(prices, events) -> positions Series (+1 long / -1 short
/ 0 flat, indexed like prices). backtest() turns positions into an equity curve
and the usual stats (CAGR, Sharpe, max drawdown, win-rate, trades). Every
strategy on the dashboard is run through this before any live signal is shown.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def backtest(prices: pd.DataFrame, positions: pd.Series,
             cost_bps: float = 2.0) -> dict:
    """positions: desired position for the NEXT session (applied with a 1-day lag
    to avoid look-ahead). cost_bps charged on every position change."""
    close = prices["Close"].astype(float)
    ret = close.pct_change().fillna(0.0)
    pos = positions.reindex(close.index).ffill().fillna(0.0)
    lagged = pos.shift(1).fillna(0.0)                    # no look-ahead
    turnover = (pos - lagged).abs()
    cost = turnover * (cost_bps / 10_000.0)
    strat = lagged * ret - cost
    equity = (1.0 + strat).cumprod()

    n = len(strat)
    years = n / TRADING_DAYS if n else 1
    total = float(equity.iloc[-1] - 1) if n else 0.0
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if n and equity.iloc[-1] > 0 else 0.0
    vol = float(strat.std() * np.sqrt(TRADING_DAYS))
    sharpe = float(strat.mean() * TRADING_DAYS / vol) if vol else 0.0
    dd = float((equity / equity.cummax() - 1).min()) if n else 0.0
    active = strat[lagged != 0]
    win = float((active > 0).mean()) if len(active) else 0.0
    exposure = float((lagged != 0).mean()) if n else 0.0
    trades = _trades(close, pos)
    tw = [t for t in trades if t["ret_pct"] > 0]

    return {
        "total_return_pct": round(total * 100, 1),
        "cagr_pct": round(cagr * 100, 1),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(dd * 100, 1),
        "day_win_rate_pct": round(win * 100, 1),
        "exposure_pct": round(exposure * 100, 1),
        "num_trades": len(trades),
        "trade_win_rate_pct": round(len(tw) / len(trades) * 100, 1) if trades else 0.0,
        "avg_trade_pct": round(float(np.mean([t["ret_pct"] for t in trades])), 2) if trades else 0.0,
        "equity_curve": [{"date": d.date().isoformat(), "equity": round(float(v), 4)}
                          for d, v in equity.iloc[::max(1, n // 400)].items()],
        "recent_trades": trades[-15:],
    }


def _trades(close: pd.Series, pos: pd.Series) -> list[dict]:
    """Group runs of a constant non-zero position into round-trip trades."""
    trades, cur = [], None
    vals = pos.values
    idx = pos.index
    for k in range(len(vals)):
        p = vals[k]
        if cur is None and p != 0:
            cur = {"side": "Long" if p > 0 else "Short", "i0": k}
        elif cur is not None and (p == 0 or np.sign(p) != np.sign(vals[cur["i0"]])):
            i0, i1 = cur["i0"], k
            entry, exit_ = float(close.iloc[i0]), float(close.iloc[i1])
            r = (exit_ / entry - 1) * (1 if cur["side"] == "Long" else -1)
            trades.append({"side": cur["side"],
                            "entry_date": idx[i0].date().isoformat(),
                            "exit_date": idx[i1].date().isoformat(),
                            "entry": round(entry, 2), "exit": round(exit_, 2),
                            "ret_pct": round(r * 100, 2)})
            cur = {"side": "Long" if p > 0 else "Short", "i0": k} if p != 0 else None
    return trades


# ---------------- strategy library ----------------

def strat_trend(prices: pd.DataFrame, events=None, fast=20, slow=50) -> pd.Series:
    """Baseline: long when fast MA > slow MA, short otherwise."""
    c = prices["Close"].astype(float)
    f, s = c.rolling(fast).mean(), c.rolling(slow).mean()
    return pd.Series(np.where(f > s, 1.0, -1.0), index=c.index)


def strat_event(prices: pd.DataFrame, events: list[dict], hold: int = 1) -> pd.Series:
    """Trade the report: on the release day take a position for `hold` days in the
    direction the edge implies (fade a bearish surprise = short; bullish = long)."""
    c = prices["Close"].astype(float)
    pos = pd.Series(0.0, index=c.index)
    dates = c.index
    for ev in events or []:
        d = ev.get("direction")
        if d not in ("bearish", "bullish"):
            continue
        i = dates.searchsorted(pd.Timestamp(ev["date"]))
        if i >= len(dates):
            continue
        side = 1.0 if d == "bullish" else -1.0
        pos.iloc[i:i + hold] = side
    return pos


def strat_event_plus_trend(prices: pd.DataFrame, events: list[dict]) -> pd.Series:
    """Event signal, but only when it agrees with the prevailing trend."""
    ev = strat_event(prices, events)
    tr = strat_trend(prices)
    return pd.Series(np.where(np.sign(ev) == np.sign(tr), ev, 0.0), index=ev.index)


STRATEGIES = {
    "Trend (20/50 MA)": strat_trend,
    "Inventory/Event edge": strat_event,
    "Event + Trend filter": strat_event_plus_trend,
}


def run_all(prices: pd.DataFrame, events: list[dict]) -> dict:
    out = {}
    for name, fn in STRATEGIES.items():
        try:
            pos = fn(prices, events)
            out[name] = backtest(prices, pos)
        except Exception as e:  # noqa: BLE001
            out[name] = {"error": str(e)}
    return out
