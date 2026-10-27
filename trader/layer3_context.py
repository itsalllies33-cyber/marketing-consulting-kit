"""Layer 3 — market context and news.

Two parts:
  * Macro gate (deterministic, free): VIX level and trend, breadth (equal-weight
    vs cap-weight S&P), credit (high yield vs Treasuries) and SPY trend.
  * Claude review (the only part that costs tokens): one call per day that reads
    the news, price action and technicals for every name held and returns a short
    summary, sentiment and suggested action per position.
"""

from __future__ import annotations

import json
import os

MACRO_TICKERS = {"vix": "^VIX", "spy": "SPY", "rsp": "RSP", "hyg": "HYG", "ief": "IEF"}
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
TRADER_MODEL = os.environ.get("CLAUDE_MODEL_TRADER", "claude-sonnet-5-5")


# ---------------------------------------------------------------- technicals

def sma(closes, n):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def rsi(closes, n=14):
    """Wilder RSI."""
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g, avg_l = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def _chg(closes, n):
    return (closes[-1] / closes[-1 - n] - 1) * 100 if len(closes) > n else None


def technicals(closes: list[float]) -> dict:
    s20, s50 = sma(closes, 20), sma(closes, 50)
    last = closes[-1]
    high = max(closes[-252:])
    trend = "n/a"
    if s20 and s50:
        trend = "up" if last > s20 > s50 else "down" if last < s20 < s50 else "mixed"
    return {
        "last": last, "rsi14": rsi(closes), "sma20": s20, "sma50": s50,
        "chg_1d": _chg(closes, 1), "chg_5d": _chg(closes, 5), "chg_20d": _chg(closes, 20),
        "off_high_pct": (last / high - 1) * 100, "trend": trend,
    }


# ---------------------------------------------------------------- macro gate

def macro_gate(provider) -> dict:
    hist = {}
    for key, sym in MACRO_TICKERS.items():
        try:
            hist[key] = provider.history(sym)
        except Exception:  # one missing series shouldn't kill the gate
            hist[key] = []

    components = []

    def add(name, value, score, note):
        components.append({"name": name, "value": value, "score": score, "note": note})

    vix = hist["vix"]
    if vix:
        lvl = vix[-1]
        add("VIX level", round(lvl, 2), 1 if lvl < 16 else -2 if lvl > 30 else -1 if lvl > 22 else 0,
            "calm" if lvl < 16 else "stressed" if lvl > 22 else "normal")
        avg = sma(vix, 20)
        if avg:
            ratio = lvl / avg
            add("VIX vs 20d avg", round(ratio, 2), -1 if ratio > 1.15 else 1 if ratio < 0.9 else 0,
                "spiking" if ratio > 1.15 else "falling" if ratio < 0.9 else "steady")
    for name, a, b, up, down, notes in (
        ("Breadth (RSP/SPY 20d)", "rsp", "spy", 1.0, -1.0, ("broadening", "narrowing")),
        ("Credit (HYG/IEF 20d)", "hyg", "ief", 0.5, -1.0, ("spreads tightening", "spreads widening")),
    ):
        x, y = hist[a], hist[b]
        if len(x) > 20 and len(y) > 20:
            chg = ((x[-1] / y[-1]) / (x[-21] / y[-21]) - 1) * 100
            add(name, round(chg, 2), 1 if chg > up else -1 if chg < down else 0,
                notes[0] if chg > up else notes[1] if chg < down else "flat")
    spy = hist["spy"]
    if len(spy) >= 50:
        above = spy[-1] > sma(spy, 50)
        add("SPY vs 50d SMA", round((spy[-1] / sma(spy, 50) - 1) * 100, 2), 1 if above else -1,
            "above trend" if above else "below trend")

    score = sum(c["score"] for c in components)
    gate = "RISK-ON" if score >= 2 else "RISK-OFF" if score <= -2 else "NEUTRAL"
    return {"score": score, "gate": gate, "components": components}


# ---------------------------------------------------------------- Claude review

SYSTEM = (
    "You are the portfolio manager's analyst for a small options-and-shares book. "
    "Each morning you read the news, price action and Greeks for every position and "
    "say what, if anything, should change. Be specific and brief. Cite the headline or "
    "number behind each call. Never invent news that is not in the input. "
    "This is decision support for a human who places every trade."
)

ACTIONS = ("hold", "add", "trim", "exit", "watch")


