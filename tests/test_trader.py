"""Offline tests for the trader monitor — sample fixtures only, no network, no keys."""
import json
import os
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from trader import greeks, layer3_context, monitor  # noqa: E402
from trader.providers import FixtureProvider  # noqa: E402

FIX = os.path.join(ROOT, "trader", "fixtures")
PORTFOLIO = os.path.join(ROOT, "trader", "portfolio.example.json")


def load_portfolio():
    with open(PORTFOLIO, encoding="utf-8") as f:
        return json.load(f)


# --- Black-Scholes ------------------------------------------------------------

def test_bs_textbook_value():
    # Hull: S=42, K=40, r=10%, sigma=20%, T=0.5 -> call 4.76, put 0.81
    assert greeks.bs_price("call", 42, 40, 0.5, 0.10, 0.20) == pytest.approx(4.76, abs=0.01)
    assert greeks.bs_price("put", 42, 40, 0.5, 0.10, 0.20) == pytest.approx(0.81, abs=0.01)


def test_greeks_signs_and_parity():
    c = greeks.greeks("call", 100, 100, 1, 0.04, 0.3)
    p = greeks.greeks("put", 100, 100, 1, 0.04, 0.3)
    assert 0 < c["delta"] < 1 and -1 < p["delta"] < 0
    assert c["delta"] - p["delta"] == pytest.approx(1, abs=1e-9)
    assert c["theta"] < 0 and c["gamma"] > 0 and c["vega"] > 0
    assert c["gamma"] == pytest.approx(p["gamma"])


def test_implied_vol_round_trip():
    price = greeks.bs_price("call", 50, 55, 0.75, 0.04, 0.47)
    assert greeks.implied_vol("call", price, 50, 55, 0.75, 0.04) == pytest.approx(0.47, abs=1e-4)
    assert greeks.implied_vol("call", 0.0, 50, 55, 0.75, 0.04) is None


# --- Technicals -----------------------------------------------------------------

def test_rsi_bounds():
    assert layer3_context.rsi([float(i) for i in range(1, 40)]) == 100.0
    flat_down = [100 - i for i in range(40)]
    assert layer3_context.rsi(flat_down) == pytest.approx(0.0, abs=1e-9)


def test_parse_review_extracts_json_and_sanitises_actions():
    text = 'Sure:\n{"book": "ok", "positions": {"A": {"action": "YOLO"}, "B": {"action": "trim"}}}\nthanks'
    data = layer3_context.parse_review(text)
    assert data["positions"]["A"]["action"] == "watch"
    assert data["positions"]["B"]["action"] == "trim"


# --- Full pipeline ----------------------------------------------------------------

@pytest.fixture
def two_day_run(tmp_path):
    pf = load_portfolio()
    monitor.run(pf, FixtureProvider(os.path.join(FIX, "day1.json")), date(2026, 10, 26), str(tmp_path), "off")
    return monitor.run(pf, FixtureProvider(os.path.join(FIX, "day2.json")), date(2026, 10, 27), str(tmp_path), "dry-run"), tmp_path


def test_day2_alerts(two_day_run):
    res, _ = two_day_run
    kinds = {(a["ticker"], a["kind"]) for a in res["alerts"]}
    assert ("HIMS", "target") in kinds       # deep ITM call past +100%
    assert ("HIMS", "dte") in kinds          # 38 DTE < 45
    assert ("NBIS", "iv_move") in kinds      # IV 62% -> 71%
    assert ("HIMS", "new_strike") in kinds   # 42.5 listed on day 2
    assert ("NOK", "new_expiry") in kinds    # 2027-03-19 listed on day 2
    assert res["alerts"][0]["severity"] == "action"


def test_first_day_has_no_diff_alerts(tmp_path):
    res = monitor.run(load_portfolio(), FixtureProvider(os.path.join(FIX, "day2.json")),
                      date(2026, 10, 27), str(tmp_path), "off")
    assert not [a for a in res["alerts"] if a["kind"] in ("new_strike", "new_expiry", "iv_move")]


def test_nav_and_greeks_consistent(two_day_run):
    res, _ = two_day_run
    a, pos = res["analytics"], res["valuation"]["positions"]
    assert a["nav"] == pytest.approx(a["cash"] + sum(p["market_value"] for p in pos))
    assert a["greeks"]["theta_day"] < 0                     # long options bleed
    assert sum(a["allocation_sector"].values()) == pytest.approx(100)
    assert len(a["nav_curve"]) == 2


def test_outputs_written(two_day_run):
    res, out = two_day_run
    html = (out / "dashboard.html").read_text(encoding="utf-8")
    for section in ("Active alerts", "Theta decay", "Strike ladder", "Aggregate Greeks", "Macro gate"):
        assert section in html
    assert (out / "snapshots" / "2026-10-26.json").exists()
    prompt = (out / "review_prompt.txt").read_text(encoding="utf-8")
    assert "HIMS-30C-2026-12" in prompt and "Return ONLY JSON" in prompt


def test_rerun_same_day_is_idempotent(tmp_path):
    pf, fx = load_portfolio(), os.path.join(FIX, "day2.json")
    first = monitor.run(pf, FixtureProvider(fx), date(2026, 10, 27), str(tmp_path), "off")
    second = monitor.run(pf, FixtureProvider(fx), date(2026, 10, 27), str(tmp_path), "off")
    assert first["alerts"] == second["alerts"]
    assert len(second["analytics"]["nav_curve"]) == 1


def test_live_mode_without_key_skips(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert layer3_context.claude_review("x", "live")["mode"] == "skipped"


def test_cli_missing_portfolio(tmp_path):
    assert monitor.main(["--portfolio", str(tmp_path / "nope.json")]) == 2


# --- Live Claude path against a local mock endpoint ------------------------------

class _ClaudeMock(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["messages"][0]["role"] == "system"
        reply = json.dumps({"book": "Mock read.", "positions": {
            "HIMS-30C-2026-12": {"summary": "Beat and raise.", "sentiment": "bullish", "action": "trim",
                                 "reason": "Target hit with 38 DTE left."}}})
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                          "choices": [{"index": 0, "finish_reason": "stop",
                                       "message": {"role": "assistant", "content": reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def test_live_review_against_mock(tmp_path, monkeypatch):
    pytest.importorskip("openai")
    srv = HTTPServer(("127.0.0.1", 0), _ClaudeMock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(layer3_context, "ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1/")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    try:
        res = monitor.run(load_portfolio(), FixtureProvider(os.path.join(FIX, "day2.json")),
                          date(2026, 10, 27), str(tmp_path), "live")
    finally:
        srv.shutdown()
    assert res["context"]["review"]["mode"] == "live"
    assert any(a["kind"] == "claude" and "TRIM" in a["message"] for a in res["alerts"])
    assert "Mock read." in (tmp_path / "dashboard.html").read_text(encoding="utf-8")
