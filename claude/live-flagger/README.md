# Live Flagger — PancakeSwap BNB Prediction

Flags only. The script makes read-only `eth_call`s and calls public Binance market-data endpoints. It never signs a transaction, holds a key or moves funds.

## Signal (as given 2026-10-27)
| Rule | Value |
|---|---|
| Decision moment | lockTimestamp − 3 s, Binance server clock (midpoint-RTT sync) |
| Chainlink | `latestRoundData()` of the Prediction contract's own `oracle()` |
| Skip | Chainlink age + seconds to lock > 25 s → `SKIP` |
| Offset | median(Chainlink − Binance 1s close at the oracle's `updatedAt`), last 30 updates |
| gapN | (Binance + offset − Chainlink) ÷ ATR(14) of closed 5m BNBUSDT candles |
| Flag | UP ≥ +0.38, DOWN ≤ −0.38, else `NO_CALL` |
| Score | on-chain closePrice vs lockPrice; tie = wrong; cancelled / non-calls unscored |

## Run
```bash
python3 flagger.py selftest   # offline math checks
python3 flagger.py run        # live loop, appends to flags.jsonl
python3 flagger.py summary    # hit rate, per-side, non-call outcome mix
```
Env overrides: `BSC_RPC`, `BINANCE_API` (default `https://data-api.binance.vision`), `FLAGGER_LOG`, `FLAGGER_CACHE`.

## Log (`flags.jsonl`)
- `decision`: epoch, timestamp, gapN, chainlink_age_s, flag, and `raw` = Binance price, Chainlink price/roundId/updatedAt, offset and all 30 samples, ATR and the candles behind it, secs_to_lock, staleness sum, input fetch latency, clock sync.
- `result`: epoch, flag, on-chain result (UP/DOWN/TIE/CANCELLED), correct (true/false/null), raw lock/close prices and oracle ids.
- `missed` / `error`: rounds the script couldn't evaluate in time, and exceptions.

## Choices the original spec file didn't pin down
`claude/live-realistic-correction-2026-10-26.md` wasn't in the repo, so these were judgment calls. Check them against the tested version:
- ATR(14) = plain mean of the last 14 true ranges (not Wilder smoothing), closed candles only.
- Binance reference = BNBUSDT last trade price; offset pairs use the 1s-kline close for the oracle's `updatedAt` second.
- Rounds that don't resolve within 120 s after closeTimestamp are logged as CANCELLED.