def build_review_prompt(valuation, analytics, techs, news, macro, portfolio) -> str:
    lines = [
        f"Date: {valuation['as_of']}",
        f"Strategy: {portfolio.get('account', {}).get('strategy', 'n/a')}",
        f"Risk tolerance: {portfolio.get('account', {}).get('risk_tolerance', 'n/a')}",
        f"NAV ${analytics['nav']:,.0f} | cash ${analytics['cash']:,.0f} | "
        f"theta ${analytics['greeks']['theta_day']:,.0f}/day | "
        f"macro gate {macro['gate']} (score {macro['score']})",
        "",
        "POSITIONS",
    ]
    for p in valuation["positions"]:
        if p["type"] == "stock":
            desc = f"{p['qty']} sh"
        else:
            desc = (f"{p['qty']}x {p['type']} {p['strike']:g} exp {p['expiry']} "
                    f"({p['dte']}d, IV {p['iv']*100:.0f}%, delta {p['delta']:.2f})")
        lines.append(f"- {p['id']} {p['ticker']} {desc} | P&L {p['pnl_pct']:+.1f}% | "
                     f"target {p.get('target_pct')}% stop {p.get('stop_pct')}% | thesis: {p.get('thesis', 'n/a')}")
    lines += ["", "TECHNICALS & NEWS"]
    for t, tech in techs.items():
        env = analytics["iv_env"].get(t, {})
        lines.append(
            f"## {t}: last {tech['last']:.2f}, 1d {_f(tech['chg_1d'])}%, 5d {_f(tech['chg_5d'])}%, "
            f"20d {_f(tech['chg_20d'])}%, RSI {_f(tech['rsi14'], 0)}, trend {tech['trend']}, "
            f"{_f(tech['off_high_pct'])}% off 52w high, IV {env.get('label', 'n/a')}")
        for n in news.get(t, [])[:6]:
            lines.append(f"  * {n['title']} ({n.get('publisher') or 'n/a'}, {n.get('published') or 'n/a'})")
        if not news.get(t):
            lines.append("  * (no headlines)")
    lines += [
        "",
        "Return ONLY JSON, no prose, in this shape:",
        '{"book": "<2-3 sentence read on the whole book today>",',
        ' "positions": {"<position id>": {"summary": "<1-2 sentences>", '
        '"sentiment": "bullish|neutral|bearish", "action": "hold|add|trim|exit|watch", '
        '"reason": "<the specific headline/number driving it>", '
        '"suggested_stop": "<optional>", "suggested_target": "<optional>"}}}',
    ]
    return "\n".join(lines)


def _f(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def parse_review(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("Claude reply had no JSON object")
    data = json.loads(text[start:end + 1])
    for v in data.get("positions", {}).values():
        if v.get("action") not in ACTIONS:
            v["action"] = "watch"
    return data


def claude_review(prompt: str, mode: str) -> dict:
    """mode: off | dry-run | live. Live needs ANTHROPIC_API_KEY and `pip install openai`."""
    if mode == "off":
        return {"mode": "off"}
    if mode == "dry-run":
        return {"mode": "dry-run", "prompt": prompt, "system": SYSTEM, "model": TRADER_MODEL}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"mode": "skipped", "error": "ANTHROPIC_API_KEY not set"}
    from openai import OpenAI  # same OpenAI-compatible path as run_prompt.py

    client = OpenAI(base_url=ANTHROPIC_BASE_URL, api_key=key)
    resp = client.chat.completions.create(
        model=TRADER_MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        max_tokens=2500,
    )
    text = resp.choices[0].message.content or ""
    try:
        return {"mode": "live", "model": TRADER_MODEL, **parse_review(text)}
    except ValueError as exc:
        return {"mode": "live", "model": TRADER_MODEL, "error": f"unparseable reply: {exc}", "raw": text}


def run(valuation, analytics, portfolio, provider, llm_mode: str) -> dict:
    tickers = sorted({p["ticker"] for p in valuation["positions"]})
    techs = {t: technicals(provider.history(t)) for t in tickers}
    news = {}
    for t in tickers:
        try:
            news[t] = provider.news(t)
        except Exception:
            news[t] = []
    macro = macro_gate(provider)
    prompt = build_review_prompt(valuation, analytics, techs, news, macro, portfolio)
    return {"technicals": techs, "news": news, "macro": macro, "review": claude_review(prompt, llm_mode)}
