#!/usr/bin/env python3
"""Data collector for PancakeSwap BNB Prediction research (BNB Chain, 5-minute rounds).

Run every 30 minutes. Each run appends (never rewrites) to the dataset in --data-dir:

  bets/YYYY-MM-DD.csv        BetBull/BetBear events from the last 90 min, de-duplicated by tx hash + log index
  rounds.csv                 every finished round since the last run, plus Chainlink publish times
  binance_1s/YYYY-MM-DD.csv  BNBUSDT 1-second closes from lock-90 s to lock+10 s for each new round
  binance_5m.csv             closed BNBUSDT 5-minute candles
  health.log                 one line per run: rows added, gaps, errors

Nothing is ever invented: if a source fails, the gap is logged and the run carries on.
Standard library only, so it runs on a bare GitHub Actions runner.
"""

import argparse
import csv
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

PREDICTION = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"
ORACLE = "0x0567F2323251f0Aab15c8dFb1967E4e8A7D42aeE"  # Chainlink BNB/USD proxy
RPCS = ["https://bsc.publicnode.com", "https://bsc-dataseed.binance.org"]
BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]

LOOKBACK_S = 90 * 60
MAX_CHUNK = 2000          # blocks per eth_getLogs call
MIN_CHUNK = 125           # stop splitting a failing range below this and log a gap
MAX_ROUNDS_PER_RUN = 500  # cap on round backfill after a long outage
PRE_LOCK_S, POST_LOCK_S = 90, 10
HTTP_TIMEOUT = 20


# --- Keccak-256 (Ethereum flavour, not NIST SHA3) for event topics and selectors ---

def _rol(v, n):
    n %= 64
    return ((v << n) | (v >> (64 - n))) & 0xFFFFFFFFFFFFFFFF


def _rc_bit(t):
    r = 1
    for _ in range(t % 255):
        r <<= 1
        if r & 0x100:
            r ^= 0x171
    return r & 1


