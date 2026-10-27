# PancakeSwap BNB Prediction data collector

Append-only collector for PancakeSwap Prediction V2 on BNB Chain (5-minute rounds).

- Prediction contract: `0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA`
- Settlement oracle: Chainlink BNB/USD `0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE`
- RPCs: `bsc.publicnode.com`, `bsc-dataseed.binance.org` (failover)
- Prices: Binance `BNBUSDT` (`api.binance.com`, fallback `data-api.binance.vision`)

Free RPCs keep only ~1 hour of logs, so the collector must **run every 30 minutes**.
Each run looks back 90 minutes, so consecutive runs overlap and de-duplicate.

## Run

```bash
./run.sh            # collect, append, commit and push data/
python3 collector.py  # collect and append only
```

## Data files (`data/`)

| File | Key (de-dup) | Contents |
|---|---|---|
| `bets.csv` | `tx_hash, log_index` | Every BetBull/BetBear: block, block timestamp, epoch, side, sender, amount |
| `rounds.csv` | `epoch` | Finished rounds: start/lock/close timestamps, lock/close price (8 decimals), lock/close Chainlink round IDs and their `updatedAt` publish times, total/bull/bear/reward amounts (wei), `oracle_called` |
| `binance_1s.csv` | `epoch, open_time_ms` | BNBUSDT 1s closes and volume, lock−90s to lock+10s |
| `binance_5m.csv` | `open_time_ms` | BNBUSDT closed 5m candles |
| `state.json` | | Last bet block and last finished epoch collected |
| `health.log` | | One line per run: status, rows added per file, gaps |

Rules: rows are only ever appended, never rewritten. Nothing is interpolated: block
timestamps come from the chain, and any failed source is written to `health.log` as a gap.
Only bets are time-sensitive (lost once the RPC prunes logs). Rounds, oracle times and
Binance klines are re-fetchable later, and a failed epoch is retried on the next run.

## Tests

```bash
pip install pytest && python3 -m pytest -q tests
```
