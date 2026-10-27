"""Render the morning dashboard as one self-contained HTML file (no JS, no CDN)."""

from __future__ import annotations

from html import escape

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171c;--muted:#5d6672;--line:#e3e6ea;
--up:#137a43;--down:#b42318;--warn:#a15c00;--info:#2f5fb3;--accent:#14171c;--bar:#c9d3e0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1116;--card:#161a21;--ink:#e7eaef;
--muted:#97a1ad;--line:#262c35;--up:#4cc38a;--down:#ff6b5e;--warn:#f0a43a;--info:#7aa7ff;--bar:#36414f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
header{display:flex;flex-wrap:wrap;gap:12px 32px;align-items:flex-end;margin-bottom:16px}
h1{font-size:20px;margin:0}h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.kpi{display:flex;flex-direction:column}.kpi b{font-size:22px;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:12px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(12,1fr)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0;overflow-x:auto}
.s12{grid-column:span 12}.s8{grid-column:span 8}.s6{grid-column:span 6}.s4{grid-column:span 4}
@media (max-width:860px){.s8,.s6,.s4{grid-column:span 12}}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:500;font-size:12px}
.scroll{overflow-x:auto}.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.alert{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}.alert:last-child{border:0}
.tag{font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;border:1px solid currentColor;height:fit-content}
.action{color:var(--down)}.warn{color:var(--warn)}.info{color:var(--info)}
.bar{height:8px;background:var(--bar);border-radius:4px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ink)}
tr.held td{font-weight:600;background:color-mix(in srgb,var(--info) 10%,transparent)}
.gate{font-size:20px;font-weight:700}.news li{margin:4px 0}.news{padding-left:18px;margin:6px 0 12px}
.foot{color:var(--muted);font-size:12px;margin-top:18px}
"""


def _money(x, signed=False):
    if x is None:
        return "–"
    s = f"{abs(x):,.0f}"
    sign = "-" if x < 0 else ("+" if signed and x > 0 else "")
    return f"{sign}${s}"


def _pct(x, nd=1, signed=True):
    return "–" if x is None else f"{x:+.{nd}f}%" if signed else f"{x:.{nd}f}%"


def _cls(x):
    return "" if not x else "up" if x > 0 else "down"


def _spark(points, w=220, h=40):
    vals = [v for _, v in points]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    xy = " ".join(f"{i / (len(vals) - 1) * w:.1f},{h - (v - lo) / rng * (h - 4) - 2:.1f}" for i, v in enumerate(vals))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="NAV trend">'
            f'<polyline fill="none" stroke="currentColor" stroke-width="2" points="{xy}"/></svg>')


def render(valuation, analytics, context, alerts, portfolio) -> str:
    e = escape
    a, g, macro, review = analytics, analytics["greeks"], context["macro"], context["review"]
    name = portfolio.get("account", {}).get("name", "Options book")
    pos = valuation["positions"]
    rv = review.get("positions") or {}

    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Options Terminal</title><style>{CSS}</style></head><body><main>"]

    out.append("<header>")
    out.append(f"<div><h1>{e(name)}</h1><span class='muted'>Morning book · {e(valuation['as_of'])}</span></div>")
    for label, val, cls in (
        ("Net asset value", _money(a["nav"]), ""),
        ("Since start", _pct(a["total_return_pct"]), _cls(a["total_return_pct"])),
        ("Open P&L", _money(a["pnl"], True), _cls(a["pnl"])),
        ("Theta / day", _money(g["theta_day"], True), _cls(g["theta_day"])),
        ("Macro gate", e(macro["gate"]), "down" if macro["gate"] == "RISK-OFF" else "up" if macro["gate"] == "RISK-ON" else ""),
    ):
        out.append(f"<div class='kpi'><span>{label}</span><b class='{cls}'>{val}</b></div>")
    out.append(f"<div class='muted'>{_spark(a['nav_curve'])}</div></header><div class='grid'>")

    # Alerts
    out.append("<section class='card s8'><h2>Active alerts</h2>")
    if not alerts:
        out.append("<p class='muted'>Nothing needs attention today.</p>")
    for al in alerts:
        out.append(f"<div class='alert'><span class='tag {al['severity']}'>{al['severity'].upper()}</span>"
                   f"<div><b>{e(al['ticker'])}</b> {e(al['message'])}</div></div>")
    out.append("</section>")

    # Aggregate Greeks
    out.append("<section class='card s4'><h2>Aggregate Greeks</h2><table>")
    for label, val in (
        ("Dollar delta", _money(g["delta_dollars"], True)),
        ("Gamma (Δ per $1)", f"{g['gamma']:,.1f}"),
        ("Theta / day", _money(g["theta_day"], True)),
        ("Theta, next 30d", _money(g["theta_30d"], True)),
        ("Theta % of options / day", _pct(g["theta_pct_of_options"], 2)),
        ("Vega per vol pt", _money(g["vega"], True)),
        ("Cash", _money(a["cash"])),
    ):
        out.append(f"<tr><td>{label}</td><td>{val}</td></tr>")
    out.append("</table></section>")

    # Positions
    out.append("<section class='card s12'><h2>Positions</h2><div class='scroll'><table><tr><th>Position</th>"
               "<th>Qty</th><th>Spot</th><th>Mark</th><th>Value</th><th>P&amp;L</th><th>P&amp;L %</th>"
               "<th>To target</th><th>Claude</th></tr>")
    for p in pos:
        label = p["ticker"] if p["type"] == "stock" else f"{p['ticker']} {p['strike']:g}{p['type'][0].upper()} {p['expiry']}"
        tt = p.get("to_target")
        bar = (f"<div class='bar' title='{tt:.0f}%'><i style='width:{max(0, min(tt, 100)):.0f}%'></i></div>"
               if tt is not None else "–")
        call = rv.get(p["id"], {}).get("action", "–")
        out.append(f"<tr><td>{e(label)}</td><td>{p['qty']}</td><td>{p['spot']:,.2f}</td><td>{p['price']:,.2f}</td>"
                   f"<td>{_money(p['market_value'])}</td><td class='{_cls(p['pnl'])}'>{_money(p['pnl'], True)}</td>"
                   f"<td class='{_cls(p['pnl_pct'])}'>{_pct(p['pnl_pct'])}</td><td style='min-width:90px'>{bar}</td>"
                   f"<td>{e(call.upper())}</td></tr>")
    out.append("</table></div></section>")

    # Theta decay
    opts = [p for p in pos if p["type"] != "stock"]
    out.append("<section class='card s6'><h2>Theta decay</h2><div class='scroll'><table><tr><th>Contract</th>"
               "<th>DTE</th><th>IV</th><th>Delta</th><th>Theta/day</th><th>% of value</th></tr>")
    for p in sorted(opts, key=lambda p: p["dte"]):
        pct = p["theta_day"] / p["market_value"] * 100 if p["market_value"] else 0
        dte_cls = "warn" if p["dte"] < portfolio.get("settings", {}).get("min_dte_warning", 45) else ""
        out.append(f"<tr><td>{e(p['ticker'])} {p['strike']:g}{p['type'][0].upper()}</td>"
                   f"<td class='{dte_cls}'>{p['dte']}</td><td>{p['iv'] * 100:.0f}%</td><td>{p['delta']:.2f}</td>"
                   f"<td class='down'>{_money(p['theta_day'], True)}</td><td>{_pct(pct, 2)}</td></tr>")
    out.append("</table></div></section>")

    # Macro gate
    out.append(f"<section class='card s6'><h2>Macro gate</h2><div class='gate'>{e(macro['gate'])} "
               f"<span class='muted' style='font-size:14px'>score {macro['score']:+d}</span></div>"
               "<table><tr><th>Signal</th><th>Value</th><th>Read</th><th>Score</th></tr>")
    for c in macro["components"]:
        out.append(f"<tr><td>{e(c['name'])}</td><td>{c['value']}</td><td>{e(c['note'])}</td>"
                   f"<td class='{_cls(c['score'])}'>{c['score']:+d}</td></tr>")
    out.append("</table></section>")

    # Strike ladders
    out.append("<section class='card s12'><h2>Strike ladder</h2><div class='grid'>")
    for p in opts:
        out.append(f"<div class='s6 scroll'><b>{e(p['ticker'])} {e(p['expiry'])} {e(p['type'])}s</b>"
                   "<table><tr><th>Strike</th><th>Bid</th><th>Ask</th><th>IV</th><th>Vol</th><th>OI</th></tr>")
        for r in valuation["ladders"][p["id"]]:
            out.append(f"<tr class='{'held' if r['held'] else ''}'><td>{r['strike']:g}</td><td>{r['bid']:.2f}</td>"
                       f"<td>{r['ask']:.2f}</td><td>{r['iv'] * 100:.0f}%</td><td>{r['volume']:,}</td><td>{r['oi']:,}</td></tr>")
        out.append("</table></div>")
    out.append("</div></section>")

    # IV environment + allocation
    out.append("<section class='card s6'><h2>IV environment</h2><table><tr><th>Name</th><th>ATM IV</th>"
               "<th>HV30</th><th>IV/HV</th><th>IV rank</th><th>Read</th></tr>")
    for t, v in a["iv_env"].items():
        rank = f"{v['iv_rank']:.0f}" if v["iv_rank"] is not None else f"<span class='muted'>{v['iv_rank_days']}d</span>"
        ratio = "–" if v["iv_hv"] is None else f"{v['iv_hv']:.2f}"
        out.append(f"<tr><td>{e(t)}</td><td>{_pct((v['atm_iv'] or 0) * 100, 0, False)}</td>"
                   f"<td>{_pct((v['hv30'] or 0) * 100, 0, False)}</td>"
                   f"<td>{ratio}</td><td>{rank}</td><td>{e(v['label'])}</td></tr>")
    out.append("</table></section>")

    out.append("<section class='card s6'><h2>Allocation</h2><table>")
    for s, pct in a["allocation_sector"].items():
        out.append(f"<tr><td>{e(s)}</td><td style='width:55%'><div class='bar'><i style='width:{min(pct, 100):.0f}%'></i></div></td>"
                   f"<td>{pct:.1f}%</td></tr>")
    out.append("</table></section>")

    # Claude + news
    out.append("<section class='card s12'><h2>Claude's read &amp; news</h2>")
    mode = review.get("mode")
    if mode == "live" and not review.get("error"):
        out.append(f"<p>{e(review.get('book', ''))}</p>")
    elif mode == "dry-run":
        out.append("<p class='muted'>Dry run — the prompt was written to <code>review_prompt.txt</code>; no API call made.</p>")
    else:
        out.append(f"<p class='muted'>Claude review {e(mode or 'off')}{': ' + e(review['error']) if review.get('error') else ''}.</p>")
    for t, items in context["news"].items():
        calls = [(pid, r) for pid, r in rv.items() if any(p["id"] == pid and p["ticker"] == t for p in pos)]
        out.append(f"<h3 style='margin:10px 0 2px;font-size:15px'>{e(t)}</h3>")
        for pid, r in calls:
            out.append(f"<div><span class='tag info'>{e(r.get('action', '').upper())}</span> "
                       f"<b>{e(r.get('sentiment', ''))}</b> — {e(r.get('summary', ''))} "
                       f"<span class='muted'>{e(r.get('reason', ''))}</span></div>")
        out.append("<ul class='news'>" + "".join(
            f"<li>{e(n['title'])} <span class='muted'>· {e(str(n.get('publisher') or ''))}</span></li>" for n in items[:5])
            + ("" if items else "<li class='muted'>No headlines</li>") + "</ul>")
    out.append("</section></div>")

    out.append("<p class='foot'>Decision support only — not financial advice. Every trade is placed by a human. "
               "Quotes from Yahoo Finance can be delayed; Greeks computed locally with Black-Scholes.</p>")
    out.append("</main></body></html>")
    return "".join(out)
