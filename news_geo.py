"""Commodity + geopolitical news, scored by Qwen for likely impact per commodity.

Pulls commodity/energy/geopolitics RSS, then a single LLM call tags each item
with the affected commodity and a bullish/bearish/neutral read + one-line why.
Fail-soft: without a key it returns the raw headlines (unscored).
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import re
import xml.etree.ElementTree as ET

import requests

import llm

FEEDS = [
    ("OilPrice", "https://oilprice.com/rss/main"),
    ("Reuters Commodities", "https://www.reutersagency.com/feed/?best-topics=commodities&post_type=best"),
    ("Investing Commodities", "https://www.investing.com/rss/news_11.rss"),
    ("Investing Economy", "https://www.investing.com/rss/news_14.rss"),
    ("ET Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Mining/Metals", "https://www.mining.com/feed/"),
]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def fetch_headlines(hours_back: int = 24, per_feed: int = 8) -> list[dict]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_back)
    items, seen = [], set()
    for name, url in FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:  # noqa: BLE001
            print(f"  news {name} failed: {e}")
            continue
        c = 0
        for it in root.iter("item"):
            title = _clean(it.findtext("title") or "")
            k = title[:80].lower()
            if not title or k in seen:
                continue
            seen.add(k)
            items.append({"source": name, "title": title,
                          "summary": _clean(it.findtext("description") or "")[:220],
                          "link": (it.findtext("link") or "").strip()})
            c += 1
            if c >= per_feed:
                break
    return items


SYSTEM = ("You are a 20-year commodity desk analyst. For each headline, decide "
          "which commodities it most affects (crude, natgas, gold, silver, or 'none') "
          "and the likely direction. Consider geopolitics (wars, sanctions, OPEC, "
          "supply routes), the USD/rates, and demand. Reply ONLY with a JSON array; "
          "one object per input item, same order: "
          '{"commodity":"crude|natgas|gold|silver|none","impact":"bullish|bearish|neutral",'
          '"why":"<=12 words"}. No invented facts.')


def analyse(headlines: list[dict]) -> list[dict]:
    """Attach commodity/impact/why to each headline (via Qwen). Fail-soft."""
    if not headlines:
        return []
    if not llm.has_key():
        return [{**h, "commodity": None, "impact": None, "why": ""} for h in headlines]
    listing = "\n".join(f"{i+1}. {h['title']}" for i, h in enumerate(headlines))
    scored = llm.json_call(SYSTEM, f"Headlines:\n{listing}", max_tokens=1600)
    out = []
    for i, h in enumerate(headlines):
        s = scored[i] if isinstance(scored, list) and i < len(scored) else {}
        out.append({**h, "commodity": (s or {}).get("commodity"),
                    "impact": (s or {}).get("impact"), "why": (s or {}).get("why", "")})
    return out


def by_commodity(scored: list[dict]) -> dict:
    """Group the market-relevant items under each commodity."""
    groups = {"crude": [], "natgas": [], "gold": [], "silver": []}
    for h in scored:
        c = h.get("commodity")
        if c in groups and h.get("impact") in ("bullish", "bearish"):
            groups[c].append(h)
    return groups
