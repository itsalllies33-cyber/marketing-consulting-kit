"""Layer 4 — alerts and push.

Compares today's chain with the previous snapshot (new strikes, new expiries,
IV moves), checks targets/stops/DTE, folds in the macro gate and Claude's calls,
and optionally pushes the result to Telegram.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

SEVERITY_ORDER = {"action": 0, "warn": 1, "info": 2}


def _alert(severity, ticker, kind, msg):
    return {"severity": severity, "ticker": ticker, "kind": kind, "message": msg}


def chain_diff(today: dict, previous: dict | None) -> list[dict]:
    alerts = []
    if not previous:
        return alerts
    for ticker, ch in today["chains"].items():
        prev = previous.get("chains", {}).get(ticker)
        if not prev:
            continue
        new_exps = sorted(set(ch["expiries"]) - set(prev["expiries"]))
        for exp in new_exps:
            alerts.append(_alert("info", ticker, "new_expiry", f"New expiry listed: {exp}"))
        for exp, strikes in ch["strikes"].items():
            if exp in new_exps or exp not in prev["strikes"]:
                continue
            added = sorted(set(strikes) - set(prev["strikes"][exp]))
            if added:
                alerts.append(_alert("info", ticker, "new_strike",
                                     f"New strikes for {exp}: " + ", ".join(f"{s:g}" for s in added)))
    return alerts


def run(valuation, analytics, context, portfolio, previous: dict | None) -> list[dict]:
    s = portfolio.get("settings", {})
    min_dte = s.get("min_dte_warning", 45)
    iv_move = s.get("iv_move_alert_pts", 5) / 100
    alerts = []

    prev_pos = {p["id"]: p for p in (previous or {}).get("positions", [])}
    for p in valuation["positions"]:
        t = p["ticker"]
        if p["stop_hit"]:
            alerts.append(_alert("action", t, "stop", f"{p['id']} hit stop: {p['pnl_pct']:+.1f}% (stop {p['stop_pct']}%)"))
        if p["target_hit"]:
            alerts.append(_alert("action", t, "target",
                                 f"{p['id']} hit target: {p['pnl_pct']:+.1f}% (target {p['target_pct']}%) — take profit or roll?"))
        elif p.get("to_target") is not None and p["to_target"] >= 80:
            alerts.append(_alert("warn", t, "near_target", f"{p['id']} is {p['to_target']:.0f}% of the way to target"))
        if p.get("underlying_target_hit"):
            alerts.append(_alert("action", t, "underlying_target", f"{t} reached underlying target {p['underlying_target']}"))
        if p["type"] != "stock":
            if p["dte"] is not None and p["dte"] < min_dte:
                alerts.append(_alert("warn", t, "dte",
                                     f"{p['id']} has {p['dte']} days left (< {min_dte}) — theta accelerates, consider rolling"))
            prev = prev_pos.get(p["id"])
            if prev and prev.get("iv") and p.get("iv") and abs(p["iv"] - prev["iv"]) >= iv_move:
                alerts.append(_alert("warn", t, "iv_move",
                                     f"{p['id']} IV moved {(p['iv'] - prev['iv']) * 100:+.1f} pts "
                                     f"({prev['iv'] * 100:.0f}% → {p['iv'] * 100:.0f}%)"))

    alerts += chain_diff(valuation, previous)

    for t in analytics["concentration"]:
        alerts.append(_alert("warn", t, "concentration",
                             f"{t} is {analytics['allocation_ticker'][t]:.0f}% of NAV "
                             f"(limit {s.get('max_position_pct', 25)}%)"))
    macro = context["macro"]
    if macro["gate"] == "RISK-OFF":
        alerts.append(_alert("warn", "MACRO", "macro", f"Macro gate RISK-OFF (score {macro['score']}) — no new risk today"))

    review = context["review"]
    for pid, r in (review.get("positions") or {}).items():
        if r.get("action") in ("exit", "trim", "add"):
            sev = "action" if r["action"] == "exit" else "warn"
            ticker = next((p["ticker"] for p in valuation["positions"] if p["id"] == pid), pid)
            alerts.append(_alert(sev, ticker, "claude", f"Claude suggests {r['action'].upper()} {pid}: {r.get('reason', '')}"))

    alerts.sort(key=lambda a: (SEVERITY_ORDER[a["severity"]], a["ticker"]))
    return alerts


def format_push(as_of, analytics, alerts, dashboard_hint="") -> str:
    head = (f"Book {as_of}: NAV ${analytics['nav']:,.0f}"
            + (f" ({analytics['total_return_pct']:+.1f}%)" if analytics.get("total_return_pct") is not None else "")
            + f", theta ${analytics['greeks']['theta_day']:,.0f}/day")
    body = [f"[{a['severity'].upper()}] {a['ticker']}: {a['message']}" for a in alerts if a["severity"] != "info"]
    return "\n".join([head] + (body or ["No action alerts."]) + ([dashboard_hint] if dashboard_hint else []))


def push_telegram(text: str) -> bool:
    """Send via a Telegram bot. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Push skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15) as r:
        return json.load(r).get("ok", False)
