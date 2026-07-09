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


# ---- indicators ----
def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _atr(prices, n=14):
    d = prices
    tr = pd.concat([d["High"] - d["Low"],
                    (d["High"] - d["Close"].shift()).abs(),
                    (d["Low"] - d["Close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


# ---- professional strategy library (each -> positions -1/0/+1) ----
def strat_donchian(prices, events=None, entry=20, exit_=10) -> pd.Series:
    """Turtle-style channel breakout: long above the 20-day high, short below the
    20-day low; ride until the opposite 10-day channel flips it."""
    c = prices["Close"].astype(float)
    hi, lo = prices["High"].rolling(entry).max(), prices["Low"].rolling(entry).min()
    pos = pd.Series(np.nan, index=c.index)
    pos[c > hi.shift()] = 1.0
    pos[c < lo.shift()] = -1.0
    return pos.ffill().fillna(0.0)


def strat_macd(prices, events=None, f=12, s=26, sig=9) -> pd.Series:
    """MACD line vs signal line — a smoother trend filter than raw MAs."""
    c = prices["Close"].astype(float)
    macd = _ema(c, f) - _ema(c, s)
    return pd.Series(np.where(macd > _ema(macd, sig), 1.0, -1.0), index=c.index)


def strat_rsi2(prices, events=None) -> pd.Series:
    """Connors RSI(2) mean-reversion with a 200-day trend filter — buy dips in an
    uptrend, sell rips in a downtrend, exit at the 5-day mean."""
    c = prices["Close"].astype(float)
    r, ma200, ma5 = _rsi(c, 2), c.rolling(200).mean(), c.rolling(5).mean()
    pos = pd.Series(np.nan, index=c.index)
    pos[(r < 10) & (c > ma200)] = 1.0
    pos[(r > 90) & (c < ma200)] = -1.0
    pos[(c > ma5) & (pos.isna())] = 0.0     # exit longs at the mean
    return pos.ffill().fillna(0.0)


def strat_bollinger(prices, events=None, n=20, k=2.0) -> pd.Series:
    """Bollinger-band reversion: fade moves outside the bands, flat inside."""
    c = prices["Close"].astype(float)
    ma, sd = c.rolling(n).mean(), c.rolling(n).std()
    pos = pd.Series(0.0, index=c.index)
    pos[c < ma - k * sd] = 1.0
    pos[c > ma + k * sd] = -1.0
    return pos


def strat_keltner_breakout(prices, events=None, n=20, mult=2.0) -> pd.Series:
    """Volatility (Keltner) breakout — long/short when price clears the EMA ± ATR
    channel; a classic momentum-ignition system."""
    c = prices["Close"].astype(float)
    mid, band = _ema(c, n), mult * _atr(prices, n)
    pos = pd.Series(np.nan, index=c.index)
    pos[c > mid + band] = 1.0
    pos[c < mid - band] = -1.0
    return pos.ffill().fillna(0.0)


def strat_momentum(prices, events=None, lb=90) -> pd.Series:
    """Time-series momentum: long if the trailing 90-day return is positive."""
    c = prices["Close"].astype(float)
    roc = c / c.shift(lb) - 1
    return pd.Series(np.where(roc > 0, 1.0, -1.0), index=c.index)


def strat_supertrend(prices, events=None, n=10, mult=3.0) -> pd.Series:
    """Supertrend(10,3) — the widely-used ATR trailing-stop trend system."""
    c = prices["Close"].astype(float)
    atr = _atr(prices, n)
    hl2 = (prices["High"] + prices["Low"]) / 2
    up, dn = hl2 - mult * atr, hl2 + mult * atr
    dir_ = pd.Series(1.0, index=c.index)
    fup, fdn = up.copy(), dn.copy()
    for i in range(1, len(c)):
        fup.iloc[i] = max(up.iloc[i], fup.iloc[i-1]) if c.iloc[i-1] > fup.iloc[i-1] else up.iloc[i]
        fdn.iloc[i] = min(dn.iloc[i], fdn.iloc[i-1]) if c.iloc[i-1] < fdn.iloc[i-1] else dn.iloc[i]
        dir_.iloc[i] = 1.0 if c.iloc[i] > fdn.iloc[i-1] else (-1.0 if c.iloc[i] < fup.iloc[i-1] else dir_.iloc[i-1])
    return dir_


def strat_seasonality(prices, events=None) -> pd.Series:
    """Calendar seasonality — long in months that have been positive on average,
    short in weak months. Bias is computed EXPANDING (only data strictly before
    each date) so there is no look-ahead."""
    c = prices["Close"].astype(float)
    df = pd.DataFrame({"ret": c.pct_change(), "m": c.index.month}, index=c.index)
    pos = []
    for i, dt in enumerate(c.index):
        past = df.iloc[:i]
        b = past.loc[past["m"] == dt.month, "ret"].mean()
        pos.append(1.0 if (b >= 0 or b != b) else -1.0)  # NaN (no history) -> long
    return pd.Series(pos, index=c.index)


STRATEGIES = {
    "Trend (20/50 MA)": strat_trend,
    "Donchian breakout (20/10)": strat_donchian,
    "MACD (12/26/9)": strat_macd,
    "Momentum (90d)": strat_momentum,
    "Keltner breakout (ATR)": strat_keltner_breakout,
    "Supertrend (10,3)": strat_supertrend,
    "RSI(2) mean-reversion": strat_rsi2,
    "Bollinger reversion": strat_bollinger,
    "Seasonality (month bias)": strat_seasonality,
    "Inventory/Event edge": strat_event,
    "Event + Trend filter": strat_event_plus_trend,
}


def bracket_trades(prices, positions, sl_mult=1.5, tgt_mult=3.0) -> list[dict]:
    """Turn a strategy's signals into a professional trade blotter: enter on the
    signal, place an ATR stop (1.5x) and target (3x), and exit on the FIRST of
    stop / target / signal-flip. Returns every trade with entry & exit price+date,
    the SL/target levels, exit reason, % return and R-multiple."""
    close = prices["Close"].astype(float)
    high, low = prices["High"].astype(float), prices["Low"].astype(float)
    atr = _atr(prices, 14)
    idx = close.index
    v = positions.reindex(idx).ffill().fillna(0.0).values
    n, i, trades = len(v), 0, []
    while i < n:
        side = v[i]
        if side == 0:
            i += 1
            continue
        entry = float(close.iloc[i])
        a = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else entry * 0.02
        if side > 0:
            sl, tgt = entry - sl_mult * a, entry + tgt_mult * a
        else:
            sl, tgt = entry + sl_mult * a, entry - tgt_mult * a
        j, reason, exitp = i + 1, None, entry
        while j < n:
            if v[j] != side:                       # signal flip / flat
                reason, exitp = "Signal", float(close.iloc[j]); break
            if side > 0:
                if low.iloc[j] <= sl: reason, exitp = "Stop", sl; break
                if high.iloc[j] >= tgt: reason, exitp = "Target", tgt; break
            else:
                if high.iloc[j] >= sl: reason, exitp = "Stop", sl; break
                if low.iloc[j] <= tgt: reason, exitp = "Target", tgt; break
            j += 1
        if reason is None:
            reason, exitp, j = "Open", float(close.iloc[-1]), n - 1
        ret = (exitp / entry - 1) * (1 if side > 0 else -1)
        risk = sl_mult * a / entry
        trades.append({
            "side": "Long" if side > 0 else "Short",
            "entry_date": idx[i].date().isoformat(), "entry": round(entry, 2),
            "sl": round(sl, 2), "target": round(tgt, 2),
            "exit_date": idx[j].date().isoformat(), "exit": round(exitp, 2),
            "reason": reason, "ret_pct": round(ret * 100, 2),
            "r_multiple": round(ret / risk, 2) if risk else 0.0,
            "hold_days": int(j - i),
        })
        if reason == "Signal":
            i = j                                  # flip point begins the next trade
        else:
            k = j + 1                              # after a bracket exit, wait for a fresh signal
            while k < n and v[k] == side:
                k += 1
            i = k
    return trades


def run_all(prices: pd.DataFrame, events: list[dict]) -> dict:
    out = {}
    for name, fn in STRATEGIES.items():
        try:
            pos = fn(prices, events)
            out[name] = backtest(prices, pos)
        except Exception as e:  # noqa: BLE001
            out[name] = {"error": str(e)}
    return out
