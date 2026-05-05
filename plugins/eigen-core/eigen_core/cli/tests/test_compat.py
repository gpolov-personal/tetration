"""Tests for the C5 daemon compatibility check."""

from __future__ import annotations

import http.server
import json
import threading
from contextlib import contextmanager

import pytest

from eigen_core.cli import compat


@contextmanager
def fake_daemon(handler_payload, *, status: int = 200, raw: bytes | None = None):
    """Spin up a one-shot HTTP server that returns ``handler_payload`` (or
    ``raw`` bytes verbatim) for ``GET /api/v1/version``. Yields the URL.
    """

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if raw is not None:
                self.wfile.write(raw)
            else:
                self.wfile.write(json.dumps(handler_payload).encode())

        def log_message(self, *_a, **_k):  # silence test output
            return

    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_ok_when_all_supports_present():
    payload = {
        "version": "dev",
        "schema_version": 2,
        "supports": ["profile", "command_name", "resolved_runner", "resolved_model"],
        "profiles": ["claude-opus", "opencode-codex"],
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is True
    assert result.schema_version == 2
    assert "claude-opus" in result.profiles
    assert result.reason == ""


def test_missing_supports_flag():
    payload = {
        "version": "old",
        "schema_version": 1,
        "supports": ["profile"],  # missing command_name + resolved_*
        "profiles": [],
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is False
    assert "command_name" in result.reason
    assert "resolved_runner" in result.reason
    assert "Upgrade claude-tasks" in result.reason


def test_caller_overrides_required_supports():
    payload = {
        "version": "dev",
        "schema_version": 2,
        "supports": ["profile"],
        "profiles": [],
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url, required_supports=["profile"])
    assert result.ok is True


def test_unreachable_daemon():
    # Pick an unused port (we never bind it).
    result = compat.check_daemon_compat("http://127.0.0.1:1", timeout=0.5)
    assert result.ok is False
    assert "could not reach" in result.reason


def test_non_json_body():
    with fake_daemon({}, raw=b"not json at all") as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is False
    assert "non-JSON" in result.reason


def test_normalise_url_strips_trailing_slash():
    payload = {
        "version": "dev",
        "schema_version": 2,
        "supports": list(compat.DEFAULT_REQUIRED_SUPPORTS),
        "profiles": [],
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url + "/")
    assert result.ok is True


def test_non_object_response():
    with fake_daemon([], raw=b'["wrong","type"]') as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is False
    assert "non-object" in result.reason


def test_malformed_supports_field_rejected():
    """A daemon that ships with supports='profile' (string instead of
    list) would silently pass the membership check via substring match.
    Force a typed error instead."""
    payload = {
        "version": "buggy",
        "schema_version": 2,
        "supports": "profile",  # WRONG: should be a list
        "profiles": [],
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is False
    assert "malformed shape" in result.reason
    assert "supports=str" in result.reason


def test_malformed_profiles_field_rejected():
    payload = {
        "version": "buggy",
        "schema_version": 2,
        "supports": list(compat.DEFAULT_REQUIRED_SUPPORTS),
        "profiles": "claude-opus",  # WRONG: should be a list
    }
    with fake_daemon(payload) as url:
        result = compat.check_daemon_compat(url)
    assert result.ok is False
    assert "malformed shape" in result.reason
    assert "profiles=str" in result.reason


# ── check_active_runs (C8 sync gate) ────────────────────────────────────


@contextmanager
def fake_active_runs_endpoint(payload, *, raw: bytes | None = None):
    """One-shot HTTP server for ``GET /api/v1/runs/active``."""

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if raw is not None:
                self.wfile.write(raw)
            else:
                self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *_a, **_k):
            return

    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_active_runs_zero_passes_gate():
    with fake_active_runs_endpoint({"total": 0}) as url:
        result = compat.check_active_runs(url, profile_prefix="opencode-")
    assert result.ok is True
    assert result.total == 0
    assert result.reason == ""


def test_active_runs_nonzero_reports_count():
    with fake_active_runs_endpoint({"total": 3}) as url:
        result = compat.check_active_runs(url, profile_prefix="opencode-")
    assert result.ok is True
    assert result.total == 3


def test_active_runs_unreachable_fails_closed():
    """Sibling of test_unreachable_daemon — same fail-closed contract."""
    result = compat.check_active_runs("http://127.0.0.1:1", timeout=0.5)
    assert result.ok is False
    assert "could not query active runs" in result.reason


def test_active_runs_non_json_fails_closed():
    with fake_active_runs_endpoint({}, raw=b"not json") as url:
        result = compat.check_active_runs(url)
    assert result.ok is False
    assert "non-JSON response" in result.reason


def test_active_runs_non_object_fails_closed():
    with fake_active_runs_endpoint([], raw=b"[]") as url:
        result = compat.check_active_runs(url)
    assert result.ok is False
    assert "non-object" in result.reason


def test_active_runs_non_integer_total_fails_closed():
    with fake_active_runs_endpoint({"total": "many"}) as url:
        result = compat.check_active_runs(url)
    assert result.ok is False
    assert "non-integer total" in result.reason
