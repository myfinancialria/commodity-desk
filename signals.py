"""Live signal per commodity — grounded in the backtested edge, current trend,
the latest event surprise and the news tilt. Every signal carries the stats it
leans on, so nothing is a black box.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _trend(prices: pd.DataFrame):
    c = prices["Close"].astype(float)
    if len(c) < 55:
        return "flat", None, None
    ma20, ma50 = c.rolling(20).mean().iloc[-1], c.rolling(50).mean().iloc[-1]
    last = float(c.iloc[-1])
    state = "up" if ma20 > ma50 else "down"
    return state, round(float(ma20), 2), round(float(ma50), 2)


def _atr_levels(prices: pd.DataFrame, side: str):
    """Suggested stop/target from ATR(14) — risk framing, not advice."""
    d = prices.tail(60)
    if len(d) < 15:
        return None, None, None
    hl = d["High"] - d["Low"]
    hc = (d["High"] - d["Close"].shift()).abs()
    lc = (d["Low"] - d["Close"].shift()).abs()
    atr = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean().iloc[-1]
    px = float(d["Close"].iloc[-1])
    if side == "long":
        return round(px, 2), round(px - 1.5 * atr, 2), round(px + 3 * atr, 2)
    if side == "short":
        return round(px, 2), round(px + 1.5 * atr, 2), round(px - 3 * atr, 2)
    return round(px, 2), None, None


def build(key: str, cfg: dict, prices: pd.DataFrame, events: list[dict],
          study: dict, backtests: dict, news: list[dict]) -> dict:
    if prices is None or prices.empty:
        return {"key": key, "name": cfg["name"], "available": False}

    trend_state, ma20, ma50 = _trend(prices)
    last = float(prices["Close"].iloc[-1])

    # latest event + what the study says about that kind of event
    latest_ev = events[-1] if events else {}
    ev_dir = latest_ev.get("direction", "neutral")
    by_dir = (study or {}).get("summary", {}).get("by_direction", {})
    ev_stat = by_dir.get(ev_dir, {})
    ev_edge_ok = ev_dir in ("bearish", "bullish") and (ev_stat.get("hit_rate") or 0) >= 55

    # news tilt for this commodity
    n_bull = sum(1 for h in news if h.get("impact") == "bullish")
    n_bear = sum(1 for h in news if h.get("impact") == "bearish")
    news_tilt = "bullish" if n_bull > n_bear else ("bearish" if n_bear > n_bull else "neutral")

    # combine votes: trend + event edge + news
    votes = []
    votes.append(1 if trend_state == "up" else -1)
    if ev_edge_ok:
        votes.append(1 if ev_dir == "bullish" else -1)
    if news_tilt != "neutral":
        votes.append(1 if news_tilt == "bullish" else -1)
    score = sum(votes)
    if score >= 2:
        verdict, side = "Bullish", "long"
    elif score <= -2:
        verdict, side = "Bearish", "short"
    else:
        verdict, side = "Neutral", "flat"

    entry, stop, target = _atr_levels(prices, side)
    best_bt = max(
        ((n, b) for n, b in (backtests or {}).items() if "error" not in b),
        key=lambda kv: kv[1].get("sharpe", -9), default=(None, {}))

    return {
        "key": key, "name": cfg["name"], "unit": cfg["unit"], "available": True,
        "last": round(last, 2),
        "verdict": verdict, "conviction": abs(score),
        "trend": trend_state, "ma20": ma20, "ma50": ma50,
        "latest_event": latest_ev,
        "event_edge": {"direction": ev_dir, **{k: ev_stat.get(k) for k in ("hit_rate", "count")},
                        "t+1": ev_stat.get("t+1", {})},
        "news_tilt": news_tilt, "news_counts": {"bullish": n_bull, "bearish": n_bear},
        "levels": {"entry": entry, "stop": stop, "target": target},
        "leans_on_strategy": best_bt[0],
        "leans_on_stats": {k: best_bt[1].get(k) for k in
                            ("cagr_pct", "sharpe", "max_drawdown_pct", "trade_win_rate_pct")},
        "rationale": _rationale(verdict, trend_state, ev_dir, ev_edge_ok, news_tilt),
    }


def _rationale(verdict, trend, ev_dir, ev_ok, news_tilt) -> str:
    bits = [f"trend is {trend}"]
    if ev_ok:
        bits.append(f"latest report skews {ev_dir} and that has an edge historically")
    if news_tilt != "neutral":
        bits.append(f"news flow leans {news_tilt}")
    return f"{verdict}: " + "; ".join(bits) + "."
