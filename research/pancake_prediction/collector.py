"""Append-only data collector for PancakeSwap BNB Prediction (BNB Chain, 5-minute rounds).

Each run:
  1. BetBull/BetBear logs from the last LOOKBACK_MIN minutes (getLogs in <= CHUNK blocks),
     de-duplicated by (tx_hash, log_index).
  2. Every finished round since the last run, plus the Chainlink publish time of its
     lock/close oracle rounds.
  3. Binance BNBUSDT 1s closes from lock-90s to lock+10s for each new round, plus 5m candles.
  4. Appends to CSVs in data/ and writes one line to data/health.log.

Nothing is ever interpolated or filled in: a failed source is logged as a gap.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from Crypto.Hash import keccak

PREDICTION = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"
ORACLE = "0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE"
RPCS = ["https://bsc.publicnode.com", "https://bsc-dataseed.binance.org"]
BINANCE = ["https://api.binance.com", "https://data-api.binance.vision"]
LOOKBACK_MIN = 90
CHUNK = 2000
BATCH = 50
WEI = 10**18
PRICE_DECIMALS = 8  # Chainlink BNB/USD and the prediction contract both use 8 decimals

DATA_DIR = Path(os.environ.get("PRED_DATA_DIR", Path(__file__).parent / "data"))

FILES = {
    "bets": ["tx_hash", "log_index", "block", "block_ts", "epoch", "side", "sender",
             "amount_wei", "amount_bnb"],
    "rounds": ["epoch", "start_ts", "lock_ts", "close_ts", "lock_price", "close_price",
               "lock_oracle_id", "close_oracle_id", "lock_oracle_updated_at",
               "close_oracle_updated_at", "total_wei", "bull_wei", "bear_wei",
               "reward_base_wei", "reward_wei", "oracle_called"],
    "binance_1s": ["epoch", "lock_ts", "open_time_ms", "close", "volume"],
    "binance_5m": ["open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms"],
}
KEYS = {
    "bets": ("tx_hash", "log_index"),
    "rounds": ("epoch",),
    "binance_1s": ("epoch", "open_time_ms"),
    "binance_5m": ("open_time_ms",),
}


def keccak_hex(sig: str) -> str:
    h = keccak.new(digest_bits=256)
    h.update(sig.encode())
    return h.hexdigest()


TOPIC_BULL = "0x" + keccak_hex("BetBull(address,uint256,uint256)")
TOPIC_BEAR = "0x" + keccak_hex("BetBear(address,uint256,uint256)")
SEL_CURRENT_EPOCH = "0x" + keccak_hex("currentEpoch()")[:8]
SEL_ROUNDS = "0x" + keccak_hex("rounds(uint256)")[:8]
SEL_GET_ROUND_DATA = "0x" + keccak_hex("getRoundData(uint80)")[:8]


# ---------- ABI helpers ----------

def words(hexdata: str) -> list[int]:
    raw = hexdata[2:] if hexdata.startswith("0x") else hexdata
    return [int(raw[i:i + 64], 16) for i in range(0, len(raw), 64)]


def signed(v: int) -> int:
    return v - (1 << 256) if v >= 1 << 255 else v


def enc_uint(v: int) -> str:
    return format(v, "064x")


def decode_round(hexdata: str) -> dict:
    """Decode the `rounds(uint256)` return tuple of PancakePredictionV2."""
    w = words(hexdata)
    if len(w) < 14:
        raise ValueError(f"rounds() returned {len(w)} words, expected 14")
    return {
        "epoch": w[0], "start_ts": w[1], "lock_ts": w[2], "close_ts": w[3],
        "lock_price": signed(w[4]), "close_price": signed(w[5]),
        "lock_oracle_id": w[6], "close_oracle_id": w[7],
        "total_wei": w[8], "bull_wei": w[9], "bear_wei": w[10],
        "reward_base_wei": w[11], "reward_wei": w[12], "oracle_called": bool(w[13]),
    }


def decode_bet_log(log: dict) -> dict:
    topic0 = log["topics"][0].lower()
    return {
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
        "block": int(log["blockNumber"], 16),
        "epoch": int(log["topics"][2], 16),
        "side": "bull" if topic0 == TOPIC_BULL else "bear",
        "sender": "0x" + log["topics"][1][-40:].lower(),
        "amount_wei": words(log["data"])[0],
    }


# ---------- RPC ----------

class RPC:
    def __init__(self, urls: list[str], session: requests.Session | None = None):
        self.urls = urls
        self.s = session or requests.Session()

    def _post(self, payload):
        last = None
        for url in self.urls:
            for attempt in range(3):
                try:
                    r = self.s.post(url, json=payload, timeout=30)
                    r.raise_for_status()
                    return r.json()
                except Exception as e:  # noqa: BLE001 - try the next endpoint
                    last = f"{url.split('//')[-1]}: {type(e).__name__}"
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"all RPCs failed ({last})")

    def call(self, method: str, params: list):
        resp = self._post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" in resp:
            raise RuntimeError(f"{method}: {resp['error']}")
        return resp["result"]

    def batch(self, calls: list[tuple[str, list]]) -> list:
        """Run calls in JSON-RPC batches; returns results in order (exception object on error)."""
        out: list = []
        for i in range(0, len(calls), BATCH):
            chunk = calls[i:i + BATCH]
            payload = [{"jsonrpc": "2.0", "id": j, "method": m, "params": p}
                       for j, (m, p) in enumerate(chunk)]
            resp = self._post(payload)
            by_id = {r.get("id"): r for r in resp} if isinstance(resp, list) else {}
            for j in range(len(chunk)):
                r = by_id.get(j)
                if r is None or "error" in r:
                    out.append(RuntimeError(str(r.get("error") if r else "missing response")))
                else:
                    out.append(r["result"])
        return out

    def eth_call(self, to: str, data: str) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])


# ---------- storage ----------

def load_keys(name: str) -> set[tuple]:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        return set()
    with path.open(newline="") as f:
        return {tuple(row[k] for k in KEYS[name]) for row in csv.DictReader(f)}


def append_rows(name: str, rows: list[dict]) -> int:
    """Append rows whose key is not yet stored. Never rewrites existing lines."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.csv"
    seen = load_keys(name)
    new = []
    for row in rows:
        key = tuple(str(row[k]) for k in KEYS[name])
        if key not in seen:
            seen.add(key)
            new.append(row)
    if not new:
        return 0
    write_header = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FILES[name])
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)


