# Prompt: Monthly Strategy

**Where to run:** Claude web app (your subscription — no API cost)  
**Phase:** Research, step 1 of 3  
**Deliverable:** A written strategy for the month: instruments, sizing rules, holding periods, what to avoid

---

## Variables

| Variable | Example |
|----------|---------|
| `{{ACCOUNT_SIZE}}` | $66,000 |
| `{{BROKER}}` | Robinhood (options level 3) |
| `{{RISK_TOLERANCE}}` | Aggressive, but downside must be capped — no naked short options, no margin |
| `{{MAX_LOSS}}` | Willing to lose up to 30% of the account in a bad month |
| `{{HOLDING_PERIOD}}` | Weeks to months; I check once a day, not intraday |
| `{{TIME_WINDOW}}` | The month of November 2026 |
| `{{EXPERIENCE}}` | Comfortable buying calls and shares; new to Greeks |
| `{{EXCLUSIONS}}` | No crypto, no leveraged ETFs, no 0DTE |

---

## Step 1: Strategy design

**System prompt:**
```
You are a buy-side portfolio strategist with an options background. You design strategies around an explicit risk budget, not around excitement. You state assumptions, quantify downside, and say plainly when something is a bad fit for the account.
```

**User prompt:**
```
Design a trading strategy for {{TIME_WINDOW}}.

Account: {{ACCOUNT_SIZE}} at {{BROKER}}
Risk tolerance: {{RISK_TOLERANCE}}
Max acceptable drawdown: {{MAX_LOSS}}
Holding period: {{HOLDING_PERIOD}}
Experience: {{EXPERIENCE}}
Exclusions: {{EXCLUSIONS}}

I want a real mix of risk and upside: the upside can be large, but downside on every position must be capped (defined), never open-ended.

Use current market conditions (search if you can) and give me:

## 1. Market read
3-5 bullets on the regime right now (volatility, trend, rates, sector leadership) and what it implies for buying options vs. shares.

## 2. Core approach
Which instruments and why. For any options: minimum days to expiration, preferred moneyness, and how you will manage theta and IV (when is IV too expensive to buy?).

## 3. Where NOT to use options
Rules for when to buy shares instead (liquidity, open interest, bid/ask width, IV level, market cap).

## 4. Sizing & diversification
Max % of the account per position, per sector and per catalyst date. How many positions. Cash reserve.

## 5. Screening criteria
The exact filters I should use to find candidates (e.g. sold off but with a dated catalyst; momentum names; options priced reasonably).

## 6. Exit rules
Profit targets, stops, time stops, and when to roll.

## 7. What would make you abandon this strategy mid-month
```

---

## Quality checklist

- [ ] Every options idea has a stated minimum DTE and a defined max loss
- [ ] Sizing rules add up (no plan that puts >100% of the account to work)
- [ ] Clear rule for shares-vs-options, tied to liquidity and IV
- [ ] Exit rules are numeric, not "use judgment"
- [ ] Market read is dated and sourced (or explicitly marked as assumption)
- [ ] You'd be comfortable if the worst case in section 4 happened

> Not financial advice. Claude's output is a starting point for your own decisions.
