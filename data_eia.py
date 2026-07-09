"""EIA weekly inventory → event list (with the surprise vs seasonal expectation).

Surprise = actual weekly change minus the same-calendar-week 5-year-average
change (a standard, no-cost proxy for consensus). A bigger-than-normal BUILD is
bearish for the commodity; a bigger-than-normal DRAW is bullish.

Needs EIA_API_KEY (free from https://www.eia.gov/opendata/). Without it, returns
an empty event list and the pipeline still runs (event studies just show 'no
inventory data').
"""
from __future__ import annotations

import os

import pandas as pd
import requests

from config import EIA_SERIES

EIA_V2 = "https://api.eia.gov/v2/seriesid/{sid}"


def _fetch_series(series_id: str) -> pd.Series:
    key = os.environ.get("EIA_API_KEY")
    if not key:
        print("  EIA_API_KEY not set — skipping inventory")
        return pd.Series(dtype=float)
    try:
        r = requests.get(EIA_V2.format(sid=series_id),
                         params={"api_key": key}, timeout=25)
        r.raise_for_status()
        rows = r.json()["response"]["data"]
    except Exception as e:  # noqa: BLE001
        print(f"  EIA {series_id} failed: {e}")
        return pd.Series(dtype=float)
    recs = {}
    for row in rows:
        per = row.get("period")
        val = row.get("value")
        if per is None or val is None:
            continue
        try:
            recs[pd.Timestamp(per)] = float(val)
        except (ValueError, TypeError):
            continue
    return pd.Series(recs).sort_index()


def _seasonal_expected_change(changes: pd.Series) -> pd.Series:
    """For each date, the mean weekly change of the same ISO week over the prior
    5 years (excluding the current observation) — the seasonal 'normal'."""
    df = pd.DataFrame({"chg": changes})
    df["week"] = df.index.isocalendar().week.astype(int)
    exp = pd.Series(index=changes.index, dtype=float)
    for dt, row in df.iterrows():
        hist = df[(df["week"] == row["week"]) & (df.index < dt)].tail(5)["chg"]
        exp[dt] = hist.mean() if len(hist) else 0.0
    return exp


def events_for(event_key: str, bearish_on: str = "build") -> list[dict]:
    """Return event dicts: date, actual, change, expected(seasonal), surprise, direction."""
    cfg = EIA_SERIES.get(event_key)
    if not cfg:
        return []
    stocks = _fetch_series(cfg["series_id"])
    if stocks.empty or len(stocks) < 60:
        return []
    change = stocks.diff()
    expected = _seasonal_expected_change(change)
    surprise = change - expected                    # >0 = bigger build than normal
    std = surprise.tail(104).std() or 1.0           # ~2y scale for thresholding
    events = []
    for dt in surprise.index:
        s = surprise[dt]
        if pd.isna(s):
            continue
        z = s / std
        if z > 0.4:
            direction = "bearish" if bearish_on == "build" else "bullish"
        elif z < -0.4:
            direction = "bullish" if bearish_on == "build" else "bearish"
        else:
            direction = "neutral"
        events.append({
            "date": dt.date(),
            "actual": round(float(stocks[dt]), 1),
            "change": round(float(change[dt]), 1) if not pd.isna(change[dt]) else None,
            "expected": round(float(expected[dt]), 1),
            "surprise": round(float(s), 1),
            "z": round(float(z), 2),
            "direction": direction,
        })
    return events


def latest_snapshot(event_key: str, bearish_on: str = "build") -> dict:
    evs = events_for(event_key, bearish_on)
    return evs[-1] if evs else {}
