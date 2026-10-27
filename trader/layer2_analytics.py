"""Layer 2 — portfolio analytics.

Looks at the book as a whole: NAV, allocation by name and sector, aggregate
Greeks, daily theta bleed, and the IV environment on every name held.
"""

from __future__ import annotations

import math
from collections import defaultdict


def realized_vol(closes: list[float], window: int = 30) -> float | None:
    if len(closes) < window + 1:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - window, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var * 252)


def iv_environment(valuation: dict, provider, history: list[dict]) -> dict:
    """Per ticker: front-ish ATM IV, 30d realized vol, IV/HV ratio and IV rank from our own snapshots."""
    env = {}
    for ticker, ch in valuation["chains"].items():
        # Use the first expiry with at least ~30 days left so weeklies don't distort it.
        atm = None
        for exp in ch["expiries"]:
            if exp >= valuation["as_of"] and ch["atm_iv"].get(exp):
                atm = ch["atm_iv"][exp]
                if (_days(valuation["as_of"], exp)) >= 30:
                    break
        hv = realized_vol(provider.history(ticker))
        past_iv = [_front(s["chains"][ticker]["atm_iv"], s["as_of"])
                   for s in history if ticker in s.get("chains", {})]
        past_iv = [x for x in past_iv if x]
        rank = None
        if atm is not None and len(past_iv) >= 5:
            lo, hi = min(past_iv + [atm]), max(past_iv + [atm])
            rank = (atm - lo) / (hi - lo) * 100 if hi > lo else 50.0
        env[ticker] = {
            "atm_iv": atm, "hv30": hv,
            "iv_hv": (atm / hv) if atm and hv else None,
            "iv_rank": rank, "iv_rank_days": len(past_iv),
            "label": _iv_label(atm, hv, rank),
        }
    return env


def _days(a: str, b: str) -> int:
    from datetime import date
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _front(atm_by_exp: dict, as_of: str):
    for exp in sorted(atm_by_exp):
        if exp >= as_of and atm_by_exp[exp] and _days(as_of, exp) >= 30:
            return atm_by_exp[exp]
    return None


def _iv_label(atm, hv, rank):
    if rank is not None:
        return "rich" if rank >= 70 else "cheap" if rank <= 30 else "fair"
    if atm and hv:
        ratio = atm / hv
        return "rich" if ratio >= 1.3 else "cheap" if ratio <= 0.9 else "fair"
    return "n/a"


def run(valuation: dict, portfolio: dict, provider, history: list[dict]) -> dict:
    positions = valuation["positions"]
    invested = sum(p["market_value"] for p in positions)
    nav = valuation["cash"] + invested
    start = portfolio.get("account", {}).get("starting_nav")

    by_ticker, by_sector = defaultdict(float), defaultdict(float)
    for p in positions:
        by_ticker[p["ticker"]] += p["market_value"]
        by_sector[p.get("sector", "Other")] += p["market_value"]
    by_sector["Cash"] += valuation["cash"]

    opts = [p for p in positions if p["type"] != "stock"]
    opt_value = sum(p["market_value"] for p in opts)
    theta = sum(p["theta_day"] for p in positions)
    totals = {
        "delta_dollars": sum(p["delta_dollars"] for p in positions),
        "gamma": sum(p["gamma"] for p in positions),
        "theta_day": theta,
        "vega": sum(p["vega"] for p in positions),
        "theta_pct_of_options": (theta / opt_value * 100) if opt_value else 0.0,
        "theta_30d": theta * 30,
    }
    max_pct = portfolio.get("settings", {}).get("max_position_pct", 25)
    concentration = [t for t, v in by_ticker.items() if nav and v / nav * 100 > max_pct]

    return {
        "nav": nav,
        "invested": invested,
        "cash": valuation["cash"],
        "starting_nav": start,
        "total_return_pct": ((nav / start - 1) * 100) if start else None,
        "pnl": sum(p["pnl"] for p in positions),
        "allocation_ticker": {t: v / nav * 100 for t, v in sorted(by_ticker.items(), key=lambda kv: -kv[1])},
        "allocation_sector": {s: v / nav * 100 for s, v in sorted(by_sector.items(), key=lambda kv: -kv[1])},
        "greeks": totals,
        "concentration": concentration,
        "iv_env": iv_environment(valuation, provider, history),
        "nav_curve": [(s["as_of"], s["nav"]) for s in history if s.get("nav")] + [(valuation["as_of"], nav)],
    }
