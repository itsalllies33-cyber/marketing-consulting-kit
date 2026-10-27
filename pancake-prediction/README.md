# PancakeSwap BNB Prediction — data collector

Collects raw data for research on PancakeSwap Prediction V2 (BNB Chain, 5-minute rounds).

- Contract: `0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA`
- Settlement oracle: Chainlink BNB/USD `0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE` (each run checks this against the contract's `oracle()`)
- RPCs: `bsc.publicnode.com`, then `bsc-dataseed.binance.org` as fallback
- Prices: `api.binance.com`, then `data-api.binance.vision` as fallback (GitHub runners are often geo-blocked from the first)

Free RPCs keep only ~1 hour of logs, so `collector.py` has to run **every 30 minutes**. Each run looks back 90 minutes, and the overlap is de-duplicated. `.github/workflows/prediction-collector.yml` does this on GitHub Actions and commits the new rows. The schedule is active only on the default branch.

```bash
python pancake-prediction/collector.py                 # one run, appends to pancake-prediction/data/
pytest -q pancake-prediction/tests                     # offline tests (fake chain + fake Binance)
```

## Files (all append-only)

| File | One row per | Key columns |
|---|---|---|
| `data/bets/YYYY-MM-DD.csv` | BetBull/BetBear event | block, block_ts, epoch, side, amount_wei/amount_bnb, sender, tx_hash, log_index |
| `data/rounds.csv` | finished round | start/lock/close_ts, lock/close_price (8 dp), lock/close_oracle_id, lock/close_oracle_updated_at (Chainlink `updatedAt`), bull/bear/total amounts (wei), oracle_called |
| `data/binance_1s/YYYY-MM-DD.csv` | second, lock−90 s … lock+10 s | epoch, lock_ts, open_time_ms, second_offset, close |
| `data/binance_5m.csv` | closed 5-minute candle | open_time_ms, OHLCV, trades |
| `data/health.log` | run | `<utc> <ok\|gaps\|error> bets+N rounds+N b1s+N b5m+N gaps=N errors=N runner=… \| details` |

## Rules

- **De-duplication.** Bets by `(tx_hash, log_index)` against today's and yesterday's files. Rounds by epoch, resuming after the highest epoch already in `rounds.csv`. 5-minute candles resume after the last `open_time_ms`.
- **A round is "finished" when its epoch is ≤ `currentEpoch() − 2`.** That is the newest round `executeRound` has closed. A round with `oracle_called=0` (cancelled, or the contract was paused) is stored as-is and noted in the health log.
- **First run.** Starts 18 rounds (90 min) back. Backfill after an outage is capped at 500 rounds per run, and anything skipped is logged.
- **`eth_getLogs` requests.** Ranges are at most 2,000 blocks. A range that fails is halved down to 125 blocks, then logged as a gap.
- **Nothing is invented.** A missing source, timestamp or second of data is a gap entry, never a filled-in value.
