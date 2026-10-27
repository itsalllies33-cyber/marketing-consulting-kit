# Prompt: Candidate Screen

**Where to run:** Claude web app, same chat as `01-strategy.md`  
**Phase:** Research, step 2 of 3  
**Deliverable:** Scored candidate list with a thesis per name and a proposed combination

---

## Variables

| Variable | Example |
|----------|---------|
| `{{STRATEGY_SUMMARY}}` | Paste sections 2–5 of the strategy Claude wrote |
| `{{UNIVERSE}}` | US + ADR equities over $1B market cap; optionable where options are used |
| `{{SEED_TICKERS}}` | Optional names you already like, e.g. NOW, NBIS, HIMS, MP, NOK |
| `{{NUM_CANDIDATES}}` | 8–12 |

---

## Step 1: Broad screen

**System prompt:**
```
You are an equity research analyst screening for a defined strategy. You are skeptical: a name only makes the list if the upside is justified by a specific, dated catalyst or a clear momentum setup. You separate facts (with dates and sources) from opinion.
```

**User prompt:**
```
Strategy:
{{STRATEGY_SUMMARY}}

Universe: {{UNIVERSE}}
Names I'm already considering (screen them on the same terms, don't assume they pass): {{SEED_TICKERS}}

Find {{NUM_CANDIDATES}} candidates that fit the strategy. Include both:
- Oversold names that sold off but have a real reason to recover (a catalyst on the calendar that could rerate the stock), and
- Momentum names where the trend has a fundamental driver.

For each candidate, score 1-5 on:
| Ticker | Catalyst (what + date) | Catalyst timing (near/medium/long) | Upside case | Downside case | IV environment (cheap/fair/rich vs. its own history) | Options liquidity (OI, spread) | Correlation to SPY/QQQ | Sector |

Then for each name, give a 3-sentence thesis and say:
- Instrument: LEAPS call / shorter call / shares — and why
- Position size as % of account
- What would prove the thesis wrong

Finally, propose a combination of 4–7 names that staggers catalyst windows (near / medium / long term) and spreads across at least 3 sectors, so one failed earnings event or one sector breaking doesn't sink the book.
```

---

## Step 2 (optional): Deep dive on one name

**User prompt:**
```
Go deeper on {{TICKER}}. Build a simple probability distribution of where the stock could be at {{EXPIRY_DATE}} (bear / base / bull with probabilities), then show what the {{STRIKE}} call would be worth in each case and the expected value per contract vs. today's ask of {{ASK}}. State every assumption.
```

---

## Quality checklist

- [ ] Every catalyst has a date (or a date range) and a source
- [ ] Oversold and momentum names are both represented
- [ ] Proposed combination spans ≥3 sectors and ≥2 catalyst windows
- [ ] Each name says what would invalidate it
- [ ] Prices and IV levels are current (re-check them yourself in the broker before trading)

> Not financial advice. Verify every number in your broker before placing an order.
