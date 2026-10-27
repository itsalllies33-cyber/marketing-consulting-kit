import csv
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def col(tmp_path, monkeypatch):
    monkeypatch.setenv("PRED_DATA_DIR", str(tmp_path))
    import collector
    importlib.reload(collector)
    monkeypatch.setattr(collector.time, "sleep", lambda *_: None)
    return collector


def w(v):
    return format(v % (1 << 256), "064x")


def test_selectors_match_known_values(col):
    assert col.SEL_GET_ROUND_DATA == "0x9a6fc8f5"
    assert col.SEL_ROUNDS == "0x8c65c81f"
    assert col.SEL_CURRENT_EPOCH == "0x76671808"


def test_decode_round_handles_negative_price(col):
    vals = [100, 1, 2, 3, -5, 73600000000, 7, 8, 30, 20, 10, 29, 28, 1]
    r = col.decode_round("0x" + "".join(w(v) for v in vals))
    assert r["lock_price"] == -5 and r["close_price"] == 73600000000
    assert r["bull_wei"] == 20 and r["oracle_called"] is True


def test_decode_bet_log(col):
    log = {"topics": [col.TOPIC_BEAR, "0x" + "0" * 24 + "ab" * 20, "0x" + w(42)],
           "data": "0x" + w(5 * 10**17), "transactionHash": "0xAA", "logIndex": "0x3",
           "blockNumber": "0x10"}
    r = col.decode_bet_log(log)
    assert r == {"tx_hash": "0xaa", "log_index": 3, "block": 16, "epoch": 42, "side": "bear",
                 "sender": "0x" + "ab" * 20, "amount_wei": 5 * 10**17}


def test_append_is_deduplicated_and_never_rewrites(col):
    row = {k: "x" for k in col.FILES["bets"]}
    assert col.append_rows("bets", [row, dict(row)]) == 1
    first = (col.DATA_DIR / "bets.csv").read_text()
    assert col.append_rows("bets", [row]) == 0
    assert (col.DATA_DIR / "bets.csv").read_text() == first
    other = dict(row, log_index="y")
    assert col.append_rows("bets", [other]) == 1
    assert (col.DATA_DIR / "bets.csv").read_text().startswith(first)


class FakeChain:
    """Minimal JSON-RPC responder: blocks 1000..3000, 1 s apart, one bet, epoch 50 current."""

    def __init__(self, col, fail_logs=False):
        self.col, self.fail_logs = col, fail_logs

    def handle(self, req):
        m, p = req["method"], req["params"]
        if m == "eth_getBlockByNumber":
            n = 3000 if p[0] == "latest" else int(p[0], 16)
            return {"number": hex(n), "timestamp": hex(1_700_000_000 + n)}
        if m == "eth_getLogs":
            if self.fail_logs:
                return {"__error__": "history pruned"}
            a, b = int(p[0]["fromBlock"], 16), int(p[0]["toBlock"], 16)
            if a <= 2500 <= b:
                return [{"topics": [self.col.TOPIC_BULL, "0x" + "0" * 64, "0x" + w(49)],
                         "data": "0x" + w(10**18), "transactionHash": "0xbeef",
                         "logIndex": "0x0", "blockNumber": hex(2500)}]
            return []
        if m == "eth_call":
            to, data = p[0]["to"], p[0]["data"]
            if data == self.col.SEL_CURRENT_EPOCH:
                return "0x" + w(50)
            if data.startswith(self.col.SEL_ROUNDS):
                e = int(data[10:], 16)
                return "0x" + "".join(w(v) for v in [e, 10, 1_700_000_000 + e * 300,
                                                     1_700_000_300 + e * 300, 600_00000000,
                                                     601_00000000, e * 10, e * 10 + 1,
                                                     3, 2, 1, 3, 3, 1])
            if data.startswith(self.col.SEL_GET_ROUND_DATA):
                rid = int(data[10:], 16)
                return "0x" + "".join(w(v) for v in [rid, 1, 5, 1_000 + rid, rid])
        raise AssertionError(req)

    def post(self, payload):
        def one(req):
            res = self.handle(req)
            if isinstance(res, dict) and "__error__" in res:
                return {"jsonrpc": "2.0", "id": req["id"], "error": {"message": res["__error__"]}}
            return {"jsonrpc": "2.0", "id": req["id"], "result": res}
        return [one(r) for r in payload] if isinstance(payload, list) else one(payload)


def fake_klines(_s, interval, start_ms, end_ms):
    step = 1000 if interval == "1s" else 300_000
    return [[t, "1", "2", "0.5", "1.5", "9", t + step - 1] for t in range(start_ms, end_ms + 1, step)][:5]


def run_with(col, monkeypatch, chain):
    monkeypatch.setattr(col.RPC, "_post", lambda self, payload: chain.post(payload))
    monkeypatch.setattr(col, "binance_klines", fake_klines)
    return col.run()


def read(col, name):
    with (col.DATA_DIR / f"{name}.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def test_full_run_then_rerun_appends_nothing_new(col, monkeypatch):
    chain = FakeChain(col)
    line = run_with(col, monkeypatch, chain)
    assert " OK " in line and "bets=1" in line and "rounds=18" in line
    bet = read(col, "bets")[0]
    assert bet["block_ts"] == str(1_700_002_500) and bet["amount_bnb"] == "1"
    r = read(col, "rounds")[-1]
    assert r["epoch"] == "48" and r["lock_oracle_updated_at"] == str(1_000 + 480)

    line2 = run_with(col, monkeypatch, chain)
    assert "bets=0 rounds=0" in line2
    assert len((col.DATA_DIR / "health.log").read_text().splitlines()) == 2


def test_failed_source_is_logged_not_invented(col, monkeypatch):
    line = run_with(col, monkeypatch, FakeChain(col, fail_logs=True))
    assert "PARTIAL" in line and "getLogs" in line and "bets=0" in line
    assert not (col.DATA_DIR / "bets.csv").exists()
    assert len(read(col, "rounds")) == 18


def test_total_outage_logs_failure(col, monkeypatch):
    def down(self, payload):
        raise RuntimeError("all RPCs failed")
    monkeypatch.setattr(col.RPC, "_post", down)
    line = col.run()
    assert line.split()[1] == "FAILED" and "gaps=2" in line
