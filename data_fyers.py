"""Live MCX (Indian market) front-month futures prices via Fyers — the ₹ overlay
on the signals. Fail-soft: no token / not logged in -> returns {} and the
dashboard just shows the international price.

Run auto_login.py first (writes access_token.txt). MCX has no clean continuous
3-year history on Fyers (monthly contracts), so backtests use the international
continuous series that MCX tracks; this module supplies the live ₹ level.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
TOKEN = HERE / "access_token.txt"

# MCX base symbols + quote unit + which months list contracts (crude/natgas are
# monthly; gold on even months; silver Mar/May/Jul/Sep/Dec).
MCX = {
    "crude":  {"base": "CRUDEOIL",   "unit": "₹/bbl",  "months": "all"},
    "natgas": {"base": "NATURALGAS", "unit": "₹/MMBtu", "months": "all"},
    "gold":   {"base": "GOLD",       "unit": "₹/10g",  "months": [2, 4, 6, 8, 10, 12]},
    "silver": {"base": "SILVER",     "unit": "₹/kg",   "months": [3, 5, 7, 9, 12]},
}
_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
        "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _client():
    if not TOKEN.exists():
        print("  Fyers: access_token.txt missing (run auto_login.py) — skipping MCX")
        return None
    cid = os.environ.get("FYERS_CLIENT_ID")
    if not cid:
        return None
    try:
        from fyers_apiv3 import fyersModel
        return fyersModel.FyersModel(client_id=cid, token=TOKEN.read_text().strip(), log_path="")
    except Exception as e:  # noqa: BLE001
        print(f"  Fyers client failed: {e}")
        return None


def _candidate_symbols(cfg: dict, today: dt.date) -> list[str]:
    """Chronological front-month candidates for the next ~4 valid contract months."""
    out, y, m = [], today.year, today.month
    for _ in range(8):
        if cfg["months"] == "all" or m in cfg["months"]:
            out.append(f"MCX:{cfg['base']}{y % 100:02d}{_MON[m-1]}FUT")
        m += 1
        if m > 12:
            m, y = 1, y + 1
        if len(out) >= 4:
            break
    return out


def fetch_mcx_prices() -> dict:
    fy = _client()
    if fy is None:
        return {}
    today = dt.date.today()
    all_syms, owner = [], {}
    for key, cfg in MCX.items():
        for s in _candidate_symbols(cfg, today):
            all_syms.append(s)
            owner[s] = key
    try:
        resp = fy.quotes(data={"symbols": ",".join(all_syms)})
    except Exception as e:  # noqa: BLE001
        print(f"  Fyers MCX quotes failed: {e}")
        return {}
    if resp.get("s") != "ok":
        return {}
    # pick the first (nearest-expiry) contract per commodity that has a live price
    out: dict[str, dict] = {}
    for item in resp.get("d", []):
        sym = item.get("n", "")
        v = item.get("v") or {}
        key = owner.get(sym)
        if not key or key in out or not v.get("lp"):
            continue
        out[key] = {"symbol": sym, "unit": MCX[key]["unit"],
                    "lp": round(float(v.get("lp")), 2),
                    "chp": round(float(v.get("chp") or 0), 2)}
    if out:
        print(f"  MCX live: {', '.join(f'{k} {out[k]['lp']}' for k in out)}")
    return out
