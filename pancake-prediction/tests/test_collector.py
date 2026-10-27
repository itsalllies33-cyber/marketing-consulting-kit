"""Offline tests for the prediction collector: fake chain + fake Binance, no network."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collector as c  # noqa: E402

NOW = 1_800_000_000
LATEST = 6000          # one block per second, block n has ts NOW - LATEST + n
CURRENT_EPOCH = 1000


def ts_of(n):
    return NOW - LATEST + n


def word(v):
    return format(v % (1 << 256), "064x")


def round_hex(e):
    lock = NOW - (CURRENT_EPOCH - e) * 300
    vals = [e, lock - 300, lock, lock + 300, 600_00000000 + e, 601_00000000 + e,
            10 * e, 10 * e + 1, 3 * 10 ** 18, 2 * 10 ** 18, 10 ** 18, 0, 0, 1]
    return "0x" + "".join(word(v) for v in vals)


class FakeChain:
    def __init__(self, logs, getlogs_max=None, fail_below=None):
        self.logs, self.getlogs_max, self.fail_below = logs, getlogs_max, fail_below
        self.getlogs_calls = []

    def handle(self, req):
        m, p = req["method"], req["params"]
        if m == "eth_blockNumber":
            return hex(LATEST)
        if m == "eth_getBlockByNumber":
            return {"timestamp": hex(ts_of(int(p[0], 16)))}
        if m == "eth_getLogs":
            a, b = int(p[0]["fromBlock"], 16), int(p[0]["toBlock"], 16)
            self.getlogs_calls.append((a, b))
            if self.getlogs_max and b - a + 1 > self.getlogs_max:
                raise c.RpcError("range too large")
            if self.fail_below is not None and a < self.fail_below:
                raise c.RpcError("history pruned")
            return [lg for lg in self.logs if a <= int(lg["blockNumber"], 16) <= b]
        if m == "eth_call":
            to, data = p[0]["to"].lower(), p[0]["data"]
            if data == c.SEL_ORACLE:
                return "0x" + "0" * 24 + c.ORACLE[2:].lower()
            if data == c.SEL_CURRENT_EPOCH:
                return "0x" + word(CURRENT_EPOCH)
            if data.startswith(c.SEL_ROUNDS):
                return round_hex(int(data[10:], 16))
            if to == c.ORACLE.lower() and data.startswith(c.SEL_GET_ROUND_DATA):
                rid = int(data[10:], 16)
                return "0x" + "".join(word(v) for v in [rid, 600_00000000, 1000 + rid, 2000 + rid, rid])
        raise AssertionError(f"unexpected {m} {p}")

    def post(self, url, payload):
        if isinstance(payload, list):
            return [{"jsonrpc": "2.0", "id": r["id"], "result": self.handle(r)} for r in payload]
        try:
            return {"jsonrpc": "2.0", "id": 1, "result": self.handle(payload)}
        except c.RpcError as e:
            return {"jsonrpc": "2.0", "id": 1, "error": {"message": str(e)}}


def make_log(block, idx, side, epoch, amount, tx="0xabc"):
    t = c.TOPIC_BULL if side == "bull" else c.TOPIC_BEAR
    return {"blockNumber": hex(block), "logIndex": hex(idx), "transactionHash": f"{tx}{block:06d}",
            "topics": [t, "0x" + "0" * 24 + "11" * 20, "0x" + word(epoch)], "data": "0x" + word(amount)}


def binance_at(now):
    """Fake Binance whose newest candle is the one still open at `now` (like the real API)."""
    def get(path):
        q = dict(kv.split("=") for kv in path.split("?")[1].split("&"))
        step = 1000 if q["interval"] == "1s" else 300_000
        start = int(q["startTime"])
        end = min(int(q.get("endTime", now * 1000)), now * 1000)
        out, t = [], start
        while t <= end and len(out) < 1000:
            out.append([t, "600.1", "600.5", "599.9", "600.2", "10", t + step - 1, "6000", 42])
            t += step
        return out
    return get


fake_binance = binance_at(NOW)


def rows(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def test_keccak_known_vectors():
    assert c.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert c.topic("Transfer(address,address,uint256)") == \
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert c.selector("balanceOf(address)") == "0x70a08231"
    assert c.keccak256(b"a" * 200) != c.keccak256(b"a" * 201)  # multi-block absorb


def test_signed_price_decode():
    assert c.i256(word(-5)) == -5
    r = c.decode_round(round_hex(990))
    assert r["epoch"] == 990 and r["lock_price"] == 600_00000990 and r["oracle_called"] == 1


def test_full_run_appends_and_dedupes(tmp_path):
    logs = [make_log(5990, 0, "bull", 999, 10 ** 17), make_log(5995, 3, "bear", 999, 5 * 10 ** 16),
            make_log(100, 1, "bull", 980, 1)]  # block 100 is outside the 90-minute window
    chain = FakeChain(logs)
    col = c.Collector(tmp_path, rpc=c.Rpc(urls=["fake"], post=chain.post), binance=fake_binance, now=NOW)
    line = col.run()
    assert "errors=0" in line, line

    bets = rows(tmp_path / "bets" / f"{c.day(NOW)}.csv")
    assert [(b["side"], b["amount_bnb"], b["epoch"]) for b in bets] == [("bull", "0.1", "999"), ("bear", "0.05", "999")]
    assert bets[0]["block_ts"] == str(ts_of(5990))
    assert all(b - a + 1 <= c.MAX_CHUNK for a, b in chain.getlogs_calls)

    rnds = rows(tmp_path / "rounds.csv")
    assert [int(r["epoch"]) for r in rnds] == list(range(981, 999))  # 18 rounds = 90 min, ending at current-2
    assert rnds[0]["lock_oracle_updated_at"] == str(2000 + 9810)

    b1s = rows(tmp_path / "binance_1s" / f"{c.day(int(rnds[0]['lock_ts']))}.csv")
    assert len(b1s) == 18 * 101
    assert {int(r["second_offset"]) for r in b1s} == set(range(-90, 11))
    assert len(rows(tmp_path / "binance_5m.csv")) == 18

    # second run 30 minutes later, same logs still visible: no duplicates, only new rounds
    global CURRENT_EPOCH
    CURRENT_EPOCH += 6
    try:
        c.Collector(tmp_path, rpc=c.Rpc(urls=["fake"], post=chain.post), binance=binance_at(NOW + 1800), now=NOW + 1800).run()
    finally:
        CURRENT_EPOCH -= 6
    assert len(rows(tmp_path / "bets" / f"{c.day(NOW)}.csv")) == 2
    assert [int(r["epoch"]) for r in rows(tmp_path / "rounds.csv")][-6:] == list(range(999, 1005))
    b5m = [int(r["open_time_ms"]) for r in rows(tmp_path / "binance_5m.csv")]
    assert len(b5m) == len(set(b5m)) == 24
    assert len((tmp_path / "health.log").read_text().splitlines()) == 2


def test_oversized_chunks_split_and_pruned_ranges_logged(tmp_path):
    chain = FakeChain([make_log(5990, 0, "bull", 999, 1)], getlogs_max=500, fail_below=2000)
    col = c.Collector(tmp_path, rpc=c.Rpc(urls=["fake"], post=chain.post), binance=fake_binance, now=NOW)
    col.collect_bets()
    assert col.added["bets"] == 1
    assert any("unavailable" in g for g in col.gaps)
    assert all(b < 2000 for g in col.gaps for b in [int(g.split()[2].split("-")[0])])


def test_all_sources_down_logs_gaps_writes_no_data(tmp_path):
    def down(*_):
        raise OSError("blocked")
    col = c.Collector(tmp_path, rpc=c.Rpc(urls=["a", "b"], post=down), binance=down, now=NOW)
    line = col.run()
    assert line.split()[1] == "error" and "bets+0 rounds+0 b1s+0 b5m+0" in line
    assert sorted(p.name for p in tmp_path.iterdir()) == ["health.log"]
