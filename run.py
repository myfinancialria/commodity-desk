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


def _add_inr_levels(sig: dict) -> None:
    """Convert the entry/stop/target from the international price into MCX ₹ using
    the live ₹/international ratio (only when the Fyers MCX price is available)."""
    m, last, L = sig.get("mcx"), sig.get("last"), sig.get("levels", {})
    if not m or not last or not L.get("entry"):
        return
    r = m["lp"] / last
    sig["levels_inr"] = {"unit": m["unit"],
                          "entry": round(L["entry"] * r, 2),
                          "stop": round(L["stop"] * r, 2) if L.get("stop") else None,
                          "target": round(L["target"] * r, 2) if L.get("target") else None}


def _successful_strategies(commodities: dict) -> list[dict]:
    """Rank strategies by their average Sharpe across the four commodities."""
    agg = {}
    for c in commodities.values():
        for name, b in (c.get("backtests") or {}).items():
            if "error" in b:
                continue
            a = agg.setdefault(name, {"sharpe": [], "cagr": [], "win": []})
            a["sharpe"].append(b.get("sharpe", 0))
            a["cagr"].append(b.get("cagr_pct", 0))
            a["win"].append(b.get("trade_win_rate_pct", 0))
    out = []
    for name, a in agg.items():
        n = len(a["sharpe"]) or 1
        out.append({"strategy": name,
                    "avg_sharpe": round(sum(a["sharpe"]) / n, 2),
                    "avg_cagr": round(sum(a["cagr"]) / n, 1),
                    "avg_win": round(sum(a["win"]) / n, 1)})
    return sorted(out, key=lambda x: x["avg_sharpe"], reverse=True)


HOW_TO = """
### How to take a trade from this desk
1. **Start with the signal.** Each commodity shows a **Bullish / Bearish / Neutral**
   verdict and a *conviction* (how many of trend, the inventory/USD event edge and
   the news agree). Trade only the higher-conviction (2–3/3) setups; skip Neutral.
2. **Use the levels.** The card gives a **reference entry, stop-loss (SL) and target**
   — in ₹ on MCX when the Fyers price is live, otherwise on the international price.
   The SL is 1.5×ATR from entry; the target is 3×ATR (a ~2:1 reward:risk).
3. **Size by risk, not by lots.** Risk a fixed **1–2% of capital per trade**.
   Quantity = (risk amount) ÷ (entry − SL distance). Never widen the stop.
4. **Enter on confirmation** (a close in the signal's direction), place the SL and
   target as a bracket, and let it run. Exit if the SL or target hits, or if the
   signal flips.
5. **Respect the report days.** Crude reacts to the Wed EIA inventory, gas to Thu
   storage, metals to USD/rate shocks — the Event-Studies tab shows how the market
   has historically moved, so avoid fresh entries into a print you can't stomach.
6. **Lean on what has edge.** The Backtests + Trade History tabs show which
   strategies actually worked over 3 years — prefer signals aligned with those.

*Educational only — not advice. Backtests are hypothetical; manage your own risk.*
"""


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
        trade_history = {}
        if px is not None and not px.empty:
            cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=BACKTEST_YEARS)
            bt_px = px[px.index >= cutoff]
            bts = backtest.run_all(bt_px, events)
            # full trade blotter for the best (highest-Sharpe) strategy
            ok = {n: b for n, b in bts.items() if "error" not in b and b.get("num_trades")}
            if ok:
                best = max(ok, key=lambda n: ok[n].get("sharpe", -9))
                pos = backtest.STRATEGIES[best](bt_px, events)
                trade_history = {"strategy": best,
                                  "trades": backtest.bracket_trades(bt_px, pos)}
        else:
            bts = {}
        sig = signals.build(key, cfg, px, events, study, bts, news_by.get(key, []))
        sig["mcx"] = mcx.get(key)          # live Indian ₹ price (or None)
        _add_inr_levels(sig)               # entry/SL/target in ₹ when MCX is live
        sig_list.append(sig)
        commodities[key] = {
            "name": cfg["name"], "unit": cfg["unit"], "event": cfg["event"],
            "n_events": len(events),
            "study": study, "backtests": bts, "trade_history": trade_history,
            "news": news_by.get(key, []),
            "signal": sig,
        }

    payload = {
        "as_of": today,
        "generated_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "commodities": commodities,
        "signals": sig_list,
        "news_all": scored[:40],
        "successful_strategies": _successful_strategies(commodities),
        "how_to": HOW_TO,
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
