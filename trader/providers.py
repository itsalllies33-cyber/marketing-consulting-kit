"""Market data providers.

Every layer talks to a provider through five calls: spot, history, expiries,
chain and news. YahooProvider is the free live source; FixtureProvider reads a
JSON file so the whole system runs offline (tests, demos, no network).
Swap in Polygon/FMP by implementing the same five methods.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date

from .greeks import bs_price


class YahooProvider:
    """Live data from Yahoo Finance via yfinance (pip install yfinance).

    Fine for one run a day. Avoid hammering intraday bars — Yahoo rate-limits.
    """

    def __init__(self):
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise SystemExit("Live mode needs yfinance: pip install yfinance") from exc
        self._yf = yf
        self._tickers = {}

    def _t(self, ticker):
        if ticker not in self._tickers:
            self._tickers[ticker] = self._yf.Ticker(ticker)
        return self._tickers[ticker]

    def history(self, ticker: str) -> list[float]:
        df = self._t(ticker).history(period="1y", auto_adjust=False)
        return [float(x) for x in df["Close"].dropna().tolist()]

    def spot(self, ticker: str) -> float:
        closes = self.history(ticker)
        if not closes:
            raise ValueError(f"No price data for {ticker}")
        return closes[-1]

    def expiries(self, ticker: str) -> list[str]:
        return list(self._t(ticker).options)

    def chain(self, ticker: str, expiry: str) -> list[dict]:
        oc = self._t(ticker).option_chain(expiry)
        rows = []
        for kind, df in (("call", oc.calls), ("put", oc.puts)):
            for rec in df.to_dict("records"):
                rows.append({
                    "kind": kind,
                    "strike": float(rec["strike"]),
                    "bid": _num(rec.get("bid")),
                    "ask": _num(rec.get("ask")),
                    "last": _num(rec.get("lastPrice")),
                    "iv": _num(rec.get("impliedVolatility")),
                    "volume": int(_num(rec.get("volume"))),
                    "oi": int(_num(rec.get("openInterest"))),
                })
        return rows

    def news(self, ticker: str) -> list[dict]:
        items = []
        for raw in (self._t(ticker).news or [])[:8]:
            c = raw.get("content", raw)  # newer yfinance nests fields under "content"
            provider = c.get("provider") or {}
            items.append({
                "title": c.get("title", ""),
                "publisher": provider.get("displayName") if isinstance(provider, dict) else c.get("publisher", ""),
                "published": c.get("pubDate") or c.get("providerPublishTime", ""),
            })
        return [i for i in items if i["title"]]


def _num(x) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) else x


class FixtureProvider:
    """Offline provider. Chains are priced with Black-Scholes from each ticker's
    fixture IV (plus a mild skew) so Greeks, ladders and alerts behave realistically.
    """

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.as_of = date.fromisoformat(self.data["as_of"])
        self.r = self.data.get("risk_free_rate", 0.04)

    def _tk(self, ticker):
        try:
            return self.data["tickers"][ticker]
        except KeyError:
            raise ValueError(f"No fixture data for {ticker}") from None

    def history(self, ticker: str) -> list[float]:
        tk = self._tk(ticker)
        if isinstance(tk.get("history"), list):
            return tk["history"]
        # Deterministic synthetic walk that ends exactly at spot.
        h = tk.get("history", {})
        rng = random.Random(h.get("seed", ticker))
        n, vol, drift = 252, h.get("vol", 0.02), h.get("drift", 0.0)
        steps = [rng.gauss(drift, vol) for _ in range(n - 1)]
        path, level = [1.0], 1.0
        for s in steps:
            level *= math.exp(s)
            path.append(level)
        scale = tk["spot"] / path[-1]
        return [round(p * scale, 2) for p in path]

    def spot(self, ticker: str) -> float:
        return self._tk(ticker)["spot"]

    def expiries(self, ticker: str) -> list[str]:
        return sorted(self._tk(ticker).get("chain", {}))

    def chain(self, ticker: str, expiry: str) -> list[dict]:
        tk = self._tk(ticker)
        spot, base_iv = tk["spot"], tk.get("iv", 0.5)
        t = max((date.fromisoformat(expiry) - self.as_of).days, 0) / 365
        rows = []
        for strike in tk["chain"][expiry]:
            iv = base_iv * (1 + 0.15 * abs(math.log(strike / spot)))  # smile
            for kind in ("call", "put"):
                mid = bs_price(kind, spot, strike, t, self.r, iv)
                spread = max(0.05, mid * 0.03)
                rows.append({
                    "kind": kind, "strike": float(strike),
                    "bid": round(max(mid - spread / 2, 0), 2), "ask": round(mid + spread / 2, 2),
                    "last": round(mid, 2), "iv": round(iv, 4),
                    "volume": int(200 * math.exp(-abs(math.log(strike / spot)) * 4)),
                    "oi": int(3000 * math.exp(-abs(math.log(strike / spot)) * 3)),
                })
        return rows

    def news(self, ticker: str) -> list[dict]:
        return self._tk(ticker).get("news", [])
