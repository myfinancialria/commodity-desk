"""The veteran-analyst desk note — Qwen + Llama draft it from the assembled facts,
then merge. Fail-soft: no key -> a plain rule-based summary so the page is never
empty.
"""
from __future__ import annotations

import json

import llm

SYSTEM = (
    "You are a commodity research analyst with 20+ years on the desk — crude, "
    "natural gas, gold and silver. You think in terms of inventories, positioning, "
    "geopolitics and the dollar. Write a crisp DESK NOTE for traders in plain "
    "English. Ground every claim in the DATA provided (event-study hit-rates, "
    "backtest stats, the latest inventory/USD surprise, the news). Give a clear "
    "lean per commodity and the key level/risk. Be honest about low-conviction "
    "setups. NEVER invent a number or a headline. This is educational, not advice."
)

TEMPLATE = """Write the desk note in this structure (Markdown):

## Desk view — <date>
2-3 sentences on the overall commodity tape (risk-on/off, USD, oil vs metals).

Then for EACH commodity (Crude, Natural Gas, Gold, Silver) a short block:
### <Commodity> — <Bullish/Bearish/Neutral>
- What the latest report/surprise said and what the market historically does then
  (use the hit-rate + average move).
- The current trend and the level that matters.
- The one geopolitical/macro item that could move it.
- The backtested strategy it leans on and that strategy's edge (CAGR/Sharpe/win-rate).

End with **Risk & caveats** (2 lines): backtests are hypothetical, past reactions
need not repeat, manage risk.

DATA (JSON):
"""


def write(payload: dict) -> str:
    compact = json.dumps(payload, default=str)[:12000]
    note = llm.dual(SYSTEM, TEMPLATE + compact, max_tokens=2200)
    return note or _fallback(payload)


def _fallback(payload: dict) -> str:
    lines = [f"## Desk view — {payload.get('as_of','')}",
             "_AI note unavailable (set OPENROUTER_API_KEY). Rule-based summary:_", ""]
    for sig in payload.get("signals", []):
        if not sig.get("available"):
            continue
        e = sig.get("event_edge", {})
        lines.append(f"### {sig['name']} — {sig['verdict']}")
        lines.append(f"- Last {sig['last']} {sig.get('unit','')}, trend {sig['trend']}. "
                     f"{sig.get('rationale','')}")
        if e.get("hit_rate"):
            lines.append(f"- Latest report skews **{e['direction']}** — historically "
                         f"{e['hit_rate']}% hit-rate over {e.get('count','?')} such events.")
        s = sig.get("leans_on_stats", {})
        if sig.get("leans_on_strategy"):
            lines.append(f"- Leans on **{sig['leans_on_strategy']}** "
                         f"(CAGR {s.get('cagr_pct')}%, Sharpe {s.get('sharpe')}, "
                         f"win-rate {s.get('trade_win_rate_pct')}%).")
        lines.append("")
    lines.append("**Risk & caveats:** backtests are hypothetical and past reactions "
                 "need not repeat. Educational only — manage your own risk.")
    return "\n".join(lines)