def load_state() -> dict:
    path = DATA_DIR / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "state.json").write_text(json.dumps(state, indent=2) + "\n")


# ---------- step 1: bets ----------

def find_block_at(rpc: RPC, target_ts: int, latest: int, latest_ts: int) -> int:
    """First block with timestamp >= target_ts (binary search on real block timestamps)."""
    lo, hi = max(0, latest - 20_000), latest  # 20k blocks covers > 90 min at BSC block times
    while lo > 0 and int(rpc.call("eth_getBlockByNumber", [hex(lo), False])["timestamp"], 16) > target_ts:
        lo = max(0, lo - 20_000)
    while lo < hi:
        mid = (lo + hi) // 2
        ts = int(rpc.call("eth_getBlockByNumber", [hex(mid), False])["timestamp"], 16)
        if ts < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def collect_bets(rpc: RPC, state: dict, gaps: list[str]) -> tuple[list[dict], int]:
    head = rpc.call("eth_getBlockByNumber", ["latest", False])
    latest, latest_ts = int(head["number"], 16), int(head["timestamp"], 16)
    start = find_block_at(rpc, latest_ts - LOOKBACK_MIN * 60, latest, latest_ts)

    prev = state.get("last_bet_block")
    if prev is not None and prev + 1 < start:
        gaps.append(f"bets: blocks {prev + 1}-{start - 1} not covered (run too late)")

    logs = []
    for a in range(start, latest + 1, CHUNK):
        b = min(a + CHUNK - 1, latest)
        try:
            logs += rpc.call("eth_getLogs", [{
                "address": PREDICTION, "fromBlock": hex(a), "toBlock": hex(b),
                "topics": [[TOPIC_BULL, TOPIC_BEAR]],
            }])
        except Exception as e:  # noqa: BLE001
            gaps.append(f"bets: getLogs {a}-{b} failed ({str(e)[:120]})")

    rows = [decode_bet_log(l) for l in logs if not l.get("removed")]

    # Real block timestamps: use the log's own field if the node returns it, else fetch.
    ts_by_block = {int(l["blockNumber"], 16): int(l["blockTimestamp"], 16)
                   for l in logs if l.get("blockTimestamp")}
    missing = sorted({r["block"] for r in rows} - ts_by_block.keys())
    results = rpc.batch([("eth_getBlockByNumber", [hex(b), False]) for b in missing])
    for b, res in zip(missing, results):
        if isinstance(res, Exception) or not res:
            gaps.append(f"bets: no timestamp for block {b}")
        else:
            ts_by_block[b] = int(res["timestamp"], 16)

    for r in rows:
        r["block_ts"] = ts_by_block.get(r["block"], "")
        r["amount_bnb"] = f"{r['amount_wei'] / WEI:.18f}".rstrip("0").rstrip(".")
    return rows, latest


# ---------- step 2: rounds ----------

def oracle_updated_at(rpc: RPC, ids: list[int], gaps: list[str]) -> dict[int, int]:
    ids = sorted({i for i in ids if i})
    calls = [("eth_call", [{"to": ORACLE, "data": SEL_GET_ROUND_DATA + enc_uint(i)}, "latest"])
             for i in ids]
    out = {}
    for i, res in zip(ids, rpc.batch(calls)):
        if isinstance(res, Exception):
            gaps.append(f"oracle: getRoundData({i}) failed")
        else:
            out[i] = words(res)[3]  # (roundId, answer, startedAt, updatedAt, answeredInRound)
    return out


