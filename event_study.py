"""Event-study engine: how did a commodity react around each event?

Given a price frame and a list of events (each with a date + a 'direction'
tag such as bearish/bullish), measure forward returns over several windows and
aggregate hit-rates and average moves by direction. This is the quantitative
answer to "what does crude/natgas/gold/silver historically do when the report
is out".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import STUDY_WINDOWS


def _t0_index(dates: pd.DatetimeIndex, event_date) -> int | None:
    """Index of the first trading day on/after the event date."""
    ts = pd.Timestamp(event_date)
    pos = dates.searchsorted(ts)
    return int(pos) if pos < len(dates) else None


def per_event_reactions(prices: pd.DataFrame, events: list[dict]) -> pd.DataFrame:
    """One row per event: forward % returns from t0 close over each window."""
    close = prices["Close"].astype(float)
    dates = close.index
    rows = []
    for ev in events:
        i = _t0_index(dates, ev["date"])
        if i is None or i >= len(close):
            continue
        base = close.iloc[i]
        rec = {
            "date": dates[i].date().isoformat(),
            "direction": ev.get("direction", "neutral"),
            "surprise": ev.get("surprise"),
            "actual": ev.get("actual"),
            "expected": ev.get("expected"),
        }
        for label, n in STUDY_WINDOWS:
            j = i + n
            rec[label] = (round(float(close.iloc[j] / base - 1) * 100, 2)
                          if j < len(close) and base else None)
        rows.append(rec)
    return pd.DataFrame(rows)


def summarise(reactions: pd.DataFrame, primary_window: str = "t+1") -> dict:
    """Aggregate by direction: count, avg move, hit-rate, over each window.

    hit-rate = share of events where the market moved the *expected* way for that
    direction (bearish -> down, bullish -> up) over the primary window.
    """
    out = {"by_direction": {}, "primary_window": primary_window, "n": int(len(reactions))}
    if reactions.empty:
        return out
    win_labels = [w for w, _ in STUDY_WINDOWS]
    for direction, grp in reactions.groupby("direction"):
        stats = {"count": int(len(grp))}
        for w in win_labels:
            vals = grp[w].dropna().astype(float)
            stats[w] = {
                "avg": round(float(vals.mean()), 2) if len(vals) else None,
                "median": round(float(vals.median()), 2) if len(vals) else None,
            }
        pw = grp[primary_window].dropna().astype(float)
        if len(pw):
            # hit-rate only has meaning for a directional call
            if direction == "bearish":
                stats["hit_rate"] = round(float((pw < 0).mean()) * 100, 1)
            elif direction == "bullish":
                stats["hit_rate"] = round(float((pw > 0).mean()) * 100, 1)
            else:
                stats["hit_rate"] = None
            stats["avg_abs"] = round(float(pw.abs().mean()), 2)
        out["by_direction"][direction] = stats
    return out


def study(prices: pd.DataFrame, events: list[dict], primary_window: str = "t+1") -> dict:
    reactions = per_event_reactions(prices, events)
    return {
        "summary": summarise(reactions, primary_window),
        "events": reactions.tail(30).to_dict("records"),  # most recent for display
    }
