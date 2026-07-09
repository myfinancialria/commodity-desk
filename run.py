"""Commodity Desk — daily orchestrator.

prices -> events (EIA inventory for crude/natgas, USD shocks for gold/silver)
       -> event-studies -> backtests -> news/geopolitics (Qwen) -> live signals
       -> veteran desk note (Qwen+Llama) -> docs/data.json + docs/index.html
Every external call is fail-soft; a down source degrades that section, not the run.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import build_dashboard
import backtest
import data_eia
import data_events
import data_fyers
import data_prices
import event_study
import narrative
import news_geo
import signals
import pandas as pd
from config import COMMODITIES, BACKTEST_YEARS

HERE = Path(__file__).parent
DOCS = HERE / "docs"


def events_for(key: str, cfg: dict, prices: dict) -> list[dict]:
    if cfg["event"] in ("eia_crude", "eia_natgas"):
        return data_eia.events_for(cfg["event"], cfg["bearish_on"])
    if cfg["event"] == "macro":
        return data_events.dxy_shock_events(prices.get("dxy"))
    return []


def main() -> int:
    today = dt.date.today().isoformat()
    print("=== Commodity Desk run:", today, "===")
    prices = data_prices.fetch_all()

    print("[news] fetching + scoring headlines...")
    scored = news_geo.analyse(news_geo.fetch_headlines())
    news_by = news_geo.by_commodity(scored)

    print("[fyers] live MCX (Indian) prices...")
    mcx = data_fyers.fetch_mcx_prices()   # {} if Fyers not configured

    commodities, sig_list = {}, []
    for key, cfg in COMMODITIES.items():
        px = prices.get(key)
        print(f"[{key}] events + study + backtest...")
        events = events_for(key, cfg, prices)
        study = event_study.study(px, events) if px is not None and not px.empty else {"summary": {"by_direction": {}}, "events": []}
        # backtests run over the recent BACKTEST_YEARS window; studies use all history
        if px is not None and not px.empty:
            cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=BACKTEST_YEARS)
            bt_px = px[px.index >= cutoff]
            bts = backtest.run_all(bt_px, events)
        else:
            bts = {}
        sig = signals.build(key, cfg, px, events, study, bts, news_by.get(key, []))
        sig["mcx"] = mcx.get(key)          # live Indian ₹ price (or None)
        sig_list.append(sig)
        commodities[key] = {
            "name": cfg["name"], "unit": cfg["unit"], "event": cfg["event"],
            "n_events": len(events),
            "study": study, "backtests": bts,
            "news": news_by.get(key, []),
            "signal": sig,
        }

    payload = {
        "as_of": today,
        "generated_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "commodities": commodities,
        "signals": sig_list,
        "news_all": scored[:40],
    }
    print("[narrative] writing veteran desk note...")
    payload["desk_note"] = narrative.write(payload)

    DOCS.mkdir(exist_ok=True)
    (DOCS / "data.json").write_text(json.dumps(payload, indent=2, default=str))
    build_dashboard.build(payload, DOCS)
    (DOCS / ".nojekyll").write_text("")
    print("Wrote", DOCS / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
