# Prompt: Contract Selection & Book Construction

**Where to run:** Claude web app, same chat as `02-screen.md`  
**Phase:** Research, step 3 of 3  
**Deliverable:** Exact orders (ticker, strike, expiry, qty, limit) plus a filled-in `portfolio.json` for the daily monitor

---

## Variables

| Variable | Example |
|----------|---------|
| `{{FINAL_NAMES}}` | NOW, NOK, HIMS, NBIS (options); MP (shares) |
| `{{ACCOUNT_SIZE}}` | $66,000 |
| `{{CHAIN_DATA}}` | Paste the bid/ask/IV/OI for the strikes you're looking at from your broker, or a screenshot |

---

## Step 1: Pick the contracts

**System prompt:**
```
You are an options trader building a defined-risk book. You choose strikes and expiries deliberately: enough time for the thesis to play out, Greeks that suit the view, and premium that is reasonable relative to IV. You show your reasoning in numbers.
```

**User prompt:**
```
Final names: {{FINAL_NAMES}}
Account size: {{ACCOUNT_SIZE}}

Current chain data:
{{CHAIN_DATA}}

For each options name, pick ONE contract and explain:
- Expiry: why this much time (must be >45 DTE; prefer LEAPS for slow theses)
- Strike: moneyness and delta, and why that fits the view
- Cost vs. IV: is this premium reasonable relative to the name's IV history?
- Theta per day in dollars and as % of the premium
- Breakeven at expiry and the stock move needed

For share positions: entry zone and size.

Then lay out the full book:
| Position | Instrument | Qty | Limit price | Cost | % of account | Target (%) | Stop (%) | Catalyst date |

Leave a cash reserve per the strategy. Then output the book as JSON in exactly this shape so I can load it into my daily monitor:

{"account": {"name": "...", "starting_nav": <number>, "cash": <number>, "strategy": "...", "risk_tolerance": "..."},
 "settings": {"risk_free_rate": 0.04, "min_dte_warning": 45, "iv_move_alert_pts": 5, "max_position_pct": 25},
 "watch": [],
 "positions": [
   {"id": "NOW-200C-2027-06", "ticker": "NOW", "type": "call", "strike": 200, "expiry": "2027-06-17", "qty": 4,
    "cost_basis": 14.20, "target_pct": 100, "stop_pct": -50, "sector": "...", "thesis": "..."},
   {"id": "MP-SH", "ticker": "MP", "type": "stock", "qty": 250, "cost_basis": 58.00, "stop_pct": -20, "sector": "...", "thesis": "..."}
 ]}
```

---

## After you place the trades

1. Replace each `cost_basis` with your **actual fill price** (per share for options, e.g. 14.20 not 1,420).
2. Save as `trader/portfolio.json` (git-ignored, stays on your machine).
3. Run the daily monitor — see `trader/README.md`.

---

## Quality checklist

- [ ] Every contract is >45 DTE
- [ ] Every contract's open interest and bid/ask spread were checked in the broker
- [ ] Total cost + cash reserve = account size
- [ ] No single name exceeds the max-position rule
- [ ] JSON validates and `cost_basis` uses actual fills

> Not financial advice. You place and own every trade.
