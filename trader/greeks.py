"""Black-Scholes pricing, Greeks and implied volatility — stdlib only.

Yahoo Finance gives prices and a (noisy) IV per contract but no Greeks, so we
compute them locally. Premium feeds (Polygon, FMP) return Greeks directly and
can skip this module.
"""

from __future__ import annotations

import math

SQRT_2PI = math.sqrt(2 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _d1_d2(spot, strike, t, r, iv):
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
    return d1, d1 - iv * math.sqrt(t)


def bs_price(kind: str, spot: float, strike: float, t: float, r: float, iv: float) -> float:
    """Option price. kind is 'call' or 'put'; t in years."""
    if t <= 0 or iv <= 0:
        intrinsic = spot - strike if kind == "call" else strike - spot
        return max(intrinsic, 0.0)
    d1, d2 = _d1_d2(spot, strike, t, r, iv)
    if kind == "call":
        return spot * _cdf(d1) - strike * math.exp(-r * t) * _cdf(d2)
    return strike * math.exp(-r * t) * _cdf(-d2) - spot * _cdf(-d1)


def greeks(kind: str, spot: float, strike: float, t: float, r: float, iv: float) -> dict:
    """Per-share Greeks. theta is per calendar day, vega per 1 vol point (0.01)."""
    if t <= 0 or iv <= 0:
        itm = spot > strike if kind == "call" else spot < strike
        delta = (1.0 if itm else 0.0) * (1 if kind == "call" else -1)
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1, d2 = _d1_d2(spot, strike, t, r, iv)
    sqrt_t = math.sqrt(t)
    gamma = _pdf(d1) / (spot * iv * sqrt_t)
    vega = spot * _pdf(d1) * sqrt_t / 100
    decay = -spot * _pdf(d1) * iv / (2 * sqrt_t)
    if kind == "call":
        delta = _cdf(d1)
        theta = decay - r * strike * math.exp(-r * t) * _cdf(d2)
    else:
        delta = _cdf(d1) - 1
        theta = decay + r * strike * math.exp(-r * t) * _cdf(-d2)
    return {"delta": delta, "gamma": gamma, "theta": theta / 365, "vega": vega}


def implied_vol(kind: str, price: float, spot: float, strike: float, t: float, r: float) -> float | None:
    """Solve for IV by bisection. Returns None when the price is outside model bounds."""
    if price <= 0 or t <= 0:
        return None
    lo, hi = 1e-4, 5.0
    if not (bs_price(kind, spot, strike, t, r, lo) <= price <= bs_price(kind, spot, strike, t, r, hi)):
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if bs_price(kind, spot, strike, t, r, mid) > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-6:
            break
    return (lo + hi) / 2
