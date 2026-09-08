"""Offline smoke tests for run_prompt.py — no API keys, no external network.

These guard the failure modes we actually hit: a SyntaxError that made the
script unrunnable, and the provider/dry-run wiring.
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "run_prompt.py")
sys.path.insert(0, ROOT)

import run_prompt  # noqa: E402


def cli(*args, env=None):
    """Run the CLI in a clean env with all provider creds stripped."""
    e = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "FREELLMAPI_KEY"):
        e.pop(k, None)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, RUNNER, *args], capture_output=True, text=True, env=e
    )


def test_list_profiles():
    r = cli("--list-profiles")
    assert r.returncode == 0
    for name in ("seo-research", "ad-copy", "bulk-copy"):
        assert name in r.stdout


def test_dry_run_freellmapi():
    r = cli("--dry-run", "--provider", "freellmapi", "--profile", "ad-copy", "--text", "hi")
    assert r.returncode == 0
    assert "DRY RUN" in r.stdout
    assert "auto:ad-copy" in r.stdout
    assert "localhost:3001" in r.stdout


def test_dry_run_claude_no_key():
    r = cli("--dry-run", "--provider", "claude", "--profile", "seo-research", "--text", "hi")
    assert r.returncode == 0
    assert "api.anthropic.com" in r.stdout
    assert "claude" in r.stdout
    assert "MISSING/placeholder" in r.stdout


def test_auto_detects_claude_when_key_present():
    r = cli("--dry-run", "--profile", "bulk-copy", "--text", "hi",
            env={"ANTHROPIC_API_KEY": "sk-ant-fake"})
    assert r.returncode == 0
    assert "Provider:  claude" in r.stdout
    assert "API key:   set" in r.stdout


def test_claude_live_without_key_exits_cleanly():
    r = cli("--provider", "claude", "--text", "hi")
    assert r.returncode == 1
    assert "ANTHROPIC_API_KEY is not set" in r.stdout
    assert "Traceback" not in r.stderr


def test_requires_some_input():
    r = cli("--dry-run")
    assert r.returncode != 0


def test_load_prompt_file_extracts_step1(tmp_path):
    p = tmp_path / "pack.md"
    p.write_text(
        "## Step 1\n\n**User prompt:**\n```\nHELLO {{X}}\n```\n", encoding="utf-8"
    )
    assert run_prompt.load_prompt_file(str(p)) == "HELLO {{X}}"


def test_resolve_provider_auto(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert run_prompt.resolve_provider("auto") == "freellmapi"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert run_prompt.resolve_provider("auto") == "claude"


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        reply = f"MOCK_OK model={body.get('model')}"
        data = json.dumps({
            "id": "x", "object": "chat.completion", "model": body.get("model"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def mock_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}/v1"
    finally:
        srv.shutdown()


def test_end_to_end_against_mock(mock_server):
    pytest.importorskip("openai")
    r = cli("--provider", "freellmapi", "--base-url", mock_server, "--api-key", "t",
            "--profile", "seo-research", "--text", "hello")
    assert r.returncode == 0, r.stderr
    assert "MOCK_OK model=auto:seo-research" in r.stdout
