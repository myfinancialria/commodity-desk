"""Macro-shock events for gold & silver.

Gold and silver have no weekly inventory print; their dominant driver is the US
dollar / real-rates (FOMC + CPI feed straight into the Dollar Index). So instead
of a hard-to-source FOMC/CPI calendar we derive events data-drivenly from large
Dollar-Index (DXY) moves: a sharp USD JUMP = 'hawkish' (bearish metals), a sharp
USD DROP = 'dovish' (bullish metals). Self-contained from the DXY price series.
"""
from __future__ import annotations

import pandas as pd


def dxy_shock_events(dxy: pd.DataFrame, z_threshold: float = 1.3) -> list[dict]:
    """Days where DXY's daily return is an outlier (|z| > threshold vs a rolling
    2-month window). Returns event dicts tagged bearish (USD up) / bullish (USD down)."""
    if dxy is None or dxy.empty or "Close" not in dxy:
        return []
    ret = dxy["Close"].astype(float).pct_change()
    vol = ret.rolling(42).std()
    z = ret / vol
    events = []
    for dt in z.index:
        zz = z[dt]
        if pd.isna(zz) or abs(zz) < z_threshold:
            continue
        # USD up sharply -> hawkish -> bearish for metals; USD down -> bullish
        direction = "bearish" if zz > 0 else "bullish"
        events.append({
            "date": dt.date(),
            "surprise": round(float(ret[dt] * 100), 2),   # DXY % move that day
            "z": round(float(zz), 2),
            "actual": round(float(dxy["Close"][dt]), 2),   # DXY level
            "expected": 0.0,
            "direction": direction,
            "driver": "USD/rates (DXY move)",
        })
    return events
