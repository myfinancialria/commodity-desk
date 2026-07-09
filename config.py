"""Commodity Desk — central config: instruments, EIA series, event types.

One place that every module reads, so adding a commodity or an event is a
single-line change.
"""
from __future__ import annotations

# Yahoo Finance continuous-front-month futures symbols.
COMMODITIES = {
    "crude": {
        "name": "WTI Crude Oil",
        "yf": "CL=F",
        "unit": "$/bbl",
        "event": "eia_crude",            # weekly EIA crude-stock report
        "bearish_on": "build",           # a bigger-than-expected build is bearish
    },
    "natgas": {
        "name": "Natural Gas",
        "yf": "NG=F",
        "unit": "$/MMBtu",
        "event": "eia_natgas",           # weekly EIA natural-gas storage report
        "bearish_on": "build",
    },
    "gold": {
        "name": "Gold",
        "yf": "GC=F",
        "unit": "$/oz",
        "event": "macro",                # FOMC + US CPI drive gold
        "bearish_on": "hawkish",
    },
    "silver": {
        "name": "Silver",
        "yf": "SI=F",
        "unit": "$/oz",
        "event": "macro",
        "bearish_on": "hawkish",
    },
}

# EIA Open Data API v2 series (weekly).
# Crude: Weekly Ending Stocks of Crude Oil (thousand barrels).
# NatGas: Weekly Lower-48 Working Gas in Underground Storage (Bcf).
EIA_SERIES = {
    "eia_crude": {
        "series_id": "PET.WCESTUS1.W",
        "label": "US crude oil stocks",
        "unit": "kbbl",
        "release_weekday": 2,   # Wednesday (0=Mon) — actual print time 10:30 ET
    },
    "eia_natgas": {
        "series_id": "NG.NW2_EPG0_SWO_R48_BCF.W",
        "label": "US working gas in storage",
        "unit": "Bcf",
        "release_weekday": 3,   # Thursday
    },
}

# Surprise = actual weekly change minus the expectation. With no paid consensus
# feed, the expectation is the same-calendar-week 5-year average change (a
# standard, defensible proxy). Configurable so a real consensus can drop in.
EXPECTATION_MODE = "seasonal_5y"   # or "prior_avg"

# Event-study windows (trading days relative to the release day t0).
STUDY_WINDOWS = [("t0", 0), ("t+1", 1), ("t+3", 3), ("t+5", 5)]

# How far back to pull price + inventory history.
HISTORY_YEARS = 12

DASH_TITLE = "Commodity Desk — Inventory, Backtests & Signals"
