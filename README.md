# Commodity Desk

A daily, auto-updated **commodity research desk** for crude oil, natural gas, gold
and silver — built to think like a 20-year analyst: inventories, positioning,
geopolitics and the dollar.

**Live dashboard:** `https://<owner>.github.io/commodity-desk/` (GitHub Pages)

## What it does, every weekday

1. **Prices** — 12 years of daily OHLC for WTI (`CL=F`), NatGas (`NG=F`), Gold
   (`GC=F`), Silver (`SI=F`) and the Dollar Index, from Yahoo's public API.
2. **Events**
   - Crude & NatGas → **US EIA weekly inventory** (crude stocks Wed, gas storage
     Thu). The *surprise* = actual weekly change minus the same-week 5-year-average
     change (a no-cost consensus proxy). A bigger-than-normal build is bearish.
   - Gold & Silver → **USD/rates shocks**: outlier daily moves in the Dollar Index
     (a sharp USD jump = hawkish/bearish metals; a drop = dovish/bullish).
3. **Event-studies** — for every historical release, how the market moved over
   t0/t+1/t+3/t+5, aggregated by surprise direction into **hit-rates and average
   moves**. This is "what crude/gas/gold/silver historically does when the report
   is out".
4. **Backtests** — three strategies per commodity (trend, the inventory/event
   edge, event+trend filter), each run through a vectorised backtester with a
   1-day execution lag and a small fee → CAGR, Sharpe, max drawdown, win-rate,
   trades and an equity curve. **Nothing goes live before it's backtested.**
5. **News & geopolitics** — commodity/energy/geopolitics RSS, scored by **Qwen**
   for the affected commodity + bullish/bearish read.
6. **Live signals** — a per-commodity verdict (Bullish/Bearish/Neutral) that
   *combines* the current trend, the latest event edge and the news tilt, with
   ATR-based reference/stop/target and the backtested strategy it leans on.
7. **Desk note** — a veteran-analyst write-up drafted by **Qwen + Llama** (both
   draft, then merge) grounded in all of the above.

Output is a self-contained static dashboard in `docs/` (Signals · Event Studies ·
Backtests · News & Geopolitics · Desk Note), deployed to GitHub Pages.

## Setup

Repository **secrets** (Settings → Secrets and variables → Actions):

| Secret | Needed for | Get it |
|---|---|---|
| `EIA_API_KEY` | crude/natgas inventory event-studies | free at https://www.eia.gov/opendata/ |
| `OPENROUTER_API_KEY` | Qwen+Llama news scoring + desk note | https://openrouter.ai |

Both are optional — without a key the relevant section degrades to "unavailable"
and the rest of the dashboard still builds. Then enable **Pages** (Deploy from
GitHub Actions) and run the **Commodity Desk — daily** workflow.

## Run locally
```bash
pip install -r requirements.txt
EIA_API_KEY=... OPENROUTER_API_KEY=... python run.py
open docs/index.html
```

## Layout
```
config.py         instruments, EIA series, event/study config
data_prices.py    Yahoo daily OHLC (+ Dollar Index)
data_eia.py       EIA inventory -> events with seasonal surprise
data_events.py    USD-shock events for gold/silver
event_study.py    reaction stats around events
backtest.py       vectorised backtester + strategy library
news_geo.py       RSS + Qwen impact scoring
signals.py        live signal per commodity
narrative.py      Qwen+Llama veteran desk note
build_dashboard.py static docs/ dashboard
run.py            daily orchestrator
```

## Disclaimer
Educational / research only — **not investment advice**. Event-studies and
backtests are hypothetical, use simple assumptions, and past reactions to reports
need not repeat. Manage your own risk.
