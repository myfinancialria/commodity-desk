"""Qwen + Llama via OpenRouter — a single-model call and a 'both draft, then
merge' call for the flagship analyst write-up. No key -> returns None/empty and
the pipeline degrades gracefully.
"""
from __future__ import annotations

import json
import os

import requests

BASE = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
QWEN = os.environ.get("QWEN_MODEL", "qwen/qwen-2.5-72b-instruct")
LLAMA = os.environ.get("LLAMA_MODEL", "meta-llama/llama-3.3-70b-instruct")
MERGE = os.environ.get("MERGE_MODEL", QWEN)


def _chat(model, system, user, *, temperature=0.4, max_tokens=1500, timeout=120):
    r = requests.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://myfinancialria.github.io/commodity-desk/",
                 "X-Title": "Commodity Desk"},
        json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}]},
        timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def _safe(model, system, user, **kw):
    try:
        return _chat(model, system, user, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  OpenRouter {model} failed: {e}")
        return ""


def has_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def qwen(system, user, **kw) -> str:
    return _safe(QWEN, system, user, **kw) if has_key() else ""


def dual(system, user, **kw) -> str:
    """Qwen and Llama each draft, then merge into one — the veteran write-up."""
    if not has_key():
        return ""
    dq = _safe(QWEN, system, user, **kw)
    dl = _safe(LLAMA, system, user, **kw)
    if not dq and not dl:
        return ""
    if not dq:
        return dl
    if not dl:
        return dq
    merge_user = ("Two veteran commodity analysts independently wrote the note "
                  "below from the SAME data. Merge into ONE tight, punchy note — "
                  "keep every specific, correct point, drop repetition, no invented "
                  f"numbers.\n\n=== ANALYST A (Qwen) ===\n{dq}\n\n=== ANALYST B (Llama) ===\n{dl}")
    return _safe(MERGE, system, merge_user, **kw) or (dq if len(dq) >= len(dl) else dl)


def json_call(system, user, **kw):
    """Single Qwen call expected to return JSON; parsed leniently."""
    txt = qwen(system, user, **kw)
    if not txt:
        return None
    m = txt.find("["); n = txt.rfind("]")
    if m < 0:
        m = txt.find("{"); n = txt.rfind("}")
    try:
        return json.loads(txt[m:n + 1]) if m >= 0 else json.loads(txt)
    except Exception:  # noqa: BLE001
        return None
