"""Layer 1 — data and valuation.

Pulls spot and the option chain for every name in the book, matches each held
contract, computes Greeks locally, values every position (P&L, progress to
target/stop) and saves a daily snapshot. Later layers diff snapshots to spot new
strikes, new expiries and IV moves.
"""

from __future__ import annotations

import json
import os
from datetime import date

from .greeks import greeks, implied_vol

CONTRACT = 100  # shares per option contract


def _mid(row) -> float:
    if row["bid"] > 0 and row["ask"] > 0:
        return (row["bid"] + row["ask"]) / 2
    return row["last"]


def _atm_iv(chain, spot, kind="call"):
    rows = [r for r in chain if r["kind"] == kind and r["iv"] > 0]
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r["strike"] - spot))["iv"]


def value_position(pos: dict, provider, as_of: date, r: float, cache: dict) -> dict:
    ticker = pos["ticker"]
    spot = cache.setdefault(("spot", ticker), provider.spot(ticker))
    out = dict(pos, spot=spot)

    if pos["type"] == "stock":
        price = spot
        out.update(price=price, market_value=price * pos["qty"],
                   delta_dollars=price * pos["qty"], gamma=0.0, theta_day=0.0, vega=0.0,
                   iv=None, dte=None, delta=1.0, quote=None)
        cost = pos["cost_basis"] * pos["qty"]
    else:
        expiry, kind = pos["expiry"], pos["type"]
        key = ("chain", ticker, expiry)
        if key not in cache:
            cache[key] = provider.chain(ticker, expiry)
        chain = cache[key]
        row = next((c for c in chain if c["kind"] == kind and abs(c["strike"] - pos["strike"]) < 1e-6), None)
        if row is None:
            raise ValueError(f"{pos['id']}: contract not found in {ticker} {expiry} chain")
        dte = (date.fromisoformat(expiry) - as_of).days
        t = max(dte, 0) / 365
        price = _mid(row)
        # Yahoo's per-contract IV is noisy; re-solve from the mid and fall back to the quote.
        iv = implied_vol(kind, price, spot, pos["strike"], t, r) or row["iv"] or 0.0
        g = greeks(kind, spot, pos["strike"], t, r, iv)
        n = pos["qty"] * CONTRACT
        out.update(
            price=price, market_value=price * n, dte=dte, iv=iv, quote=row,
            delta=g["delta"], gamma=g["gamma"] * n, theta_day=g["theta"] * n, vega=g["vega"] * n,
            delta_dollars=g["delta"] * spot * n,
        )
        cost = pos["cost_basis"] * n

    pnl = out["market_value"] - cost
    pnl_pct = pnl / cost * 100 if cost else 0.0
    target, stop = pos.get("target_pct"), pos.get("stop_pct")
    out.update(
        cost=cost, pnl=pnl, pnl_pct=pnl_pct,
        to_target=(pnl_pct / target * 100) if target else None,
        target_hit=bool(target is not None and pnl_pct >= target),
        stop_hit=bool(stop is not None and pnl_pct <= stop),
    )
    if pos.get("underlying_target"):
        out["underlying_target_hit"] = spot >= pos["underlying_target"]
    return out


def chain_summary(provider, tickers, cache) -> dict:
    """Per ticker: expiries, strikes per expiry and front ATM IV — the diffable part of the chain."""
    summary = {}
    for ticker in tickers:
        spot = cache.setdefault(("spot", ticker), provider.spot(ticker))
        exps = provider.expiries(ticker)
        strikes, atm = {}, {}
        for exp in exps:
            key = ("chain", ticker, exp)
            if key not in cache:
                cache[key] = provider.chain(ticker, exp)
            chain = cache[key]
            strikes[exp] = sorted({c["strike"] for c in chain})
            atm[exp] = _atm_iv(chain, spot)
        summary[ticker] = {"spot": spot, "expiries": exps, "strikes": strikes, "atm_iv": atm}
    return summary


def run(portfolio: dict, provider, as_of: date) -> dict:
    r = portfolio.get("settings", {}).get("risk_free_rate", 0.04)
    cache: dict = {}
    positions = [value_position(p, provider, as_of, r, cache) for p in portfolio["positions"]]
    tickers = sorted({p["ticker"] for p in portfolio["positions"]} | set(portfolio.get("watch", [])))
    return {
        "as_of": as_of.isoformat(),
        "positions": positions,
        "chains": chain_summary(provider, tickers, cache),
        "ladders": {p["id"]: strike_ladder(p, cache[("chain", p["ticker"], p["expiry"])])
                    for p in positions if p["type"] != "stock"},
        "cash": portfolio.get("account", {}).get("cash", 0.0),
    }


def strike_ladder(pos: dict, chain: list[dict], width: int = 3) -> list[dict]:
    """The held strike plus `width` strikes either side, same option type."""
    rows = sorted((c for c in chain if c["kind"] == pos["type"]), key=lambda c: c["strike"])
    idx = next(i for i, c in enumerate(rows) if abs(c["strike"] - pos["strike"]) < 1e-6)
    return [dict(c, held=(i == idx)) for i, c in enumerate(rows) if abs(i - idx) <= width]


def save_snapshot(valuation: dict, snap_dir: str) -> str:
    os.makedirs(snap_dir, exist_ok=True)
    path = os.path.join(snap_dir, f"{valuation['as_of']}.json")
    slim = {
        "as_of": valuation["as_of"],
        "chains": valuation["chains"],
        "positions": [{k: p.get(k) for k in ("id", "ticker", "price", "iv", "pnl_pct", "market_value")}
                      for p in valuation["positions"]],
        "nav": valuation.get("nav"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=1)
    return path


def load_history(snap_dir: str, as_of: str) -> list[dict]:
    """All snapshots before as_of, oldest first (for NAV curve and IV rank)."""
    if not os.path.isdir(snap_dir):
        return []
    out = []
    for f in sorted(os.listdir(snap_dir)):
        if f.endswith(".json") and f[:-5] < as_of:
            with open(os.path.join(snap_dir, f), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out
