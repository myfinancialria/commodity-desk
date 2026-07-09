"""Daily OHLC history from Yahoo's public chart API (plain requests — no yfinance
dependency, more robust in CI). Returns a date-indexed DataFrame per symbol.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from config import COMMODITIES, HISTORY_YEARS

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
CHART_HOSTS = ["https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
               "https://query2.finance.yahoo.com/v8/finance/chart/{sym}"]
DXY = "DX-Y.NYB"
COLS = ["Open", "High", "Low", "Close", "Volume"]


def _via_yfinance(symbol: str, years: int) -> pd.DataFrame:
    """Primary source — yfinance does Yahoo's cookie+crumb handshake, so it gets
    past the datacenter-IP rate-limiting that blocks the raw chart endpoint."""
    import yfinance as yf
    h = yf.Ticker(symbol).history(period=f"{years}y", auto_adjust=False)
    if h is None or h.empty:
        return pd.DataFrame(columns=COLS)
    df = h[[c for c in COLS if c in h.columns]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df.dropna(subset=["Close"])


def _via_chart(symbol: str, years: int) -> pd.DataFrame:
    """Fallback — raw chart API (query1/query2)."""
    params = {"range": f"{years}y", "interval": "1d", "includePrePost": "false"}
    for attempt in range(2):
        host = CHART_HOSTS[attempt % len(CHART_HOSTS)]
        r = requests.get(host.format(sym=symbol), params=params, headers=UA, timeout=20)
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        df = pd.DataFrame({"Open": q.get("open"), "High": q.get("high"),
                           "Low": q.get("low"), "Close": q.get("close"),
                           "Volume": q.get("volume")},
                          index=pd.to_datetime(res["timestamp"], unit="s").normalize())
        df.index.name = "date"
        return df.dropna(subset=["Close"])
    return pd.DataFrame(columns=COLS)


def fetch_ohlc(symbol: str, years: int = HISTORY_YEARS) -> pd.DataFrame:
    for name, fn in (("yfinance", _via_yfinance), ("chart", _via_chart)):
        try:
            df = fn(symbol, years)
            if not df.empty:
                return df
            print(f"  {symbol} via {name}: empty")
        except Exception as e:  # noqa: BLE001
            print(f"  {symbol} via {name} failed: {e}")
        time.sleep(1)
    return pd.DataFrame(columns=COLS)


def fetch_all() -> dict[str, pd.DataFrame]:
    """{key: prices} for every commodity, plus 'dxy' (US Dollar Index)."""
    out = {}
    for key, cfg in COMMODITIES.items():
        print(f"[prices] {cfg['name']} ({cfg['yf']})...")
        out[key] = fetch_ohlc(cfg["yf"])
        time.sleep(0.4)
    print(f"[prices] Dollar Index ({DXY})...")
    out["dxy"] = fetch_ohlc(DXY)
    return out
