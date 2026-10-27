#!/usr/bin/env python3
"""Live Flagger for PancakeSwap BNB Prediction (flags only, read-only).

Signal (as specified by the user, 2026-10-27):
  - Decision moment: 3 s before the next round locks, clock synced to Binance server time.
  - Chainlink price = latest published update. SKIP if (Chainlink age + seconds to lock) > 25 s.
  - offset = median(Chainlink - Binance) over the last 30 oracle updates.
  - gapN   = (Binance + offset - Chainlink) / ATR14(5m).
  - UP if gapN >= +0.38, DOWN if gapN <= -0.38, else NO_CALL.
Every round is logged with all raw inputs (also non-calls). After a round resolves,
the flag is scored against the on-chain result (closePrice vs lockPrice; tie = wrong).

SAFETY: this script never signs or sends transactions. It only uses eth_call and
public Binance market-data endpoints. There is no private key anywhere in this code.

Stdlib only. Usage:
  python3 flagger.py run                 # live loop
  python3 flagger.py summary             # hit-rate summary from the log
  python3 flagger.py selftest            # offline math checks
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

PREDICTION = "0x18B2A687610328590Bc8F2e5fEdDe3b582A49cdA"  # PancakeSwap Prediction V2 (BNB)
SEL = {
    "currentEpoch": "0x76671808",
    "rounds": "0x8c65c81f",
    "oracle": "0x7dc0d1d0",
    "latestRoundData": "0xfeaf968c",
    "getRoundData": "0x9a6fc8f5",
    "decimals": "0x313ce567",
}

LEAD_S = 3.0
MAX_STALENESS_S = 25.0
OFFSET_N = 30
ATR_N = 14
THRESH = 0.38
RESOLVE_GRACE_S = 120  # after closeTimestamp, how long to wait before calling a round cancelled

RPC = os.environ.get("BSC_RPC", "https://bsc-dataseed.bnbchain.org")
BINANCE = os.environ.get("BINANCE_API", "https://data-api.binance.vision")
SYMBOL = "BNBUSDT"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.environ.get("FLAGGER_LOG", os.path.join(HERE, "flags.jsonl"))
CACHE = os.environ.get("FLAGGER_CACHE", os.path.join(HERE, "offset_cache.json"))


# ---------- pure signal math (tested by selftest) ----------

def true_ranges(klines):
    """klines: list of (high, low, close) oldest->newest. Returns TRs from the 2nd candle on."""
    out = []
    for prev, cur in zip(klines, klines[1:]):
        h, l, pc = cur[0], cur[1], prev[2]
        out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def atr(klines, n=ATR_N):
    """Simple mean of the last n true ranges over closed candles (needs n+1 candles)."""
    tr = true_ranges(klines)
    if len(tr) < n:
        raise ValueError(f"need {n + 1} closed candles, got {len(klines)}")
    return sum(tr[-n:]) / n


def gap_n(binance, offset, chainlink, atr_value):
    return (binance + offset - chainlink) / atr_value


def decide(gap, cl_age, secs_to_lock):
    if cl_age + secs_to_lock > MAX_STALENESS_S:
        return "SKIP"
    if gap >= THRESH:
        return "UP"
    if gap <= -THRESH:
        return "DOWN"
    return "NO_CALL"


def outcome(lock_price, close_price):
    if close_price > lock_price:
        return "UP"
    if close_price < lock_price:
        return "DOWN"
    return "TIE"


def score(flag, result):
    """True/False for UP/DOWN flags; None for non-calls or cancelled rounds. Tie = wrong."""
    if flag not in ("UP", "DOWN") or result == "CANCELLED":
        return None
    return flag == result


# ---------- IO ----------

def http_json(url, payload=None, timeout=10):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json",
                                                          "user-agent": "live-flagger/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def eth_call(to, data):
    res = http_json(RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                          "params": [{"to": to, "data": data}, "latest"]})
    if "error" in res:
        raise RuntimeError(res["error"])
    raw = res["result"][2:]
    return [int(raw[i:i + 64], 16) for i in range(0, len(raw), 64)]


def signed(x):
    return x - (1 << 256) if x >= 1 << 255 else x


def arg(n):
    return format(n, "064x")


class Chain:
    def __init__(self):
        self.oracle = "0x" + format(eth_call(PREDICTION, SEL["oracle"])[0], "040x")
        self.decimals = eth_call(self.oracle, SEL["decimals"])[0]

    def current_epoch(self):
        return eth_call(PREDICTION, SEL["currentEpoch"])[0]

    def round(self, epoch):
        w = eth_call(PREDICTION, SEL["rounds"] + arg(epoch))
        return {"epoch": w[0], "startTimestamp": w[1], "lockTimestamp": w[2], "closeTimestamp": w[3],
                "lockPrice": signed(w[4]), "closePrice": signed(w[5]),
                "lockOracleId": w[6], "closeOracleId": w[7], "oracleCalled": bool(w[13])}

    def _rd(self, w):
        return {"roundId": w[0], "answer": signed(w[1]) / 10 ** self.decimals, "updatedAt": w[3]}

    def latest(self):
        return self._rd(eth_call(self.oracle, SEL["latestRoundData"]))

    def get_round(self, rid):
        return self._rd(eth_call(self.oracle, SEL["getRoundData"] + arg(rid)))


class Binance:
    def __init__(self):
        self.clock_offset = 0.0  # binance_time - local_time, seconds

    def sync(self):
        t0 = time.time()
        st = http_json(f"{BINANCE}/api/v3/time")["serverTime"] / 1000
        t1 = time.time()
        self.clock_offset = st - (t0 + t1) / 2
        return {"rtt_ms": round((t1 - t0) * 1000, 1), "clock_offset_s": round(self.clock_offset, 4)}

    def now(self):
        return time.time() + self.clock_offset

    def price(self):
        return float(http_json(f"{BINANCE}/api/v3/ticker/price?symbol={SYMBOL}")["price"])

    def closed_5m(self, n):
        rows = http_json(f"{BINANCE}/api/v3/klines?symbol={SYMBOL}&interval=5m&limit={n + 1}")
        now_ms = self.now() * 1000
        rows = [r for r in rows if r[6] < now_ms][-n:]  # drop the still-open candle
        return [{"openTime": r[0], "high": float(r[2]), "low": float(r[3]), "close": float(r[4])} for r in rows]

    def price_at(self, ts):
        """Close of the 1s candle that contains unix second ts."""
        rows = http_json(f"{BINANCE}/api/v3/klines?symbol={SYMBOL}&interval=1s&startTime={ts * 1000}&limit=1")
        return float(rows[0][4]) if rows else None


def load_cache():
    try:
        with open(CACHE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


def save_cache(c):
    keep = dict(sorted(c.items())[-200:])
    with open(CACHE, "w") as f:
        json.dump(keep, f)


def offset_samples(chain, bn, latest, cache):
    """Last OFFSET_N oracle updates paired with Binance at the same second."""
    samples, rid = [], latest["roundId"]
    for _ in range(OFFSET_N * 2):
        if len(samples) >= OFFSET_N:
            break
        if rid not in cache:
            try:
                rd = latest if rid == latest["roundId"] else chain.get_round(rid)
            except RuntimeError:
                break  # reverted: start of the aggregator phase
            if rd["updatedAt"] == 0:
                break  # walked off the start of the aggregator phase
            cache[rid] = {"chainlink": rd["answer"], "updatedAt": rd["updatedAt"],
                          "binance": bn.price_at(rd["updatedAt"])}
        s = cache[rid]
        if s["binance"] is not None:
            samples.append({"roundId": rid, **s})
        rid -= 1
    return samples


def log(rec):
    rec["logged_at"] = datetime.now(timezone.utc).isoformat()
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


def read_log():
    try:
        with open(LOG) as f:
            return [json.loads(l) for l in f if l.strip()]
    except OSError:
        return []


def resolve_pending(chain, bn, pending):
    for epoch in sorted(pending):
        dec = pending[epoch]
        rd = chain.round(epoch)
        if rd["oracleCalled"]:
            res = outcome(rd["lockPrice"], rd["closePrice"])
        elif bn.now() > rd["closeTimestamp"] + RESOLVE_GRACE_S and rd["closeTimestamp"]:
            res = "CANCELLED"
        else:
            continue
        log({"type": "result", "epoch": epoch, "flag": dec["flag"], "result": res,
             "correct": score(dec["flag"], res),
             "lockPrice_raw": rd["lockPrice"], "closePrice_raw": rd["closePrice"],
             "lockOracleId": rd["lockOracleId"], "closeOracleId": rd["closeOracleId"],
             "lockTimestamp": rd["lockTimestamp"], "closeTimestamp": rd["closeTimestamp"]})
        del pending[epoch]


def run():
    chain, bn = Chain(), Binance()
    print(f"oracle={chain.oracle} decimals={chain.decimals} rpc={RPC} log={LOG}", flush=True)
    done = {r["epoch"] for r in read_log() if r.get("type") == "decision"}
    scored = {r["epoch"] for r in read_log() if r.get("type") == "result"}
    pending = {r["epoch"]: r for r in read_log() if r.get("type") == "decision" and r["epoch"] not in scored}
    cache = load_cache()
    while True:
        try:
            resolve_pending(chain, bn, pending)
            epoch = chain.current_epoch()
            rd = chain.round(epoch)
            if epoch in done:
                time.sleep(5)
                continue
            sync = bn.sync()
            wait = rd["lockTimestamp"] - LEAD_S - bn.now()
            if wait < -1.0:  # started too late for this round's decision moment
                done.add(epoch)
                log({"type": "missed", "epoch": epoch, "lockTimestamp": rd["lockTimestamp"],
                     "late_by_s": round(-wait, 3)})
                continue
            if wait > 20:
                time.sleep(wait - 15)
                continue
            # pre-fetch slow inputs, then fine-sync and fire at lock - 3 s
            klines = bn.closed_5m(ATR_N + 1)
            offset_samples(chain, bn, chain.latest(), cache)  # warm cache; decision call adds at most a few
            sync = bn.sync()
            time.sleep(max(0.0, rd["lockTimestamp"] - LEAD_S - bn.now()))

            t_decision = bn.now()
            binance_px = bn.price()
            latest = chain.latest()
            t_inputs_done = bn.now()
            samples = offset_samples(chain, bn, latest, cache)
            save_cache(cache)

            diffs = [s["chainlink"] - s["binance"] for s in samples]
            offset = statistics.median(diffs) if diffs else None
            atr_v = atr([(k["high"], k["low"], k["close"]) for k in klines])
            secs_to_lock = rd["lockTimestamp"] - t_decision
            cl_age = t_decision - latest["updatedAt"]
            gap = gap_n(binance_px, offset, latest["answer"], atr_v) if offset is not None and atr_v > 0 else None
            if gap is None:
                flag = "NO_CALL"
            else:
                flag = decide(gap, cl_age, secs_to_lock)
            rec = {"type": "decision", "epoch": epoch,
                   "timestamp": datetime.fromtimestamp(t_decision, timezone.utc).isoformat(),
                   "decision_unix": round(t_decision, 3), "gapN": None if gap is None else round(gap, 5),
                   "chainlink_age_s": round(cl_age, 3), "flag": flag,
                   "raw": {"binance_price": binance_px, "chainlink_price": latest["answer"],
                           "chainlink_roundId": latest["roundId"], "chainlink_updatedAt": latest["updatedAt"],
                           "offset": offset, "offset_n": len(diffs), "offset_samples": samples,
                           "atr14_5m": atr_v, "atr_klines": klines,
                           "lockTimestamp": rd["lockTimestamp"], "startTimestamp": rd["startTimestamp"],
                           "secs_to_lock": round(secs_to_lock, 3),
                           "staleness_sum_s": round(cl_age + secs_to_lock, 3),
                           "input_fetch_s": round(t_inputs_done - t_decision, 3),
                           "clock_sync": sync, "thresh": THRESH, "max_staleness_s": MAX_STALENESS_S}}
            log(rec)
            done.add(epoch)
            pending[epoch] = rec
        except KeyboardInterrupt:
            raise
        except Exception as e:  # keep running; log the failure so gaps are visible
            log({"type": "error", "error": repr(e)})
            time.sleep(5)


def summary():
    recs = read_log()
    dec = {r["epoch"]: r for r in recs if r.get("type") == "decision"}
    res = {r["epoch"]: r for r in recs if r.get("type") == "result"}
    counts = {}
    for d in dec.values():
        counts[d["flag"]] = counts.get(d["flag"], 0) + 1
    calls = [r for r in res.values() if r["correct"] is not None]
    wins = sum(r["correct"] for r in calls)
    print(f"decisions: {len(dec)}  by flag: {counts}")
    print(f"resolved: {len(res)}  scored calls: {len(calls)}  correct: {wins}  "
          f"hit rate: {wins / len(calls):.3f}" if calls else "no scored calls yet")
    for side in ("UP", "DOWN"):
        s = [r for r in calls if r["flag"] == side]
        if s:
            print(f"  {side}: {sum(r['correct'] for r in s)}/{len(s)}")
    nc = [r for r in res.values() if r["flag"] in ("NO_CALL", "SKIP")]
    if nc:
        dist = {}
        for r in nc:
            dist[r["result"]] = dist.get(r["result"], 0) + 1
        print(f"non-call outcomes: {dist}")


def selftest():
    k = [(10, 8, 9), (11, 9, 10), (10.5, 9.5, 10)]
    assert true_ranges(k) == [2, 1]
    assert true_ranges([(10, 9, 9.5), (12, 11, 11.5)]) == [2.5]  # gap up uses prev close
    k15 = [(100 + i, 99 + i, 99.5 + i) for i in range(15)]
    assert abs(atr(k15) - 1.5) < 1e-12
    assert abs(gap_n(600.0, 0.2, 599.81, 1.0) - 0.39) < 1e-9
    assert decide(0.38, 10, 3) == "UP" and decide(-0.38, 10, 3) == "DOWN"
    assert decide(0.379, 10, 3) == "NO_CALL" and decide(5, 22.1, 3) == "SKIP"
    assert decide(5, 22, 3) == "UP"  # exactly 25 s is allowed
    assert outcome(100, 101) == "UP" and outcome(100, 99) == "DOWN" and outcome(100, 100) == "TIE"
    assert score("UP", "TIE") is False and score("DOWN", "TIE") is False
    assert score("NO_CALL", "UP") is None and score("UP", "CANCELLED") is None
    assert statistics.median([0.1, 0.3, -0.2]) == 0.1
    print("selftest ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["run", "summary", "selftest"])
    {"run": run, "summary": summary, "selftest": selftest}[p.parse_args().cmd]()