_RC = [sum(_rc_bit(j + 7 * i) << (2 ** j - 1) for j in range(7)) for i in range(24)]
_ROT = [[0] * 5 for _ in range(5)]
_x, _y = 1, 0
for _t in range(24):
    _ROT[_x][_y] = ((_t + 1) * (_t + 2) // 2) % 64
    _x, _y = _y, (2 * _x + 3 * _y) % 5


def _keccak_f(a):
    for rnd in range(24):
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        a = [a[i] ^ d[i % 5] for i in range(25)]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(a[x + 5 * y], _ROT[x][y])
        a = [b[i] ^ (~b[(i + 1) % 5 + 5 * (i // 5)] & b[(i + 2) % 5 + 5 * (i // 5)]) for i in range(25)]
        a[0] ^= _RC[rnd]
    return a


def keccak256(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data) + b"\x01"
    msg += b"\x00" * (-len(msg) % rate)
    msg[-1] |= 0x80
    state = [0] * 25
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            state[i] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        state = _keccak_f(state)
    return b"".join(s.to_bytes(8, "little") for s in state)[:32]


def topic(sig):
    return "0x" + keccak256(sig.encode()).hex()


def selector(sig):
    return "0x" + keccak256(sig.encode())[:4].hex()


TOPIC_BULL = topic("BetBull(address,uint256,uint256)")
TOPIC_BEAR = topic("BetBear(address,uint256,uint256)")
SEL_CURRENT_EPOCH = selector("currentEpoch()")
SEL_ROUNDS = selector("rounds(uint256)")
SEL_ORACLE = selector("oracle()")
SEL_GET_ROUND_DATA = selector("getRoundData(uint80)")


# --- ABI helpers ---

def words(hexdata):
    h = hexdata[2:] if hexdata.startswith("0x") else hexdata
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def u256(w):
    return int(w, 16)


def i256(w):
    v = int(w, 16)
    return v - (1 << 256) if v >> 255 else v


def enc_uint(v):
    return format(v, "064x")


ROUND_FIELDS = ["epoch", "start_ts", "lock_ts", "close_ts", "lock_price", "close_price",
                "lock_oracle_id", "close_oracle_id", "total_amount", "bull_amount",
                "bear_amount", "reward_base_cal_amount", "reward_amount", "oracle_called"]


def decode_round(hexdata):
    w = words(hexdata)
    if len(w) < 14:
        raise ValueError(f"rounds() returned {len(w)} words, expected 14")
    out = {}
    for i, name in enumerate(ROUND_FIELDS):
        out[name] = i256(w[i]) if name in ("lock_price", "close_price") else u256(w[i])
    return out


def decode_round_data(hexdata):
    """Chainlink getRoundData -> (roundId, answer, startedAt, updatedAt, answeredInRound)."""
    w = words(hexdata)
    if len(w) < 5:
        raise ValueError("getRoundData returned short data")
    return {"round_id": u256(w[0]), "answer": i256(w[1]), "started_at": u256(w[2]),
            "updated_at": u256(w[3]), "answered_in_round": u256(w[4])}


def wei_to_bnb(wei):
    return str((Decimal(wei) / Decimal(10 ** 18)).normalize()) if wei else "0"


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


# --- transports ---

def http_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "content-type": "application/json", "user-agent": "prediction-collector/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read())


class RpcError(Exception):
    pass


class Rpc:
    """JSON-RPC with endpoint failover. `post` is injectable for tests."""

    def __init__(self, urls=RPCS, post=http_json):
        self.urls, self.post, self.used = list(urls), post, set()

    def _send(self, payload):
        errors = []
        for url in self.urls:
            try:
                res = self.post(url, payload)
                self.used.add(url)
                return res
            except Exception as e:  # network or HTTP failure: try the next endpoint
                errors.append(f"{url}: {e}")
        raise RpcError("; ".join(errors))

    def call(self, method, params):
        res = self._send({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" in res:
            raise RpcError(f"{method}: {res['error']}")
        return res["result"]

    def batch(self, calls):
        """[(method, params)] -> results in order. Falls back to single calls if batching is refused."""
        if not calls:
            return []
        payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
        try:
            res = self._send(payload)
            if isinstance(res, list) and len(res) == len(calls):
                by_id = {r["id"]: r for r in res}
                if all("result" in by_id.get(i, {}) for i in range(len(calls))):
                    return [by_id[i]["result"] for i in range(len(calls))]
        except RpcError:
            pass
        return [self.call(m, p) for m, p in calls]

    def eth_call(self, to, data):
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])


def binance_get(path, get=http_json):
    errors = []
    for host in BINANCE_HOSTS:
        try:
            return get(host + path)
        except Exception as e:
            errors.append(f"{host}: {e}")
    raise RuntimeError("; ".join(errors))


# --- dataset files ---

BET_COLS = ["block", "block_ts", "block_time_utc", "epoch", "side", "amount_wei", "amount_bnb",
            "sender", "tx_hash", "log_index"]
ROUND_COLS = ["epoch", "start_ts", "lock_ts", "close_ts", "lock_price", "close_price",
              "lock_oracle_id", "close_oracle_id", "lock_oracle_updated_at", "close_oracle_updated_at",
              "lock_oracle_answer", "close_oracle_answer", "total_amount_wei", "bull_amount_wei",
              "bear_amount_wei", "reward_base_cal_amount_wei", "reward_amount_wei", "oracle_called",
              "fetched_at"]
B1S_COLS = ["epoch", "lock_ts", "open_time_ms", "second_offset", "close"]
B5M_COLS = ["open_time_ms", "open_time_utc", "open", "high", "low", "close", "volume",
            "close_time_ms", "quote_volume", "trades"]


def append_rows(path, cols, rows):
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="raise")
        if new:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def read_column(path, col):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return [row[col] for row in csv.DictReader(f) if row.get(col)]


# --- collector ---

class Collector:
    def __init__(self, data_dir, rpc=None, binance=binance_get, now=None):
        self.dir = Path(data_dir)
        self.rpc = rpc or Rpc()
        self.binance = binance
        self.now = int(now if now is not None else time.time())
        self.gaps, self.errors = [], []
        self.added = {"bets": 0, "rounds": 0, "b1s": 0, "b5m": 0}
        self._ts_cache = {}

    def gap(self, msg):
        self.gaps.append(msg)

    def error(self, msg):
        self.errors.append(msg)

    # blocks
    def block_ts(self, numbers):
        need = [n for n in dict.fromkeys(numbers) if n not in self._ts_cache]
        for i in range(0, len(need), 100):
            part = need[i:i + 100]
            res = self.rpc.batch([("eth_getBlockByNumber", [hex(n), False]) for n in part])
            for n, blk in zip(part, res):
                if blk:
                    self._ts_cache[n] = int(blk["timestamp"], 16)
        return {n: self._ts_cache.get(n) for n in numbers}

    def first_block_at_or_after(self, target_ts, latest):
        lo, hi = max(0, latest - 1), latest
        step = 2000
        while lo > 0 and self.block_ts([lo])[lo] >= target_ts:
            hi, lo = lo, max(0, lo - step)
            step *= 2
        while lo < hi:
            mid = (lo + hi) // 2
            if self.block_ts([mid])[mid] < target_ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    # step 1
    def collect_bets(self):
        latest = int(self.rpc.call("eth_blockNumber", []), 16)
        start = self.first_block_at_or_after(self.now - LOOKBACK_S, latest)
        logs = []
        b = start
        while b <= latest:
            end = min(b + MAX_CHUNK - 1, latest)
            logs += self._get_logs(b, end)
            b = end + 1

        today, yday = day(self.now), day(self.now - 86400)
        seen = set()
        for d in {today, yday}:
            p = self.dir / "bets" / f"{d}.csv"
            if p.exists():
                with p.open(newline="") as f:
                    seen |= {(r["tx_hash"], r["log_index"]) for r in csv.DictReader(f)}

        fresh = []
        for lg in logs:
            key = (lg["transactionHash"].lower(), str(int(lg["logIndex"], 16)))
            if key in seen or lg.get("removed"):
                continue
            seen.add(key)
            fresh.append((key, lg))

        missing = [int(lg["blockNumber"], 16) for _, lg in fresh if "blockTimestamp" not in lg]
        ts_map = self.block_ts(missing) if missing else {}

        by_day = {}
        for (tx, li), lg in fresh:
            blk = int(lg["blockNumber"], 16)
            ts = int(lg["blockTimestamp"], 16) if "blockTimestamp" in lg else ts_map.get(blk)
            if ts is None:
                self.gap(f"bet {tx}:{li} block {blk} timestamp unavailable, row skipped")
                continue
            amount = u256(words(lg["data"])[0])
            by_day.setdefault(day(ts), []).append({
                "block": blk, "block_ts": ts, "block_time_utc": iso(ts),
                "epoch": u256(lg["topics"][2][2:]),
                "side": "bull" if lg["topics"][0].lower() == TOPIC_BULL else "bear",
                "amount_wei": amount, "amount_bnb": wei_to_bnb(amount),
                "sender": "0x" + lg["topics"][1][-40:], "tx_hash": tx, "log_index": li,
            })
        for d, rows in sorted(by_day.items()):
            rows.sort(key=lambda r: (r["block"], int(r["log_index"])))
            self.added["bets"] += append_rows(self.dir / "bets" / f"{d}.csv", BET_COLS, rows)

    def _get_logs(self, a, b):
        try:
            return self.rpc.call("eth_getLogs", [{
                "address": PREDICTION, "fromBlock": hex(a), "toBlock": hex(b),
                "topics": [[TOPIC_BULL, TOPIC_BEAR]]}])
        except RpcError as e:
            if b - a + 1 > MIN_CHUNK:
                mid = (a + b) // 2
                return self._get_logs(a, mid) + self._get_logs(mid + 1, b)
            self.gap(f"logs blocks {a}-{b} unavailable ({str(e)[:160]})")
            return []

    # step 2
    def collect_rounds(self):
        try:
            oracle_word = words(self.rpc.eth_call(PREDICTION, SEL_ORACLE))[0]
            on_chain = "0x" + oracle_word[-40:]
            if on_chain.lower() != ORACLE.lower():
                self.error(f"contract oracle() is {on_chain}, expected {ORACLE}; using on-chain value")
                oracle = on_chain
            else:
                oracle = ORACLE
        except Exception as e:
            self.error(f"oracle() check failed: {e}")
            oracle = ORACLE

        current = u256(words(self.rpc.eth_call(PREDICTION, SEL_CURRENT_EPOCH))[0])
        last_done = current - 2  # currentEpoch-2 is the newest round that executeRound has closed
        have = [int(e) for e in read_column(self.dir / "rounds.csv", "epoch")]
        first = (max(have) + 1) if have else last_done - LOOKBACK_S // 300 + 1
        if last_done - first + 1 > MAX_ROUNDS_PER_RUN:
            self.gap(f"rounds {first}-{last_done - MAX_ROUNDS_PER_RUN} skipped (backfill capped at {MAX_ROUNDS_PER_RUN})")
            first = last_done - MAX_ROUNDS_PER_RUN + 1
        epochs = list(range(max(first, 1), last_done + 1))
        if not epochs:
            return []

        raw = self.rpc.batch([("eth_call", [{"to": PREDICTION, "data": SEL_ROUNDS + enc_uint(e)}, "latest"])
                              for e in epochs])
        rounds = []
        for e, r in zip(epochs, raw):
            try:
                rounds.append(decode_round(r))
            except ValueError as ex:
                self.gap(f"round {e} undecodable: {ex}")

        oracle_ids = sorted({rid for r in rounds for rid in (r["lock_oracle_id"], r["close_oracle_id"]) if rid})
        published = {}
        if oracle_ids:
            try:
                res = self.rpc.batch([("eth_call", [{"to": oracle, "data": SEL_GET_ROUND_DATA + enc_uint(rid)}, "latest"])
                                      for rid in oracle_ids])
                for rid, hexdata in zip(oracle_ids, res):
                    try:
                        published[rid] = decode_round_data(hexdata)
                    except ValueError:
                        self.gap(f"oracle round {rid} getRoundData undecodable")
            except RpcError as e:
                self.gap(f"oracle publish times unavailable ({str(e)[:160]})")

        rows = []
        for r in rounds:
            lo, co = published.get(r["lock_oracle_id"], {}), published.get(r["close_oracle_id"], {})
            rows.append({
                "epoch": r["epoch"], "start_ts": r["start_ts"], "lock_ts": r["lock_ts"], "close_ts": r["close_ts"],
                "lock_price": r["lock_price"], "close_price": r["close_price"],
                "lock_oracle_id": r["lock_oracle_id"], "close_oracle_id": r["close_oracle_id"],
                "lock_oracle_updated_at": lo.get("updated_at", ""), "close_oracle_updated_at": co.get("updated_at", ""),
                "lock_oracle_answer": lo.get("answer", ""), "close_oracle_answer": co.get("answer", ""),
                "total_amount_wei": r["total_amount"], "bull_amount_wei": r["bull_amount"],
                "bear_amount_wei": r["bear_amount"], "reward_base_cal_amount_wei": r["reward_base_cal_amount"],
                "reward_amount_wei": r["reward_amount"], "oracle_called": r["oracle_called"],
                "fetched_at": self.now,
            })
            if not r["oracle_called"]:
                self.gap(f"round {r['epoch']} oracle_called=0 (cancelled or not executed)")
        self.added["rounds"] += append_rows(self.dir / "rounds.csv", ROUND_COLS, rows)
        return rows

    # step 3
    def collect_binance_1s(self, rounds):
        by_day = {}
        for r in rounds:
            lock = int(r["lock_ts"])
            if not lock:
                continue
            start_ms, end_ms = (lock - PRE_LOCK_S) * 1000, (lock + POST_LOCK_S) * 1000
            try:
                kl = self.binance(f"/api/v3/klines?symbol=BNBUSDT&interval=1s&startTime={start_ms}&endTime={end_ms}&limit=1000")
            except Exception as e:
                self.gap(f"binance 1s for epoch {r['epoch']} unavailable ({str(e)[:160]})")
                continue
            rows = [{"epoch": r["epoch"], "lock_ts": lock, "open_time_ms": k[0],
                     "second_offset": k[0] // 1000 - lock, "close": k[4]} for k in kl if start_ms <= k[0] <= end_ms]
            expected = PRE_LOCK_S + POST_LOCK_S + 1
            if len(rows) < expected:
                self.gap(f"binance 1s epoch {r['epoch']}: {len(rows)}/{expected} seconds")
            by_day.setdefault(day(lock), []).extend(rows)
        for d, rows in sorted(by_day.items()):
            self.added["b1s"] += append_rows(self.dir / "binance_1s" / f"{d}.csv", B1S_COLS, rows)

    def collect_binance_5m(self):
        path = self.dir / "binance_5m.csv"
        have = [int(v) for v in read_column(path, "open_time_ms")]
        start_ms = (max(have) + 300_000) if have else (self.now - LOOKBACK_S) // 300 * 300 * 1000
        now_ms = self.now * 1000
        rows = []
        while start_ms + 300_000 <= now_ms:
            try:
                kl = self.binance(f"/api/v3/klines?symbol=BNBUSDT&interval=5m&startTime={start_ms}&limit=1000")
            except Exception as e:
                self.gap(f"binance 5m from {iso(start_ms // 1000)} unavailable ({str(e)[:160]})")
                break
            closed = [k for k in kl if k[6] < now_ms and k[0] >= start_ms]
            rows += [{"open_time_ms": k[0], "open_time_utc": iso(k[0] // 1000), "open": k[1], "high": k[2],
                      "low": k[3], "close": k[4], "volume": k[5], "close_time_ms": k[6],
                      "quote_volume": k[7], "trades": k[8]} for k in closed]
            if len(kl) < 1000 or not closed:
                break
            start_ms = closed[-1][0] + 300_000
        self.added["b5m"] += append_rows(path, B5M_COLS, rows)

    # orchestration
    def run(self):
        rounds = []
        for name, step in [("bets", self.collect_bets), ("rounds", self.collect_rounds)]:
            try:
                out = step()
                if name == "rounds":
                    rounds = out or []
            except Exception as e:
                self.error(f"{name}: {type(e).__name__}: {str(e)[:200]}")
        for name, step in [("binance_1s", lambda: self.collect_binance_1s(rounds)),
                           ("binance_5m", self.collect_binance_5m)]:
            try:
                step()
            except Exception as e:
                self.error(f"{name}: {type(e).__name__}: {str(e)[:200]}")
        return self.write_health()

    def write_health(self):
        a = self.added
        status = "ok" if not self.gaps and not self.errors else ("error" if self.errors else "gaps")
        runner = "github-actions" if os.environ.get("GITHUB_ACTIONS") else socket.gethostname()
        detail = " | ".join(self.errors + self.gaps)
        line = (f"{iso(self.now)} {status} bets+{a['bets']} rounds+{a['rounds']} b1s+{a['b1s']} "
                f"b5m+{a['b5m']} gaps={len(self.gaps)} errors={len(self.errors)} runner={runner}"
                + (f" | {detail}" if detail else ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / "health.log").open("a") as f:
            f.write(line.replace("\n", " ") + "\n")
        return line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    args = ap.parse_args(argv)
    print(Collector(args.data_dir).run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
