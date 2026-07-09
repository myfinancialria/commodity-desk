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


def fetch_ohlc(symbol: str, years: int = HISTORY_YEARS) -> pd.DataFrame:
    params = {"range": f"{years}y", "interval": "1d", "includePrePost": "false"}
    # try each host with retries; hosts rate-limit independently
    for attempt in range(4):
        host = CHART_HOSTS[attempt % len(CHART_HOSTS)]
        try:
            r = requests.get(host.format(sym=symbol), params=params,
                             headers=UA, timeout=20)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            df = pd.DataFrame({
                "Open": q.get("open"), "High": q.get("high"),
                "Low": q.get("low"), "Close": q.get("close"),
                "Volume": q.get("volume"),
            }, index=pd.to_datetime(ts, unit="s").normalize())
            df = df.dropna(subset=["Close"])
            df.index.name = "date"
            return df
        except Exception as e:  # noqa: BLE001
            print(f"  yahoo {symbol} attempt {attempt+1} failed: {e}")
            time.sleep(2 * (attempt + 1))
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


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
