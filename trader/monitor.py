"""Daily options-book monitor — runs all four layers and writes the morning dashboard.

  Layer 1  data & valuation    spot, chains, matched contracts, local Greeks, P&L, snapshot
  Layer 2  portfolio analytics NAV, allocation, aggregate Greeks, theta bleed, IV environment
  Layer 3  context & news      deterministic macro gate + one Claude call reading news/price action
  Layer 4  alerts & dashboard  targets/stops/DTE, new strikes/expiries, IV moves, HTML + optional push

Usage (from the repo root):
  # Offline demo on the bundled sample book (no network, no keys):
  python -m trader.monitor --portfolio trader/portfolio.example.json --fixture trader/fixtures/day2.json

  # Live, once each morning (pip install yfinance openai; set ANTHROPIC_API_KEY):
  python -m trader.monitor --portfolio trader/portfolio.json

  # See exactly what Claude would be sent, without paying for the call:
  python -m trader.monitor --portfolio trader/portfolio.json --llm dry-run

Not financial advice. It flags; a human decides and places every trade.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from . import dashboard, layer1_valuation, layer2_analytics, layer3_context, layer4_alerts
from .providers import FixtureProvider

HERE = os.path.dirname(os.path.abspath(__file__))


def run(portfolio: dict, provider, as_of: date, out_dir: str, llm_mode: str = "off") -> dict:
    snap_dir = os.path.join(out_dir, "snapshots")
    iso = as_of.isoformat()

    valuation = layer1_valuation.run(portfolio, provider, as_of)
    history = layer1_valuation.load_history(snap_dir, iso)
    previous = history[-1] if history else None
    analytics = layer2_analytics.run(valuation, portfolio, provider, history)
    valuation["nav"] = analytics["nav"]
    context = layer3_context.run(valuation, analytics, portfolio, provider, llm_mode)
    alerts = layer4_alerts.run(valuation, analytics, context, portfolio, previous)

    os.makedirs(out_dir, exist_ok=True)
    layer1_valuation.save_snapshot(valuation, snap_dir)
    html_path = os.path.join(out_dir, "dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(dashboard.render(valuation, analytics, context, alerts, portfolio))
    with open(os.path.join(out_dir, "alerts.json"), "w", encoding="utf-8") as f:
        json.dump({"as_of": iso, "alerts": alerts, "review": context["review"]}, f, indent=2, default=str)
    if context["review"].get("mode") == "dry-run":
        with open(os.path.join(out_dir, "review_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(f"MODEL: {context['review']['model']}\n\nSYSTEM:\n{context['review']['system']}\n\n"
                    f"USER:\n{context['review']['prompt']}\n")

    return {"valuation": valuation, "analytics": analytics, "context": context,
            "alerts": alerts, "dashboard": html_path}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portfolio", default=os.path.join(HERE, "portfolio.json"))
    ap.add_argument("--fixture", help="Offline market data JSON instead of Yahoo Finance")
    ap.add_argument("--date", help="Valuation date YYYY-MM-DD (default: fixture date or today)")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--llm", choices=("auto", "off", "dry-run", "live"), default="auto",
                    help="auto = live when ANTHROPIC_API_KEY is set, else off")
    ap.add_argument("--push", action="store_true", help="Send action/warn alerts to Telegram")
    args = ap.parse_args(argv)

    if not os.path.exists(args.portfolio):
        print(f"No portfolio at {args.portfolio}. Copy trader/portfolio.example.json and edit it.", file=sys.stderr)
        return 2
    with open(args.portfolio, encoding="utf-8") as f:
        portfolio = json.load(f)

    if args.fixture:
        provider = FixtureProvider(args.fixture)
        as_of = date.fromisoformat(args.date) if args.date else provider.as_of
    else:
        from .providers import YahooProvider
        provider = YahooProvider()
        as_of = date.fromisoformat(args.date) if args.date else date.today()

    llm = args.llm
    if llm == "auto":
        llm = "live" if os.environ.get("ANTHROPIC_API_KEY") else "off"

    res = run(portfolio, provider, as_of, args.out, llm)
    a = res["analytics"]
    print(layer4_alerts.format_push(as_of.isoformat(), a, res["alerts"]))
    print(f"\nDashboard: {res['dashboard']}")
    if args.push:
        layer4_alerts.push_telegram(layer4_alerts.format_push(as_of.isoformat(), a, res["alerts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