def collect_rounds(rpc: RPC, state: dict, gaps: list[str]) -> tuple[list[dict], int]:
    """Returns (rounds, safe_epoch): safe_epoch is the highest epoch with no failure at or
    below it, so a failed epoch is retried on the next run."""
    current = words(rpc.eth_call(PREDICTION, SEL_CURRENT_EPOCH))[0]
    # current = betting, current-1 = locked/live; finished rounds are <= current-2.
    last_done = current - 2
    first = state.get("last_round_epoch", last_done - LOOKBACK_MIN // 5) + 1
    epochs = list(range(first, last_done + 1))
    calls = [("eth_call", [{"to": PREDICTION, "data": SEL_ROUNDS + enc_uint(e)}, "latest"])
             for e in epochs]
    rounds = []
    safe = last_done
    for e, res in zip(epochs, rpc.batch(calls)):
        if isinstance(res, Exception):
            gaps.append(f"rounds: epoch {e} failed (will retry)")
            safe = min(safe, e - 1)
            continue
        r = decode_round(res)
        if not r["oracle_called"]:
            # Cancelled/unsettled round: kept as-is, flagged.
            gaps.append(f"rounds: epoch {e} not settled by oracle")
        rounds.append(r)

    upd = oracle_updated_at(rpc, [x for r in rounds for x in
                                  (r["lock_oracle_id"], r["close_oracle_id"])], gaps)
    for r in rounds:
        r["lock_oracle_updated_at"] = upd.get(r["lock_oracle_id"], "")
        r["close_oracle_updated_at"] = upd.get(r["close_oracle_id"], "")
        r["oracle_called"] = int(r["oracle_called"])
    return rounds, safe


# ---------- step 3: Binance ----------

def binance_klines(s: requests.Session, interval: str, start_ms: int, end_ms: int) -> list:
    last = None
    for base in BINANCE:
        try:
            r = s.get(f"{base}/api/v3/klines", timeout=30, params={
                "symbol": "BNBUSDT", "interval": interval,
                "startTime": start_ms, "endTime": end_ms, "limit": 1000})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = f"{base.split('//')[-1]}: {type(e).__name__}"
    raise RuntimeError(last)


def collect_binance(s: requests.Session, rounds: list[dict], gaps: list[str]):
    ones, fives = [], []
    for r in rounds:
        lock = r["lock_ts"]
        if not lock:
            continue
        try:
            for k in binance_klines(s, "1s", (lock - 90) * 1000, (lock + 10) * 1000):
                ones.append({"epoch": r["epoch"], "lock_ts": lock, "open_time_ms": k[0],
                             "close": k[4], "volume": k[5]})
        except Exception as e:  # noqa: BLE001
            gaps.append(f"binance 1s: epoch {r['epoch']} failed ({str(e)[:80]})")

    locks = [r["lock_ts"] for r in rounds if r["lock_ts"]]
    if locks:
        now_ms = int(time.time() * 1000)
        try:
            for k in binance_klines(s, "5m", (min(locks) - 1800) * 1000, now_ms):
                if k[6] < now_ms:  # only closed candles, so rows never need rewriting
                    fives.append(dict(zip(FILES["binance_5m"], [k[0], *k[1:6], k[6]])))
        except Exception as e:  # noqa: BLE001
            gaps.append(f"binance 5m: failed ({str(e)[:80]})")
    return ones, fives


# ---------- run ----------

def run() -> str:
    state = load_state()
    gaps: list[str] = []
    added = {k: 0 for k in FILES}
    rpc = RPC(RPCS)

    try:
        bets, latest = collect_bets(rpc, state, gaps)
        added["bets"] = append_rows("bets", bets)
        state["last_bet_block"] = latest
    except Exception as e:  # noqa: BLE001
        gaps.append(f"bets: step failed ({str(e)[:160]})")

    rounds = []
    try:
        rounds, safe = collect_rounds(rpc, state, gaps)
        added["rounds"] = append_rows("rounds", rounds)
        state["last_round_epoch"] = max(safe, state.get("last_round_epoch", safe))
    except Exception as e:  # noqa: BLE001
        gaps.append(f"rounds: step failed ({str(e)[:160]})")

    if rounds:
        ones, fives = collect_binance(requests.Session(), rounds, gaps)
        added["binance_1s"] = append_rows("binance_1s", ones)
        added["binance_5m"] = append_rows("binance_5m", fives)

    save_state(state)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "OK" if not gaps else ("PARTIAL" if any(added.values()) else "FAILED")
    line = (f"{stamp} {status} added "
            + " ".join(f"{k}={v}" for k, v in added.items())
            + f" | gaps={len(gaps)}" + (" | " + "; ".join(gaps) if gaps else ""))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "health.log").open("a") as f:
        f.write(line + "\n")
    return line


if __name__ == "__main__":
    print(run())
    sys.exit(0)
